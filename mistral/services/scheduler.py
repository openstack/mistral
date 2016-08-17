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

from oslo_config import cfg
from oslo_log import log as logging
from oslo_service import periodic_task
from oslo_service import threadgroup
from oslo_utils import importutils

from mistral import context
from mistral.db.v2 import api as db_api
from mistral import exceptions as exc


LOG = logging.getLogger(__name__)

CONF = cfg.CONF

# {scheduler_instance: thread_group}
_schedulers = {}


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
    ctx_serializer = context.RpcContextSerializer(
        context.JsonPayloadSerializer()
    )

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


class CallScheduler(periodic_task.PeriodicTasks):
    # TODO(rakhmerov): Think how to make 'spacing' configurable.
    @periodic_task.periodic_task(spacing=1, run_immediately=True)
    def run_delayed_calls(self, ctx=None):
        time_filter = datetime.datetime.now() + datetime.timedelta(
            seconds=1)

        # Wrap delayed calls processing in transaction to guarantee that calls
        # will be processed just once. Do delete query to DB first to force
        # hanging up all parallel transactions.
        # It should work with transactions which run at least 'READ-COMMITTED'
        # mode.
        delayed_calls = []

        with db_api.transaction():
            candidate_calls = db_api.get_delayed_calls_to_start(
                time_filter
            )
            calls_to_make = []

            for call in candidate_calls:
                # Mark this delayed call has been processed in order to
                # prevent calling from parallel transaction.
                result, number_of_updated = db_api.update_delayed_call(
                    id=call.id,
                    values={'processing': True},
                    query_filter={'processing': False}
                )

                # If number_of_updated != 1 other scheduler already
                # updated.
                if number_of_updated == 1:
                    calls_to_make.append(result)

        for call in calls_to_make:
            LOG.debug('Processing next delayed call: %s', call)

            target_auth_context = copy.deepcopy(call.auth_context)

            if call.factory_method_path:
                factory = importutils.import_class(
                    call.factory_method_path
                )

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

            delayed_calls.append(
                (target_auth_context, target_method, method_args)
            )

        ctx_serializer = context.RpcContextSerializer(
            context.JsonPayloadSerializer()
        )

        for (target_auth_context, target_method, method_args) in delayed_calls:
            try:
                # Set the correct context for the method.
                ctx_serializer.deserialize_context(target_auth_context)

                # Call the method.
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

        with db_api.transaction():
            for call in calls_to_make:
                try:
                    # Delete calls that were processed.
                    db_api.delete_delayed_call(call.id)
                except Exception as e:
                    LOG.error(
                        "failed to delete call [call=%s, "
                        "exception=%s]", call, e
                    )


def setup():
    tg = threadgroup.ThreadGroup()

    scheduler = CallScheduler(CONF)

    tg.add_dynamic_timer(
        scheduler.run_periodic_tasks,
        initial_delay=None,
        periodic_interval_max=1,
        context=None
    )

    _schedulers[scheduler] = tg

    return tg


def stop_all_schedulers():
    for scheduler, tg in _schedulers.items():
        tg.stop()
        del _schedulers[scheduler]
