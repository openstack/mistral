# Modified in 2025 by NetCracker Technology Corp.
#
#     Licensed under the Apache License, Version 2.0 (the "License");
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


class TestSafeInput(base.EngineTestCase):

    def test_safe_input_false(self):
        wf_text = """---
        version: '2.0'
        wf:
          tasks:
            task1:
              input:
                url: <% $.ItWillBeError %>
              action: std.http
              safe-input: false
              on-error: task2
            task2:
              action: std.noop
        """

        wf_service.create_workflows(wf_text)
        wf_ex = self.engine.start_workflow('wf')

        self.await_workflow_error(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
            tasks = wf_ex.task_executions

        self.assertEqual(len(tasks), 1)
        task1 = self._assert_single_item(tasks, name='task1')
        self.assertEqual(task1.state, states.ERROR)

    def test_safe_input_true(self):
        wf_text = """---
        version: '2.0'
        wf:
          tasks:
            task1:
              input:
                url: <% $.ItWillBeError %>
              action: std.http
              safe-input: true
              on-error: task2
            task2:
              action: std.noop
        """

        wf_service.create_workflows(wf_text)
        wf_ex = self.engine.start_workflow('wf')

        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
            tasks = wf_ex.task_executions

        self.assertEqual(len(tasks), 2)

        task1 = self._assert_single_item(tasks, name='task1')
        task2 = self._assert_single_item(tasks, name='task2')

        self.assertEqual(task1.state, states.ERROR)
        self.assertEqual(task2.state, states.SUCCESS)

    def test_safe_input_in_task_defaults(self):
        wf_text = """---
            version: '2.0'
            wf:
              task-defaults:
                safe-input: true
              tasks:
                task1:
                  action: std.http
                  input:
                    url: <% $.ItWillBeError %>
                  on-error:
                    - task2
                task2:
                  action: std.http
                  input:
                    url: <% $.ItWillBeError %>
                  safe-input: false
                  on-error:
                    - task3
                task3:
                  action: std.noop
            """

        wf_service.create_workflows(wf_text)
        wf_ex = self.engine.start_workflow('wf')

        self.await_workflow_error(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
            tasks = wf_ex.task_executions

        self.assertEqual(len(tasks), 2)

        task1 = self._assert_single_item(tasks, name='task1')
        task2 = self._assert_single_item(tasks, name='task2')

        self.assertEqual(task1.state, states.ERROR)
        self.assertEqual(task2.state, states.ERROR)

    def test_default_value_of_safe_input(self):
        wf_text = """---
        version: '2.0'
        wf:
          tasks:
            task1:
              input:
                url: <% $.ItWillBeError %>
              action: std.http
              on-error: task2
            task2:
              action: std.noop
        """

        wf_service.create_workflows(wf_text)
        wf_ex = self.engine.start_workflow('wf')

        self.await_workflow_error(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
            tasks = wf_ex.task_executions

        self.assertEqual(len(tasks), 1)
        task1 = self._assert_single_item(tasks, name='task1')
        self.assertEqual(task1.state, states.ERROR)
