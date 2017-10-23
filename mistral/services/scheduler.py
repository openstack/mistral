# Copyright 2014 - Mirantis, Inc.
# Copyright 2015 - StackStorm, Inc.
# Copyright 2016 - Brocade Communications Systems, Inc.
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

from mistral import context
from mistral.db import utils as db_utils
from mistral.db.v2 import api as db_api
from mistral import exceptions as exc


LOG = logging.getLogger(__name__)

CONF = cfg.CONF

# All schedulers.
_schedulers = set()


def schedule_call(factory_method_path, target_method_name,
                  run_after, serializers=None, key=None, **method_args):
    """Schedules call and lately invokes target_method.

    Add this call specification to DB, and then after run_after
    seconds service CallScheduler invokes the target_method.

    :param factory_method_path: Full python-specific path to
        factory method that creates a target object that the call will be
        made against.
    :param target_method_name: Name of a method which will be invoked.
    :param run_after: Value in seconds.
    :param serializers: map of argument names and their serializer class
        paths. Use when an argument is an object of specific type, and needs
        to be serialized. Example:
        { "result": "mistral.utils.serializer.ResultSerializer"}
        Serializer for the object type must implement serializer interface
        in mistral/utils/serializer.py
    :param key: Key which can potentially be used for squashing similar
        delayed calls.
    :param method_args: Target method keyword arguments.
    """
    ctx_serializer = context.RpcContextSerializer()

    ctx = (
        ctx_serializer.serialize_context(context.ctx())
        if context.has_ctx() else {}
    )

    execution_time = (datetime.datetime.now() +
                      datetime.timedelta(seconds=run_after))

    if serializers:
        for arg_name, serializer_path in serializers.items():
            if arg_name not in method_args:
                raise exc.MistralException(
                    "Serializable method argument %s"
                    " not found in method_args=%s"
                    % (arg_name, method_args))
            try:
                serializer = importutils.import_class(serializer_path)()
            except ImportError as e:
                raise ImportError(
                    "Cannot import class %s: %s" % (serializer_path, e)
                )

            method_args[arg_name] = serializer.serialize(method_args[arg_name])

    values = {
        'factory_method_path': factory_method_path,
        'target_method_name': target_method_name,
        'execution_time': execution_time,
        'auth_context': ctx,
        'serializers': serializers,
        'key': key,
        'method_arguments': method_args,
        'processing': False
    }

    db_api.create_delayed_call(values)


