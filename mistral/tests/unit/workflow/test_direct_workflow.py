# Copyright 2015 - Mirantis, Inc.
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

import mock

from mistral.db.v2 import api as db_api
from mistral.db.v2.sqlalchemy import models
from mistral import exceptions as exc
from mistral.services import workflows as wf_service
from mistral.tests.unit import base
from mistral.workbook import parser as spec_parser
from mistral.workflow import direct_workflow as d_wf
from mistral.workflow import states


class DirectWorkflowControllerTest(base.DbTestCase):
    def _prepare_test(self, wf_text):
        wfs = wf_service.create_workflows(wf_text)
        wf_spec = spec_parser.get_workflow_spec_by_definition_id(
            wfs[0].id,
            wfs[0].updated_at
        )

        wf_ex = models.WorkflowExecution(
            id='1-2-3-4',
            spec=wf_spec.to_dict(),
            state=states.RUNNING,
            workflow_id=wfs[0].id,
            input={},
            context={}
        )

        self.wf_ex = wf_ex
        self.wf_spec = wf_spec

        return wf_ex

    def _create_task_execution(self, name, state):
        tasks_spec = self.wf_spec.get_tasks()

        task_ex = models.TaskExecution(
            id=self.getUniqueString('id'),
            name=name,
            spec=tasks_spec[name].to_dict(),
            state=state
        )

        self.wf_ex.task_executions.append(task_ex)

        return task_ex

    @mock.patch.object(db_api, 'get_workflow_execution')
    @mock.patch.object(db_api, 'get_task_execution')
    def test_continue_workflow(self, get_task_execution,
                               get_workflow_execution):
        wf_text = """---
        version: '2.0'

        wf:
          type: direct

          tasks:
            task1:
              action: std.echo output="Hey"
              publish:
                res1: <% $.task1 %>
              on-complete:
                - task2: <% $.res1 = 'Hey' %>
                - task3: <% $.res1 = 'Not Hey' %>

            task2:
              action: std.echo output="Hi"

            task3:
              action: std.echo output="Hoy"
        """

        wf_ex = self._prepare_test(wf_text)

        get_workflow_execution.return_value = wf_ex

        wf_ctrl = d_wf.DirectWorkflowController(wf_ex)

        # Workflow execution is in initial step. No running tasks.
        cmds = wf_ctrl.continue_workflow()

        self.assertEqual(1, len(cmds))

        cmd = cmds[0]

        self.assertIs(wf_ctrl.wf_ex, cmd.wf_ex)
        self.assertIsNotNone(cmd.task_spec)
        self.assertEqual('task1', cmd.task_spec.get_name())
        self.assertEqual(states.RUNNING, self.wf_ex.state)

        # Assume that 'task1' completed successfully.
        task1_ex = self._create_task_execution('task1', states.SUCCESS)
        task1_ex.published = {'res1': 'Hey'}

        get_task_execution.return_value = task1_ex

        task1_ex.action_executions.append(
            models.ActionExecution(
                name='std.echo',
                workflow_name='wf',
                state=states.SUCCESS,
                output={'result': 'Hey'},
                accepted=True,
                runtime_context={'index': 0}
            )
        )

        cmds = wf_ctrl.continue_workflow()

        task1_ex.processed = True

        self.assertEqual(1, len(cmds))
        self.assertEqual('task2', cmds[0].task_spec.get_name())

        self.assertEqual(states.RUNNING, self.wf_ex.state)
        self.assertEqual(states.SUCCESS, task1_ex.state)

        # Now assume that 'task2' completed successfully.
        task2_ex = self._create_task_execution('task2', states.SUCCESS)
        task2_ex.action_executions.append(
            models.ActionExecution(
                name='std.echo',
                workflow_name='wf',
                state=states.SUCCESS,
                output={'result': 'Hi'},
                accepted=True
            )
        )

        cmds = wf_ctrl.continue_workflow()

        task2_ex.processed = True

        self.assertEqual(0, len(cmds))

    def test_continue_workflow_no_start_tasks(self):
        wf_text = """---
        version: '2.0'

        wf:
          description: >
            Invalid workflow that doesn't have start tasks (tasks with
            no inbound connections).
          type: direct

          tasks:
            task1:
              on-complete: task2

            task2:
              on-complete: task1
        """

        self.assertRaises(exc.DSLParsingException, self._prepare_test, wf_text)
