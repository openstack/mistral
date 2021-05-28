# Copyright 2018 - Nokia Networks.
#
# Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

import copy
import datetime
import eventlet
import random
import threading

from oslo_config import cfg
from oslo_log import log as logging
from oslo_utils import importutils
from osprofiler import profiler

from mistral import context
from mistral.db import utils as db_utils
from mistral.db.v2 import api as db_api
from mistral import exceptions as exc
from mistral.scheduler import base
from mistral_lib import utils


LOG = logging.getLogger(__name__)

CONF = cfg.CONF


class DefaultScheduler(base.Scheduler):
    def __init__(self, conf):
        """Initializes a scheduler instance.

        # TODO(rakhmerov): Fix docstring
        :param fixed_delay: A fixed part of the delay (in seconds) that
            defines how often this scheduler checks the persistent job
            store for the new jobs to run.
        :param random_delay: A random part of the delay (in seconds) that
            defines how often this scheduler checks the persistent job
            store for the new jobs to run.
        :param batch_size: Defines how many jobs this scheduler can pick
            up from the job store at once.
        """

        self._fixed_delay = conf.fixed_delay
        self._random_delay = conf.random_delay
        self._batch_size = conf.batch_size

        # Dictionary containing {GreenThread: ScheduledJob} pairs that
        # represent in-memory jobs.
        self.in_memory_jobs = {}

        self._job_store_checker_thread = threading.Thread(
            target=self._job_store_checker
        )
        self._job_store_checker_thread.daemon = True

        self._stopped = True

    def start(self):
        self._stopped = False

        self._job_store_checker_thread.start()

    def stop(self, graceful=False):
        self._stopped = True

        if graceful:
            self._job_store_checker_thread.join()

    def _job_store_checker(self):
        while not self._stopped:
            LOG.debug(
                "Starting Scheduler Job Store checker [scheduler=%s]...", self
            )

            eventlet.sleep(
                self._fixed_delay +
                random.Random().randint(0, self._random_delay * 1000) * 0.001
            )

            try:
                self._process_store_jobs()
            except Exception:
                LOG.exception(
                    "Scheduler failed to process delayed calls"
                    " due to unexpected exception."
                )

    def _process_store_jobs(self):
        # Select and capture eligible jobs.
        with db_api.transaction():
            candidate_jobs = db_api.get_scheduled_jobs_to_start(
                utils.utc_now_sec(),
                self._batch_size
            )

            captured_jobs = [
                job for job in candidate_jobs
                if self._capture_scheduled_job(job)
            ]

        # Invoke and delete scheduled jobs.
        for job in captured_jobs:
            auth_ctx, func, func_args = self._prepare_job(job)

            self._invoke_job(auth_ctx, func, func_args)

            self._delete_scheduled_job(job)

    def schedule(self, job, allow_redistribute=False):
        scheduled_job = self._persist_job(job)

        self._schedule_in_memory(job.run_after, scheduled_job)

    def has_scheduled_jobs(self, **filters):
        # Checking in-memory jobs first.
        for j in self.in_memory_jobs.values():
            if filters and 'key' in filters and filters['key'] != j.key:
                continue

            if filters and 'processing' in filters:
                if filters['processing'] is (j.captured_at is None):
                    continue

            return True

        if filters and 'processing' in filters:
            processing = filters.pop('processing')

            filters['captured_at'] = {'neq' if processing else 'eq': None}

        return db_api.get_scheduled_jobs_count(**filters) > 0

    @staticmethod
    def _persist_job(job):
        ctx_serializer = context.RpcContextSerializer()

        ctx = (
            ctx_serializer.serialize_context(context.ctx())
            if context.has_ctx() else {}
        )

        execute_at = (utils.utc_now_sec() +
                      datetime.timedelta(seconds=job.run_after))

        args = job.func_args
        arg_serializers = job.func_arg_serializers

        if arg_serializers:
            for arg_name, serializer_path in arg_serializers.items():
                if arg_name not in args:
                    raise exc.MistralException(
                        "Serializable function argument %s"
                        " not found in func_args=%s"
                        % (arg_name, args))
                try:
                    serializer = importutils.import_class(serializer_path)()
                except ImportError as e:
                    raise ImportError(
                        "Cannot import class %s: %s" % (serializer_path, e)
                    )

                args[arg_name] = serializer.serialize(args[arg_name])

        values = {
            'run_after': job.run_after,
            'target_factory_func_name': job.target_factory_func_name,
            'func_name': job.func_name,
            'func_args': args,
            'func_arg_serializers': arg_serializers,
            'auth_ctx': ctx,
            'execute_at': execute_at,
            'captured_at': None,
            'key': job.key
        }

        return db_api.create_scheduled_job(values)

    def _schedule_in_memory(self, run_after, scheduled_job):
        green_thread = eventlet.spawn_after(
            run_after,
            self._process_memory_job,
            scheduled_job
        )

        self.in_memory_jobs[green_thread] = scheduled_job

    def _process_memory_job(self, scheduled_job):
        # 1. Capture the job in Job Store.
        if not self._capture_scheduled_job(scheduled_job):
            LOG.warning(
                "Unable to capture a scheduled job [scheduled_job=%s]",
                scheduled_job
            )

            return

        # 2. Invoke the target function.
        auth_ctx, func, func_args = self._prepare_job(scheduled_job)

        self._invoke_job(auth_ctx, func, func_args)

        self._delete_scheduled_job(scheduled_job)

        # 3. Delete the job from Job Store, if success.
        # TODO(rakhmerov):
        # 3.1 What do we do if invocation wasn't successful?

        # Delete from a local collection of in-memory jobs.
        del self.in_memory_jobs[eventlet.getcurrent()]

    @staticmethod
    def _capture_scheduled_job(scheduled_job):
        """Capture a scheduled persistent job in a job store.

        :param scheduled_job: Job.
        :return: True if the job has been captured, False if not.
        """

        now_sec = utils.utc_now_sec()

        # Mark this job as captured in order to prevent calling from
        # a parallel transaction. We don't use query filter
        # {'captured_at': None} to account for a case when the job needs
        # to be recaptured after a maximum capture time has elapsed. If this
        # method was called for a job that has non-empty "captured_at" then
        # it means that it is already eligible for recapturing and the
        # Job Store selected it.
        _, updated_cnt = db_api.update_scheduled_job(
            id=scheduled_job.id,
            values={'captured_at': now_sec},
            query_filter={'captured_at': scheduled_job.captured_at}
        )

        # We need to update "captured_at" of the initial object stored in
        # memory because it's used in a few places.
        if updated_cnt == 1:
            scheduled_job.captured_at = now_sec

        # If updated_cnt != 1 then another scheduler
        # has already updated it.
        return updated_cnt == 1

    @db_utils.retry_on_db_error
    def _delete_scheduled_job(self, scheduled_job):
        db_api.delete_scheduled_job(scheduled_job.id)

    @staticmethod
    def _prepare_job(scheduled_job):
        """Prepares a scheduled job for invocation.

        To make an invocation of a delayed call it needs to be prepared for
        further usage, we need to reconstruct a final target func
        and deserialize arguments, if needed.

        :param scheduled_job: Persistent scheduled job.
        :return: A tuple (auth_ctx, func, args) where all data is properly
            deserialized.
        """

        LOG.debug(
            'Preparing a scheduled job. [ID=%s, target_factory_func_name=%s,'
            ' func_name=%s, func_args=%s]',
            scheduled_job.id,
            scheduled_job.target_factory_func_name,
            scheduled_job.func_name,
            scheduled_job.func_args
        )

        auth_ctx = copy.deepcopy(scheduled_job.auth_ctx)

        if scheduled_job.target_factory_func_name:
            factory = importutils.import_class(
                scheduled_job.target_factory_func_name
            )

            func = getattr(factory(), scheduled_job.func_name)
        else:
            func = importutils.import_class(scheduled_job.func_name)

        args = copy.deepcopy(scheduled_job.func_args)

        serializers_dict = scheduled_job.func_arg_serializers

        if serializers_dict:
            # Deserialize arguments.
            for arg_name, ser_path in serializers_dict.items():
                serializer = importutils.import_class(ser_path)()

                deserialized = serializer.deserialize(args[arg_name])

                args[arg_name] = deserialized

        return auth_ctx, func, args

    @staticmethod
    def _invoke_job(auth_ctx, func, args):
        # Scheduler runs jobs in an separate thread that's neither related
        # to an RPC nor a REST request processing thread. So we need to
        # initialize a profiler specifically for this thread.
        if cfg.CONF.profiler.enabled:
            profiler.init(cfg.CONF.profiler.hmac_keys)

        ctx_serializer = context.RpcContextSerializer()

        try:
            # Set the correct context for the function.
            ctx_serializer.deserialize_context(auth_ctx)

            # Invoke the function.
            func(**args)
        except Exception as e:
            LOG.exception(
                "Scheduled job failed, method: %s, exception: %s",
                func,
                e
            )
        finally:
            # Remove context.
            context.set_ctx(None)
