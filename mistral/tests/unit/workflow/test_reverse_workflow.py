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

from mistral.db.v2 import api as db_api
from mistral.db.v2.sqlalchemy import models
from mistral import exceptions as exc
from mistral.services import workbooks as wb_service
from mistral.tests.unit import base
from mistral.workbook import parser as spec_parser
from mistral.workflow import reverse_workflow as reverse_wf
from mistral.workflow import states


# TODO(rakhmerov): This workflow is too simple. Add more complicated one.

WB = """
---
version: '2.0'

name: my_wb

workflows:
  wf:
    type: reverse
    tasks:
      task1:
        action: std.echo output="Hey"

      task2:
        action: std.echo output="Hi!"
        requires: [task1]
"""


class ReverseWorkflowControllerTest(base.DbTestCase):
    def setUp(self):
        super(ReverseWorkflowControllerTest, self).setUp()

        wb_service.create_workbook_v2(WB)

        self.wb_spec = spec_parser.get_workbook_spec_from_yaml(WB)

    def _create_workflow_execution(self, params):
        wf_def = db_api.get_workflow_definitions()[0]

        self.wf_ex = db_api.create_workflow_execution({
            'id': '1-2-3-4',
            'spec': self.wb_spec.get_workflows().get('wf').to_dict(),
            'state': states.RUNNING,
            'params': params,
            'workflow_id': wf_def.id
        })

    def _create_task_execution(self, name, state):
        tasks_spec = self.wb_spec.get_workflows()['wf'].get_tasks()

        return db_api.create_task_execution({
            'name': name,
            'spec': tasks_spec[name].to_dict(),
            'state': state,
            'workflow_execution_id': self.wf_ex.id
        })

    def test_start_workflow_task2(self):
        with db_api.transaction():
            self._create_workflow_execution({'task_name': 'task2'})

            wf_ctrl = reverse_wf.ReverseWorkflowController(self.wf_ex)

            cmds = wf_ctrl.continue_workflow()

        self.assertEqual(1, len(cmds))
        self.assertEqual('task1', cmds[0].task_spec.get_name())

    def test_start_workflow_task1(self):
        with db_api.transaction():
            self._create_workflow_execution({'task_name': 'task1'})

            wf_ctrl = reverse_wf.ReverseWorkflowController(self.wf_ex)

            cmds = wf_ctrl.continue_workflow()

        self.assertEqual(1, len(cmds))
        self.assertEqual('task1', cmds[0].task_spec.get_name())

    def test_start_workflow_without_task(self):
        with db_api.transaction():
            self._create_workflow_execution({})

            wf_ctrl = reverse_wf.ReverseWorkflowController(self.wf_ex)

        self.assertRaises(exc.WorkflowException, wf_ctrl.continue_workflow)

    def test_continue_workflow(self):
        with db_api.transaction():
            self._create_workflow_execution({'task_name': 'task2'})

            wf_ctrl = reverse_wf.ReverseWorkflowController(self.wf_ex)

            # Assume task1 completed.
            task1_ex = self._create_task_execution('task1', states.SUCCESS)

            task1_ex.executions.append(
                models.ActionExecution(
                    name='std.echo',
                    workflow_name='wf',
                    state=states.SUCCESS,
                    output={'result': 'Hey'},
                    accepted=True
                )
            )

            cmds = wf_ctrl.continue_workflow()

            task1_ex.processed = True

            self.assertEqual(1, len(cmds))
            self.assertEqual('task2', cmds[0].task_spec.get_name())

            # Now assume task2 completed.
            task2_ex = self._create_task_execution('task2', states.SUCCESS)

            task2_ex.executions.append(
                models.ActionExecution(
                    name='std.echo',
                    workflow_name='wf',
                    state=states.SUCCESS,
                    output={'result': 'Hi!'},
                    accepted=True
                )
            )

            cmds = wf_ctrl.continue_workflow()

            task1_ex.processed = True

            self.assertEqual(0, len(cmds))
