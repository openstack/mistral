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
from mistral.services import workflows as wf_service
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

WB3 = """
---
version: '2.0'

name: wb3

workflows:
  wf1:
    input:
      - wf_name
    output:
      sub_wf_out: <% $.sub_wf_out %>

    tasks:
      task1:
        workflow: <% $.wf_name %>
        publish:
          sub_wf_out: <% task(task1).result.sub_wf_out %>

  wf2:
    output:
      sub_wf_out: wf2_out

    tasks:
        task1:
            action: std.noop
"""

WB4 = """
---
version: '2.0'

name: wb4

workflows:
  wf1:
    input:
      - wf_name
      - inp
    output:
      sub_wf_out: <% $.sub_wf_out %>

    tasks:
      task1:
        workflow: <% $.wf_name %>
        input: <% $.inp %>
        publish:
          sub_wf_out: <% task(task1).result.sub_wf_out %>

  wf2:
    input:
      - inp
    output:
      sub_wf_out: <% $.inp %>

    tasks:
        task1:
            action: std.noop

"""

WB5 = """
---
version: '2.0'

name: wb5

workflows:
  wf1:
    input:
      - wf_name
      - inp
    output:
      sub_wf_out: '{{ _.sub_wf_out }}'

    tasks:
      task1:
        workflow: '{{ _.wf_name }}'
        input: '{{ _.inp }}'
        publish:
          sub_wf_out: '{{ task("task1").result.sub_wf_out }}'

  wf2:
    input:
      - inp
    output:
      sub_wf_out: '{{ _.inp }}'

    tasks:
        task1:
            action: std.noop
"""

WB6 = """
---
version: '2.0'

name: wb6

workflows:
  wf1:
    tasks:
      task1:
        workflow: wf2

  wf2:
    tasks:
      task1:
        workflow: wf3

  wf3:
    tasks:
      task1:
        action: std.noop
"""


