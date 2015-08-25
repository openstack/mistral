# Copyright 2015 - Mirantis, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

from oslo_config import cfg
from oslo_log import log as logging

from mistral.db.v2 import api as db_api
from mistral.services import workflows as wf_service
from mistral.tests.unit.engine import base
from mistral.workflow import states


LOG = logging.getLogger(__name__)

# Use the set_default method to set value otherwise in certain test cases
# the change in value is not permanent.
cfg.CONF.set_default('auth_enable', False, group='pecan')


class DirectWorkflowWithCyclesTest(base.EngineTestCase):
    def test_direct_workflow_on_closures(self):
        wf_text = """
        version: '2.0'

        wf:
          vars:
            cnt: 0

          output:
            cnt: <% $.cnt %>

          tasks:
            task1:
              on-complete:
                - task2

            task2:
              action: std.echo output=2
              publish:
                cnt: <% $.cnt + 1 %>
              on-success:
                - task3

            task3:
              action: std.echo output=3
              on-success:
                - task2: <% $.cnt < 2 %>
        """

        wf_service.create_workflows(wf_text)

        wf_ex = self.engine.start_workflow('wf', {})

        self._await(lambda: self.is_execution_success(wf_ex.id))

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        task_execs = wf_ex.task_executions

        # Expecting one execution for task1 and two executions
        # for task2 and task3 because of the cycle 'task2 <-> task3'.
        task1_ex = self._assert_single_item(task_execs, name='task1')
        task2_execs = self._assert_multiple_items(task_execs, 2, name='task2')
        task3_execs = self._assert_multiple_items(task_execs, 2, name='task3')

        self.assertEqual(5, len(task_execs))

        self.assertTrue(wf_ex.state, states.SUCCESS)
        self.assertTrue(task1_ex.state, states.SUCCESS)
        self.assertTrue(task2_execs[0].state, states.SUCCESS)
        self.assertTrue(task2_execs[1].state, states.SUCCESS)
        self.assertTrue(task3_execs[0].state, states.SUCCESS)
        self.assertTrue(task3_execs[1].state, states.SUCCESS)

        # TODO(rakhmerov): Evaluation of workflow output doesn't work yet.
        # Need to fix it.
        # self.assertEqual(3, wf_ex.output)
