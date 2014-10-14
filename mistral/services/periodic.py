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
from mistral.db.v1 import api as db_api_v1
from mistral.db.v2 import api as db_api_v2
from mistral import engine
from mistral.engine1 import rpc
from mistral.openstack.common import log
from mistral.openstack.common import periodic_task
from mistral.openstack.common import threadgroup
from mistral.services import triggers
from mistral.services import trusts
from mistral.workbook import parser as spec_parser

LOG = log.getLogger(__name__)


class MistralPeriodicTasks(periodic_task.PeriodicTasks):

    def __init__(self, transport=None):
        super(MistralPeriodicTasks, self).__init__()

        self.transport = engine.get_transport(transport)
        self.engine = engine.EngineClient(self.transport)

    @periodic_task.periodic_task(spacing=1, run_immediately=True)
    def process_cron_triggers_v1(self, ctx):
        LOG.debug('Processing cron triggers.')

        for t in triggers.get_next_triggers_v1():
            # Setup admin context before schedule triggers.
            wb = db_api_v1.workbook_get(t['workbook_name'])

            auth_ctx.set_ctx(trusts.create_context(wb.trust_id, wb.project_id))

            try:
                task = spec_parser.get_workbook_spec_from_yaml(
                    wb['definition']).get_trigger_task_name(t['name'])

                self.engine.start_workflow_execution(wb['name'], task)
            finally:
                next_time = triggers.get_next_execution_time(
                    t['pattern'],
                    t['next_execution_time']
                )

                db_api_v1.trigger_update(
                    t['id'],
                    {'next_execution_time': next_time}
                )

                auth_ctx.set_ctx(None)

    @periodic_task.periodic_task(spacing=1, run_immediately=True)
    def process_cron_triggers_v2(self, ctx):
        LOG.debug('Processing cron triggers.')

        for t in triggers.get_next_cron_triggers():
            # Setup admin context before schedule triggers.
            ctx = trusts.create_context(t.trust_id, t.project_id)

            auth_ctx.set_ctx(ctx)

            LOG.debug("Cron trigger security context: %s" % ctx)

            try:
                rpc.get_engine_client().start_workflow(
                    t.workflow.name,
                    t.workflow_input
                )
            finally:
                next_time = triggers.get_next_execution_time(
                    t.pattern,
                    t.next_execution_time
                )

                db_api_v2.update_cron_trigger(
                    t.name,
                    {'next_execution_time': next_time}
                )

                auth_ctx.set_ctx(None)


def setup(transport):
    tg = threadgroup.ThreadGroup()
    pt = MistralPeriodicTasks(transport=transport)

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