class SubworkflowsTest(base.EngineTestCase):
    def setUp(self):
        super(SubworkflowsTest, self).setUp()

        wb_service.create_workbook_v2(WB1)
        wb_service.create_workbook_v2(WB2)
        wb_service.create_workbook_v2(WB3)
        wb_service.create_workbook_v2(WB4)
        wb_service.create_workbook_v2(WB5)
        wb_service.create_workbook_v2(WB6)

    def test_subworkflow_success(self):
        wf2_ex = self.engine.start_workflow('wb1.wf2')

        project_id = auth_context.ctx().project_id

        # Execution of 'wf2'.
        self.assertEqual(project_id, wf2_ex.project_id)
        self.assertIsNotNone(wf2_ex)
        self.assertDictEqual({}, wf2_ex.input)
        self.assertDictEqual({'namespace': '', 'env': {}}, wf2_ex.params)

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

        with db_api.transaction():
            wf1_ex = db_api.get_workflow_execution(wf1_ex.id)

            wf1_output = wf1_ex.output

        self.assertDictEqual(
            {'final_result': "'Bonnie & Clyde'"},
            wf1_output
        )

        # Wait till workflow 'wf2' is completed.
        self.await_workflow_success(wf2_ex.id, timeout=4)

        with db_api.transaction():
            wf2_ex = db_api.get_workflow_execution(wf2_ex.id)

            wf2_output = wf2_ex.output

        self.assertDictEqual(
            {'slogan': "'Bonnie & Clyde' is a cool movie!"},
            wf2_output
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
        self.engine.start_workflow('wb1.wf2')

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
        wf_ex = self.engine.start_workflow('wb2.wf1')

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

        wf2_ex = self.engine.start_workflow('wb1.wf2', env=env)

        # Execution of 'wf2'.
        self.assertIsNotNone(wf2_ex)
        self.assertDictEqual({}, wf2_ex.input)
        self.assertDictEqual(
            {'env': env, 'namespace': ''},
            wf2_ex.params
        )

        self._await(lambda: len(db_api.get_workflow_executions()) == 2, 0.5, 5)

        wf_execs = db_api.get_workflow_executions()

        self.assertEqual(2, len(wf_execs))

        # Execution of 'wf1'.
        wf1_ex = self._assert_single_item(wf_execs, name='wb1.wf1')
        wf2_ex = self._assert_single_item(wf_execs, name='wb1.wf2')

        self.assertIsNotNone(wf1_ex.task_execution_id)
        self.assertDictContainsSubset({}, wf1_ex.params)

        # Wait till workflow 'wf1' is completed.
        self.await_workflow_success(wf1_ex.id)

        # Wait till workflow 'wf2' is completed.
        self.await_workflow_success(wf2_ex.id)

    def test_dynamic_subworkflow_wf2(self):
        ex = self.engine.start_workflow('wb3.wf1', wf_input={'wf_name': 'wf2'})

        self.await_workflow_success(ex.id)

        with db_api.transaction():
            ex = db_api.get_workflow_execution(ex.id)
            self.assertEqual({'sub_wf_out': 'wf2_out'}, ex.output)

    def test_dynamic_subworkflow_call_failure(self):
        ex = self.engine.start_workflow(
            'wb3.wf1',
            wf_input={'wf_name': 'not_existing_wf'}
        )

        self.await_workflow_error(ex.id)

        with db_api.transaction():
            ex = db_api.get_workflow_execution(ex.id)

            self.assertIn('not_existing_wf', ex.state_info)

    def test_dynamic_subworkflow_with_generic_input(self):
        self._test_dynamic_workflow_with_dict_param('wb4.wf1')

    def test_dynamic_subworkflow_with_jinja(self):
        self._test_dynamic_workflow_with_dict_param('wb5.wf1')

    def test_string_workflow_input_failure(self):
        ex = self.engine.start_workflow(
            'wb4.wf1',
            wf_input={'wf_name': 'wf2', 'inp': 'invalid_string_input'}
        )

        self.await_workflow_error(ex.id)

        with db_api.transaction():
            ex = db_api.get_workflow_execution(ex.id)

            self.assertIn('invalid_string_input', ex.state_info)

    def _test_dynamic_workflow_with_dict_param(self, wf_identifier):
        ex = self.engine.start_workflow(
            wf_identifier,
            wf_input={'wf_name': 'wf2', 'inp': {'inp': 'abc'}}
        )

        self.await_workflow_success(ex.id)

        with db_api.transaction():
            ex = db_api.get_workflow_execution(ex.id)

            self.assertEqual({'sub_wf_out': 'abc'}, ex.output)

    def test_subworkflow_root_execution_id(self):
        self.engine.start_workflow('wb6.wf1')

        self._await(lambda: len(db_api.get_workflow_executions()) == 3, 0.5, 5)

        wf_execs = db_api.get_workflow_executions()

        wf1_ex = self._assert_single_item(wf_execs, name='wb6.wf1')
        wf2_ex = self._assert_single_item(wf_execs, name='wb6.wf2')
        wf3_ex = self._assert_single_item(wf_execs, name='wb6.wf3')

        self.assertEqual(3, len(wf_execs))

        # Wait till workflow 'wf1' is completed (and all the sub-workflows
        # will be completed also).
        self.await_workflow_success(wf1_ex.id)

        with db_api.transaction():
            wf1_ex = db_api.get_workflow_execution(wf1_ex.id)
            wf2_ex = db_api.get_workflow_execution(wf2_ex.id)
            wf3_ex = db_api.get_workflow_execution(wf3_ex.id)

            self.assertIsNone(wf1_ex.root_execution_id, None)
            self.assertEqual(wf2_ex.root_execution_id, wf1_ex.id)
            self.assertEqual(wf2_ex.root_execution, wf1_ex)
            self.assertEqual(wf3_ex.root_execution_id, wf1_ex.id)
            self.assertEqual(wf3_ex.root_execution, wf1_ex)

    def test_cascade_delete(self):
        wf_text = """
        version: 2.0

        wf:
          tasks:
            task1:
              workflow: sub_wf1

            task2:
              workflow: sub_wf2

        sub_wf1:
          tasks:
            task1:
              action: std.noop

        sub_wf2:
          tasks:
            task1:
              action: std.noop
        """

        wf_service.create_workflows(wf_text)

        wf_ex = self.engine.start_workflow('wf')

        self.await_workflow_success(wf_ex.id)

        self.assertEqual(3, len(db_api.get_workflow_executions()))
        self.assertEqual(4, len(db_api.get_task_executions()))
        self.assertEqual(2, len(db_api.get_action_executions()))

        # Now delete the root workflow execution and make sure that
        # all dependent objects are deleted as well.
        db_api.delete_workflow_execution(wf_ex.id)

        self.assertEqual(0, len(db_api.get_workflow_executions()))
        self.assertEqual(0, len(db_api.get_task_executions()))
        self.assertEqual(0, len(db_api.get_action_executions()))
