# Copyright 2014 - Mirantis, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License");
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


import datetime

from mistral import context
from mistral.db.v2 import api as db_api
from mistral.openstack.common import importutils
from mistral.openstack.common import log
from mistral.openstack.common import periodic_task
from mistral.openstack.common import threadgroup


LOG = log.getLogger(__name__)


def schedule_call(factory_method_path, target_method_name,
                  run_after, **method_args):
    """Add this call specification to DB, and then after run_after
    seconds service CallScheduler invokes the target_method.

    :param factory_method_path: Full python-specific path to
    factory method for target object construction.
    :param target_method_name: Name of target object method which
    will be invoked.
    :param run_after: Value in seconds.
    :param method_args: Target method keyword arguments.
    :return: None
    """
    ctx = context.ctx().to_dict() if context.has_ctx() else {}

    execution_time = (datetime.datetime.now()
                      + datetime.timedelta(seconds=run_after))

    values = {
        'factory_method_path': factory_method_path,
        'target_method_name': target_method_name,
        'execution_time': execution_time,
        'auth_context': ctx,
        'method_arguments': method_args
    }

    db_api.create_delayed_call(values)


class CallScheduler(periodic_task.PeriodicTasks):
    @periodic_task.periodic_task(spacing=1)
    def run_delayed_calls(self, ctx=None):
        LOG.debug('Processing next delayed calls.')

        datetime_filter = (datetime.datetime.now()
                           + datetime.timedelta(seconds=1))
        delayed_calls = db_api.get_delayed_calls_to_start(datetime_filter)

        for call in delayed_calls:
            ctx = context.MistralContext(call.auth_context)
            context.set_ctx(ctx)

            if call.factory_method_path:
                factory = importutils.import_class(call.factory_method_path)
                target_object = factory()
                target_method = getattr(target_object,
                                        call.target_method_name)
            else:
                target_method = importutils.import_class(
                    call.target_method_name)
            try:
                # Call the method.
                target_method(**call.method_arguments)
            except Exception as e:
                LOG.debug("Exception was thrown during the "
                          "delayed call %s - %s", call, e)
            finally:
                # After call, delete this delayed call from DB.
                db_api.delete_delayed_call(call.id)


def setup():
    tg = threadgroup.ThreadGroup()
    pt = CallScheduler()

    tg.add_dynamic_timer(
        pt.run_periodic_tasks,
        initial_delay=None,
        periodic_interval_max=1,
        context=None)
