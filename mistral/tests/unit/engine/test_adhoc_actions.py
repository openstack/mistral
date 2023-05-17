# Copyright 2014 - Mirantis, Inc.
# Copyright 2020 Nokia Software.
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

from mistral_lib import actions as ml_actions

from mistral.db.v2 import api as db_api
from mistral import exceptions as exc
from mistral.services import workbooks as wb_service
from mistral.tests.unit.engine import base
from mistral.workflow import states


# Use the set_default method to set value otherwise in certain test cases
# the change in value is not permanent.
cfg.CONF.set_default('auth_enable', False, group='pecan')

WB = """
---
version: '2.0'

name: my_wb

actions:
  concat_twice:
    base: std.echo
    base-input:
      output: "<% $.s1 %>+<% $.s2 %>"
    input:
      - s1: "a"
      - s2
    output: "<% $ %> and <% $ %>"

  test_env:
    base: std.echo
    base-input:
      output: '{{ env().foo }}'

  nested_concat:
    base: my_wb.concat_twice
    base-input:
      s2: '{{ _.n2 }}'
    input:
      - n2: 'b'
    output:
      nested_concat: '{{ _ }}'

  missing_base:
    base: wrong
    input:
      - some_input

  nested_missing_base:
    base: missing_base
    input:
      - some_input

workflows:
  wf1:
    type: direct
    input:
      - str1
      - str2
    output:
      workflow_result: <% $.result %> # Access to execution context variables
      concat_task_result: <% task(concat).result %> # Same but via task name

    tasks:
      concat:
        action: concat_twice s1=<% $.str1 %> s2=<% $.str2 %>
        publish:
          result: <% task(concat).result %>

  wf2:
    type: direct
    input:
      - str1
      - str2
    output:
      workflow_result: <% $.result %> # Access to execution context variables
      concat_task_result: <% task(concat).result %> # Same but via task name

    tasks:
      concat:
        action: concat_twice s2=<% $.str2 %>
        publish:
          result: <% task(concat).result %>

  wf3:
    type: direct
    input:
      - str1
      - str2

    tasks:
      concat:
        action: concat_twice

  wf4:
    type: direct
    input:
      - str1
    output:
        workflow_result: '{{ _.printenv_result }}'

    tasks:
      printenv:
        action: test_env
        publish:
          printenv_result: '{{ task().result }}'

  wf5:
    type: direct
    output:
      workflow_result: '{{ _.nested_result }}'
    tasks:
      nested_test:
        action: nested_concat
        publish:
          nested_result: '{{ task().result }}'

  wf6:
    type: direct
    output:
      workflow_result: '{{ _.missing_result }}'
    tasks:
      missing_action:
        action: missing_base
        on-complete:
          - next_action
      next_action:
        publish:
          missing_result: 'Finished'

  wf7:
    type: direct
    output:
      workflow_result: '{{ _.missing_result }}'
    tasks:
      nested_missing_action:
        action: nested_missing_base
        on-complete:
          - next_action
      next_action:
        publish:
          missing_result: 'Finished'
"""


