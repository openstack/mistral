# -*- coding: utf-8 -*-
#
# Copyright 2013 - Mirantis, Inc.
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

from mistral import context as auth_ctx
from mistral.db.v2 import api as db_api_v2
from mistral.engine import rpc
from mistral.openstack.common import log
from mistral.openstack.common import periodic_task
from mistral.openstack.common import threadgroup
from mistral.services import security
from mistral.services import triggers

LOG = log.getLogger(__name__)


class MistralPeriodicTasks(periodic_task.PeriodicTasks):
    @periodic_task.periodic_task(spacing=1, run_immediately=True)
    def process_cron_triggers_v2(self, ctx):
        for t in triggers.get_next_cron_triggers():
            LOG.debug("Processing cron trigger: %s" % t)
            # Setup admin context before schedule triggers.
            ctx = security.create_context(t.trust_id, t.project_id)
            auth_ctx.set_ctx(ctx)

            LOG.debug("Cron trigger security context: %s" % ctx)

            try:
                rpc.get_engine_client().start_workflow(
                    t.workflow.name,
                    t.workflow_input,
                    **t.workflow_params
                )
            finally:
                if t.remaining_executions > 0:
                    t.remaining_executions -= 1
                if t.remaining_executions == 0:
                    db_api_v2.delete_cron_trigger(t.name)
                else:  # if remaining execution = None or > 0
                    next_time = triggers.get_next_execution_time(
                        t.pattern,
                        t.next_execution_time
                    )

                    db_api_v2.update_cron_trigger(
                        t.name,
                        {'next_execution_time': next_time,
                         'remaining_executions': t.remaining_executions}
                    )

                    auth_ctx.set_ctx(None)


def setup():
    tg = threadgroup.ThreadGroup()
    pt = MistralPeriodicTasks()

    ctx = auth_ctx.MistralContext(
        user_id=None,
        project_id=None,
        auth_token=None,
        is_admin=True
    )

    tg.add_dynamic_timer(
        pt.run_periodic_tasks,
        initial_delay=None,
        periodic_interval_max=1,
        context=ctx
    )
