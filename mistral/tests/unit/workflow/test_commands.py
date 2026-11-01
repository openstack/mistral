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

from mistral.db.v2 import api as db_api
from mistral.lang import parser as spec_parser
from mistral.services import workflows as wf_service
from mistral.tests.unit import base
from mistral.workflow import commands
from mistral.workflow import states


WF = """
---
version: '2.0'

wf:
  tasks:
    task1:
      action: std.noop
"""


class WorkflowCommandsTest(base.DbTestCase):
    def setUp(self):
        super(WorkflowCommandsTest, self).setUp()

        wf_def = wf_service.create_workflows(WF)[0]

        wf_spec = spec_parser.get_workflow_spec_by_definition_id(
            wf_def.id, wf_def.updated_at
        )

        self.wf_ex = db_api.create_workflow_execution(
            {
                'spec': wf_spec.to_dict(),
                'state': states.RUNNING,
                'workflow_id': wf_def.id,
            }
        )

        self.task_ex = db_api.create_task_execution(
            {
                'name': 'task1',
                'spec': wf_spec.get_tasks()['task1'].to_dict(),
                'state': states.ERROR,
                'workflow_execution_id': self.wf_ex.id,
            }
        )

        self.wf_spec = wf_spec

    def test_restore_run_existing_task(self):
        triggered_by = [{'task_id': 'task-id', 'event': 'on-success'}]

        with db_api.transaction():
            cmd = commands.RunExistingTask(
                self.wf_ex,
                self.wf_spec,
                self.task_ex,
                reset=False,
                triggered_by=triggered_by,
                rerun=True,
            )

            restored = commands.restore_command_from_dict(
                self.wf_ex, cmd.to_dict()
            )

        self.assertIsInstance(restored, commands.RunExistingTask)
        self.assertEqual(self.task_ex.id, restored.task_ex.id)
        self.assertFalse(restored.reset)
        self.assertTrue(restored.rerun)
        self.assertEqual(triggered_by, restored.triggered_by)