class AdhocActionsTest(base.EngineTestCase):
    def setUp(self):
        super(AdhocActionsTest, self).setUp()

        wb_service.create_workbook_v2(WB)

    def test_run_workflow_with_adhoc_action(self):
        wf_ex = self.engine.start_workflow(
            'my_wb.wf1',
            wf_input={'str1': 'a', 'str2': 'b'}
        )

        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            self.assertDictEqual(
                {
                    'workflow_result': 'a+b and a+b',
                    'concat_task_result': 'a+b and a+b'
                },
                wf_ex.output
            )

    def test_run_adhoc_action_without_input_value(self):
        wf_ex = self.engine.start_workflow(
            'my_wb.wf2',
            wf_input={'str1': 'a', 'str2': 'b'}
        )

        self.await_workflow_success(wf_ex.id)

        expected_output = {
            'workflow_result': 'a+b and a+b',
            'concat_task_result': 'a+b and a+b'
        }

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            self.assertDictEqual(expected_output, wf_ex.output)

    def test_run_adhoc_action_without_sufficient_input_value(self):
        wf_ex = self.engine.start_workflow(
            'my_wb.wf3',
            wf_input={'str1': 'a', 'str2': 'b'}
        )
        self.await_workflow_error(wf_ex.id)
        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
        self.assertIn("Invalid input", wf_ex.state_info)
        self.assertEqual(states.ERROR, wf_ex.state)

    def test_run_adhoc_action_with_env(self):
        wf_ex = self.engine.start_workflow(
            'my_wb.wf4',
            wf_input={'str1': 'a'},
            env={'foo': 'bar'}
        )

        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            self.assertDictEqual(
                {
                    'workflow_result': 'bar'
                },
                wf_ex.output
            )

    def test_run_nested_adhoc_with_output(self):
        wf_ex = self.engine.start_workflow('my_wb.wf5')

        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            self.assertDictEqual(
                {
                    'workflow_result': {'nested_concat': 'a+b and a+b'}
                },
                wf_ex.output
            )

    def test_missing_adhoc_action_definition(self):
        wf_ex = self.engine.start_workflow('my_wb.wf6')

        self.await_workflow_error(wf_ex.id)

        with db_api.transaction():
            # Note: We need to reread execution to access related tasks.
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            tasks = wf_ex.task_executions

            task1 = self._assert_single_item(tasks, name='missing_action')

        self.assertEqual(states.ERROR, task1.state)

    def test_nested_missing_adhoc_action_definition(self):
        wf_ex = self.engine.start_workflow('my_wb.wf7')

        self.await_workflow_error(wf_ex.id)

        with db_api.transaction():
            # Note: We need to reread execution to access related tasks.
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            tasks = wf_ex.task_executions

            task1 = self._assert_single_item(
                tasks,
                name='nested_missing_action'
            )

        self.assertEqual(states.ERROR, task1.state)

    def test_adhoc_async_action(self):
        wb_text = """---
        version: '2.0'

        name: my_wb1

        actions:
          my_action:
            input:
              - my_param

            base: std.async_noop
            output: (((<% $ %>)))

        workflows:
          my_wf:
            tasks:
              task1:
                action: my_action my_param="asdfasdf"
        """

        wb_service.create_workbook_v2(wb_text)

        wf_ex = self.engine.start_workflow('my_wb1.my_wf')

        self.await_workflow_running(wf_ex.id, timeout=4)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
            wf_ex_id = wf_ex.id
            task_execs = wf_ex.task_executions
            task1_ex = task_execs[0]
        self.engine.start_task(task1_ex.id, True, False, None, False, False)
        action_execs = db_api.get_action_executions(
            task_execution_id=task1_ex.id
        )
        a_ex_id = action_execs[0].id

        self.engine.on_action_complete(a_ex_id, ml_actions.Result(data='Hi!'))

        self.await_action_success(a_ex_id)
        self.await_workflow_success(wf_ex_id)

        with db_api.transaction(read_only=True):
            a_ex = db_api.get_action_execution(a_ex_id)

            self.assertEqual('(((Hi!)))', a_ex.output.get('result'))

    def test_adhoc_action_definition_with_namespace(self):
        namespace1 = 'ad-hoc_test'
        namespace2 = 'ad-hoc_test2'

        wb_text = """---

        version: '2.0'

        name: my_wb1

        actions:
          test_env:
            base: std.echo
            base-input:
              output: '{{ env().foo }}' # TODO(rakhmerov): It won't work.

        workflows:
          wf:
            input:
              - str1
            output:
                workflow_result: '{{ _.printenv_result }}'

            tasks:
              printenv:
                action: test_env
                publish:
                  printenv_result: '{{ task().result }}'
        """

        wb_service.create_workbook_v2(wb_text, namespace=namespace1)
        wb_service.create_workbook_v2(wb_text, namespace=namespace2)

        with db_api.transaction():
            action_defs = db_api.get_action_definitions(
                name='my_wb1.test_env'
            )

            self.assertEqual(2, len(action_defs))

            action_defs = db_api.get_action_definitions(
                name='my_wb1.test_env',
                namespace=namespace1
            )

            self.assertEqual(1, len(action_defs))

            action_defs = db_api.get_action_definitions(
                name='my_wb1.test_env',
                namespace=namespace2
            )

            self.assertEqual(1, len(action_defs))

            self.assertRaises(
                exc.DBEntityNotFoundError,
                db_api.get_action_definition,
                name='my_wb1.test_env'
            )

    def test_adhoc_action_execution_with_namespace(self):
        namespace = 'ad-hoc_test'

        wb_service.create_workbook_v2(WB, namespace=namespace)

        wf_ex = self.engine.start_workflow(
            'my_wb.wf4',
            wf_input={'str1': 'a'},
            env={'foo': 'bar'},
            wf_namespace=namespace
        )

        self.await_workflow_success(wf_ex.id, timeout=5)

        with db_api.transaction():
            action_execs = db_api.get_action_executions(
                name='my_wb.test_env',
                workflow_namespace=namespace
            )

            self.assertEqual(1, len(action_execs))

            self.assertEqual(namespace, action_execs[0].workflow_namespace)

    def test_adhoc_action_runtime_context_name(self):
        wf_ex = self.engine.start_workflow(
            'my_wb.wf4',
            wf_input={'str1': 'a'},
            env={'foo': 'bar'}
        )

        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            action_execs = db_api.get_action_executions(name='my_wb.test_env')

            self.assertEqual(1, len(action_execs))
