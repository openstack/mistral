# Copyright 2015 - StackStorm, Inc.
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

from mistral.db.v2 import api as db_api
from mistral.services import workflows as wf_service
from mistral.tests.unit.engine import base
from mistral.workflow import states


class WorkflowStopTest(base.EngineTestCase):
    def setUp(self):
        super(WorkflowStopTest, self).setUp()

        WORKFLOW = """
        version: '2.0'

        wf:
          type: direct
          tasks:
            task1:
              action: std.echo output="Echo"
              on-complete:
                - task2

            task2:
              action: std.echo output="foo"
              wait-before: 3
        """
        wf_service.create_workflows(WORKFLOW)

        self.exec_id = self.engine.start_workflow('wf', {}).id

    def test_stop_failed(self):
        self.engine.stop_workflow(self.exec_id, states.SUCCESS, "Force stop")

        self.await_workflow_success(self.exec_id)

        wf_ex = db_api.get_workflow_execution(self.exec_id)

        self.assertEqual(states.SUCCESS, wf_ex.state)
        self.assertEqual("Force stop", wf_ex.state_info)

    def test_stop_succeeded(self):
        self.engine.stop_workflow(self.exec_id, states.ERROR, "Failure")

        self.await_workflow_error(self.exec_id)

        wf_ex = db_api.get_workflow_execution(self.exec_id)

        self.assertEqual(states.ERROR, wf_ex.state)
        self.assertEqual("Failure", wf_ex.state_info)
