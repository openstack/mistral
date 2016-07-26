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

from oslo_config import cfg

from mistral.db.v2 import api as db_api
from mistral import exceptions as exc
from mistral.services import workbooks as wb_service
from mistral.services import workflows as wf_service
from mistral.tests.unit.engine import base
from mistral.workflow import states


# Use the set_default method to set value otherwise in certain test cases
# the change in value is not permanent.
cfg.CONF.set_default('auth_enable', False, group='pecan')


WORKBOOK = """
---
version: '2.0'

name: my_wb

workflows:
  wf1:
    type: reverse
    input:
      - param1
      - param2

    tasks:
      task1:
        action: std.echo output=<% $.param1 %>
        publish:
          result1: <% task(task1).result %>

      task2:
        action: std.echo output="<% $.result1 %> & <% $.param2 %>"
        publish:
          result2: <% task(task2).result %>
        requires: [task1]

      task3:
        action: std.noop

      task4:
        action: std.noop
        requires: task3
"""


class ReverseWorkflowEngineTest(base.EngineTestCase):
    def setUp(self):
        super(ReverseWorkflowEngineTest, self).setUp()

        wb_service.create_workbook_v2(WORKBOOK)

    def test_start_task1(self):
        wf_input = {'param1': 'a', 'param2': 'b'}

        wf_ex = self.engine.start_workflow(
            'my_wb.wf1',
            wf_input,
            task_name='task1'
        )

        # Execution 1.
        self.assertIsNotNone(wf_ex)
        self.assertDictEqual(wf_input, wf_ex.input)
        self.assertDictEqual({'task_name': 'task1'}, wf_ex.params)

        # Wait till workflow 'wf1' is completed.
        self.await_workflow_success(wf_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(1, len(wf_ex.task_executions))
        self.assertEqual(1, len(db_api.get_task_executions()))

        task_ex = self._assert_single_item(
            wf_ex.task_executions,
            name='task1',
            state=states.SUCCESS
        )

        self.assertDictEqual({'result1': 'a'}, task_ex.published)

    def test_start_task2(self):
        wf_input = {'param1': 'a', 'param2': 'b'}

        wf_ex = self.engine.start_workflow(
            'my_wb.wf1',
            wf_input,
            task_name='task2'
        )

        # Execution 1.
        self.assertIsNotNone(wf_ex)
        self.assertDictEqual(wf_input, wf_ex.input)
        self.assertDictEqual({'task_name': 'task2'}, wf_ex.params)

        # Wait till workflow 'wf1' is completed.
        self.await_workflow_success(wf_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(2, len(wf_ex.task_executions))
        self.assertEqual(2, len(db_api.get_task_executions()))

        task1_ex = self._assert_single_item(
            wf_ex.task_executions,
            name='task1',
            state=states.SUCCESS
        )

        self.assertDictEqual({'result1': 'a'}, task1_ex.published)

        task2_ex = self._assert_single_item(
            wf_ex.task_executions,
            name='task2',
            state=states.SUCCESS
        )

        self.assertDictEqual({'result2': 'a & b'}, task2_ex.published)

    def test_one_line_requires_syntax(self):
        wf_input = {'param1': 'a', 'param2': 'b'}

        wf_ex = self.engine.start_workflow(
            'my_wb.wf1',
            wf_input,
            task_name='task4'
        )

        self.await_workflow_success(wf_ex.id)

        tasks = db_api.get_task_executions()

        self.assertEqual(2, len(tasks))

        self._assert_single_item(tasks, name='task4', state=states.SUCCESS)
        self._assert_single_item(tasks, name='task3', state=states.SUCCESS)

    def test_inconsistent_task_names(self):
        wf_text = """
        version: '2.0'

        wf:
          type: reverse

          tasks:
            task2:
              action: std.noop

            task3:
              action: std.noop
              requires: [task1]
        """

        exception = self.assertRaises(
            exc.InvalidModelException,
            wf_service.create_workflows,
            wf_text
        )

        self.assertIn("Task 'task1' not found", exception.message)
