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

from mistral import context
from mistral.db.v1 import api as db_api
from mistral import engine
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
    def scheduler_triggers(self, ctx):
        LOG.debug('Processing next Scheduler triggers.')

        for trigger in triggers.get_next_triggers():
            # Setup admin context before schedule triggers.
            context.set_ctx(ctx)

            wb = db_api.workbook_get(trigger['workbook_name'])

            context.set_ctx(trusts.create_context(wb.trust_id, wb.project_id))

            try:
                task = spec_parser.get_workbook_spec_from_yaml(
                    wb['definition']).get_trigger_task_name(trigger['name'])

                self.engine.start_workflow_execution(wb['name'], task)
            finally:
                triggers.set_next_execution_time(trigger)
                context.set_ctx(None)


def setup(transport):
    tg = threadgroup.ThreadGroup()
    pt = MistralPeriodicTasks(transport=transport)

    ctx = context.MistralContext(
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
