# Copyright 2014 - Mirantis, Inc.
# Copyright 2015 - StackStorm, Inc.
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
from oslo_config import cfg

from mistral.actions import std_actions
from mistral import context as auth_context
from mistral.db.v2 import api as db_api
from mistral import exceptions as exc
from mistral.services import workbooks as wb_service
from mistral.tests.unit.engine import base
from mistral.workflow import states


# Use the set_default method to set value otherwise in certain test cases
# the change in value is not permanent.
cfg.CONF.set_default('auth_enable', False, group='pecan')


WB1 = """
---
version: '2.0'

name: wb1

workflows:
  wf1:
    type: reverse

    input:
      - param1
      - param2
    output:
      final_result: <% $.final_result %>

    tasks:
      task1:
        action: std.echo output=<% $.param1 %>
        publish:
          result1: <% task(task1).result %>

      task2:
        action: std.echo output="'<% $.param1 %> & <% $.param2 %>'"
        publish:
          final_result: <% task(task2).result %>
        requires: [task1]

  wf2:
    type: direct

    output:
      slogan: <% $.slogan %>

    tasks:
      task1:
        workflow: wf1 param1='Bonnie' param2='Clyde' task_name='task2'
        publish:
          slogan: "<% task(task1).result.final_result %> is a cool movie!"
"""

WB2 = """
---
version: '2.0'

name: wb2

workflows:
  wf1:
    type: direct

    tasks:
      task1:
        workflow: wf2

  wf2:
    type: direct

    output:
      var1: <% $.does_not_exist %>

    tasks:
        task1:
            action: std.noop
"""


class SubworkflowsTest(base.EngineTestCase):
    def setUp(self):
        super(SubworkflowsTest, self).setUp()

        wb_service.create_workbook_v2(WB1)
        wb_service.create_workbook_v2(WB2)

    def test_subworkflow_success(self):
        wf2_ex = self.engine.start_workflow('wb1.wf2', None)

        project_id = auth_context.ctx().project_id

        # Execution of 'wf2'.
        self.assertEqual(project_id, wf2_ex.project_id)
        self.assertIsNotNone(wf2_ex)
        self.assertDictEqual({}, wf2_ex.input)
        self.assertDictEqual({}, wf2_ex.params)

        self._await(lambda: len(db_api.get_workflow_executions()) == 2, 0.5, 5)

        wf_execs = db_api.get_workflow_executions()

        self.assertEqual(2, len(wf_execs))

        # Execution of 'wf2'.
        wf1_ex = self._assert_single_item(wf_execs, name='wb1.wf1')
        wf2_ex = self._assert_single_item(wf_execs, name='wb1.wf2')

        self.assertEqual(project_id, wf1_ex.project_id)
        self.assertIsNotNone(wf1_ex.task_execution_id)
        self.assertDictContainsSubset(
            {
                'task_name': 'task2',
                'task_execution_id': wf1_ex.task_execution_id
            },
            wf1_ex.params
        )
        self.assertDictEqual(
            {
                'param1': 'Bonnie',
                'param2': 'Clyde'
            },
            wf1_ex.input
        )

        # Wait till workflow 'wf1' is completed.
        self.await_workflow_success(wf1_ex.id)

        wf1_ex = db_api.get_workflow_execution(wf1_ex.id)

        self.assertDictEqual(
            {'final_result': "'Bonnie & Clyde'"},
            wf1_ex.output
        )

        # Wait till workflow 'wf2' is completed.
        self.await_workflow_success(wf2_ex.id, timeout=4)

        wf2_ex = db_api.get_workflow_execution(wf2_ex.id)

        self.assertDictEqual(
            {'slogan': "'Bonnie & Clyde' is a cool movie!"},
            wf2_ex.output
        )

        # Check project_id in tasks.
        wf1_task_execs = db_api.get_task_executions(
            workflow_execution_id=wf1_ex.id
        )
        wf2_task_execs = db_api.get_task_executions(
            workflow_execution_id=wf2_ex.id
        )

        wf2_task1_ex = self._assert_single_item(wf1_task_execs, name='task1')
        wf1_task1_ex = self._assert_single_item(wf2_task_execs, name='task1')
        wf1_task2_ex = self._assert_single_item(wf1_task_execs, name='task2')

        self.assertEqual(project_id, wf2_task1_ex.project_id)
        self.assertEqual(project_id, wf1_task1_ex.project_id)
        self.assertEqual(project_id, wf1_task2_ex.project_id)

    @mock.patch.object(std_actions.EchoAction, 'run',
                       mock.MagicMock(side_effect=exc.ActionException))
    def test_subworkflow_error(self):
        self.engine.start_workflow('wb1.wf2', None)

        self._await(lambda: len(db_api.get_workflow_executions()) == 2, 0.5, 5)

        wf_execs = db_api.get_workflow_executions()

        self.assertEqual(2, len(wf_execs))

        wf1_ex = self._assert_single_item(wf_execs, name='wb1.wf1')
        wf2_ex = self._assert_single_item(wf_execs, name='wb1.wf2')

        # Wait till workflow 'wf1' is completed.
        self.await_workflow_error(wf1_ex.id)

        # Wait till workflow 'wf2' is completed, its state must be ERROR.
        self.await_workflow_error(wf2_ex.id)

    def test_subworkflow_yaql_error(self):
        wf_ex = self.engine.start_workflow('wb2.wf1', None)

        self.await_workflow_error(wf_ex.id)

        wf_execs = db_api.get_workflow_executions()

        self.assertEqual(2, len(wf_execs))

        wf2_ex = self._assert_single_item(wf_execs, name='wb2.wf2')

        self.assertEqual(states.ERROR, wf2_ex.state)
        self.assertIn('Can not evaluate YAQL expression', wf2_ex.state_info)

        # Ensure error message is bubbled up to the main workflow.
        wf1_ex = self._assert_single_item(wf_execs, name='wb2.wf1')

        self.assertEqual(states.ERROR, wf1_ex.state)
        self.assertIn('Can not evaluate YAQL expression', wf1_ex.state_info)

    def test_subworkflow_environment_inheritance(self):
        env = {'key1': 'abc'}

        wf2_ex = self.engine.start_workflow('wb1.wf2', None, env=env)

        # Execution of 'wf2'.
        self.assertIsNotNone(wf2_ex)
        self.assertDictEqual({}, wf2_ex.input)
        self.assertDictEqual({'env': env}, wf2_ex.params)

        self._await(lambda: len(db_api.get_workflow_executions()) == 2, 0.5, 5)

        wf_execs = db_api.get_workflow_executions()

        self.assertEqual(2, len(wf_execs))

        # Execution of 'wf1'.
        wf1_ex = self._assert_single_item(wf_execs, name='wb1.wf1')
        wf2_ex = self._assert_single_item(wf_execs, name='wb1.wf2')

        expected_start_params = {
            'task_name': 'task2',
            'task_execution_id': wf1_ex.task_execution_id,
            'env': env
        }

        self.assertIsNotNone(wf1_ex.task_execution_id)
        self.assertDictContainsSubset(expected_start_params, wf1_ex.params)

        # Wait till workflow 'wf1' is completed.
        self.await_workflow_success(wf1_ex.id)

        # Wait till workflow 'wf2' is completed.
        self.await_workflow_success(wf2_ex.id)