class Scheduler(object):
    def __init__(self):
        self._stopped = False
        self._thread = threading.Thread(target=self._loop)
        self._thread.daemon = True
        self._fixed_delay = CONF.scheduler.fixed_delay
        self._random_delay = CONF.scheduler.random_delay

    def start(self):
        self._thread.start()

    def stop(self, graceful=False):
        self._stopped = True

        if graceful:
            self._thread.join()

    def _loop(self):
        while not self._stopped:
            LOG.debug("Starting Scheduler loop [scheduler=%s]...", self)

            try:
                self._process_delayed_calls()
            except Exception:
                LOG.exception(
                    "Scheduler failed to process delayed calls"
                    " due to unexpected exception."
                )

            eventlet.sleep(
                self._fixed_delay +
                random.Random().randint(0, self._random_delay * 1000) * 0.001
            )

    def _process_delayed_calls(self, ctx=None):
        """Run delayed required calls.

        This algorithm should work with transactions having at least
        'READ-COMMITTED' isolation mode.

        :param ctx: Auth context.
        """

        # Select and capture calls matching time criteria.
        db_calls = self._capture_calls()

        if not db_calls:
            return

        # Determine target methods, deserialize arguments etc.
        prepared_calls = self._prepare_calls(db_calls)

        # Invoke prepared calls.
        self._invoke_calls(prepared_calls)

        # Delete invoked calls from DB.
        self.delete_calls(db_calls)

    @staticmethod
    @db_utils.retry_on_deadlock
    def _capture_calls():
        """Captures delayed calls eligible for processing (based on time).

        The intention of this method is to select delayed calls based on time
        criteria and mark them in DB as being processed so that no other
        threads could process them in parallel.

        :return: A list of delayed calls captured for further processing.
        """
        result = []

        time_filter = datetime.datetime.now() + datetime.timedelta(seconds=1)

        with db_api.transaction():
            candidates = db_api.get_delayed_calls_to_start(time_filter)

            for call in candidates:
                # Mark this delayed call has been processed in order to
                # prevent calling from parallel transaction.
                db_call, updated_cnt = db_api.update_delayed_call(
                    id=call.id,
                    values={'processing': True},
                    query_filter={'processing': False}
                )

                # If updated_cnt != 1 then another scheduler
                # has already updated it.
                if updated_cnt == 1:
                    result.append(db_call)

        LOG.debug("Scheduler captured %s delayed calls.", len(result))

        return result

    @staticmethod
    def _prepare_calls(raw_calls):
        """Prepares delayed calls for invocation.

        After delayed calls were selected from DB they still need to be
        prepared for further usage, we need to build final target methods
        and deserialize arguments, if needed.

        :param raw_calls: Delayed calls fetched from DB (DB models).
        :return: A list of tuples (target_auth_context, target_method,
         method_args) where all data is properly deserialized.
        """

        result = []

        for call in raw_calls:
            LOG.debug(
                'Preparing next delayed call. '
                '[ID=%s, factory_method_path=%s, target_method_name=%s, '
                'method_arguments=%s]', call.id, call.factory_method_path,
                call.target_method_name, call.method_arguments
            )

            target_auth_context = copy.deepcopy(call.auth_context)

            if call.factory_method_path:
                factory = importutils.import_class(call.factory_method_path)

                target_method = getattr(factory(), call.target_method_name)
            else:
                target_method = importutils.import_class(
                    call.target_method_name
                )

            method_args = copy.deepcopy(call.method_arguments)

            if call.serializers:
                # Deserialize arguments.
                for arg_name, ser_path in call.serializers.items():
                    serializer = importutils.import_class(ser_path)()

                    deserialized = serializer.deserialize(
                        method_args[arg_name]
                    )

                    method_args[arg_name] = deserialized

            result.append((target_auth_context, target_method, method_args))

        return result

    @staticmethod
    def _invoke_calls(delayed_calls):
        """Invokes prepared delayed calls.

        :param delayed_calls: Prepared delayed calls represented as tuples
        (target_auth_context, target_method, method_args).
        """

        ctx_serializer = context.RpcContextSerializer()

        for (target_auth_context, target_method, method_args) in delayed_calls:
            try:
                # Set the correct context for the method.
                ctx_serializer.deserialize_context(target_auth_context)

                # Invoke the method.
                target_method(**method_args)
            except Exception as e:
                LOG.exception(
                    "Delayed call failed, method: %s, exception: %s",
                    target_method,
                    e
                )
            finally:
                # Remove context.
                context.set_ctx(None)

    @staticmethod
    @db_utils.retry_on_deadlock
    def delete_calls(db_calls):
        """Deletes delayed calls.

        :param db_calls: Delayed calls to delete from DB.
        """

        with db_api.transaction():
            for call in db_calls:
                try:
                    db_api.delete_delayed_call(call.id)
                except Exception as e:
                    LOG.error(
                        "Failed to delete delayed call [call=%s, "
                        "exception=%s]", call, e
                    )

                    # We have to re-raise any exception because the transaction
                    # would be already invalid anyway. If it's a deadlock then
                    # it will be handled.
                    raise e

        LOG.debug("Scheduler deleted %s delayed calls.", len(db_calls))


def start():
    sched = Scheduler()

    _schedulers.add(sched)

    sched.start()

    return sched


def stop_scheduler(sched, graceful=False):
    if not sched:
        return

    sched.stop(graceful)

    _schedulers.remove(sched)


def stop_all_schedulers():
    for sched in _schedulers:
        sched.stop(graceful=True)

    _schedulers.clear()
