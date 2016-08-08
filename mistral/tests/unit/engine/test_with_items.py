# Copyright 2015 - Mirantis, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

import copy
from oslo_config import cfg
import testtools

from mistral.actions import base as action_base
from mistral.db.v2 import api as db_api
from mistral import exceptions as exc
from mistral.services import workbooks as wb_service
from mistral.services import workflows as wf_service
from mistral.tests.unit import base as test_base
from mistral.tests.unit.engine import base
from mistral import utils
from mistral.workflow import data_flow
from mistral.workflow import states
from mistral.workflow import utils as wf_utils

# TODO(nmakhotkin) Need to write more tests.

# Use the set_default method to set value otherwise in certain test cases
# the change in value is not permanent.
cfg.CONF.set_default('auth_enable', False, group='pecan')

WB = """
---
version: "2.0"

name: wb1

workflows:
  with_items:
    type: direct

    input:
     - names_info

    tasks:
      task1:
        with-items: name_info in <% $.names_info %>
        action: std.echo output=<% $.name_info.name %>
        publish:
          result: <% task(task1).result[0] %>

"""

WB_WITH_STATIC_VAR = """
---
version: "2.0"

name: wb1

workflows:
  with_items:
    type: direct

    input:
     - names_info
     - greeting

    tasks:
      task1:
        with-items: name_info in <% $.names_info %>
        action: std.echo output="<% $.greeting %>, <% $.name_info.name %>!"
        publish:
          result: <% task(task1).result %>
"""


WB_MULTI_ARRAY = """
---
version: "2.0"

name: wb1

workflows:
  with_items:
    type: direct

    input:
     - arrayI
     - arrayJ

    tasks:
      task1:
        with-items:
          - itemX in <% $.arrayI %>
          - itemY in <% $.arrayJ %>
        action: std.echo output="<% $.itemX %> <% $.itemY %>"
        publish:
          result: <% task(task1).result %>

"""


WB_ACTION_CONTEXT = """
---
version: "2.0"

name: wb1

workflows:
  wf1_with_items:
    type: direct

    input:
      - links

    tasks:
      task1:
        with-items: link in <% $.links %>
        action: std.http url=<% $.link %>
        publish:
          result: <% task(task1) %>
"""


WF_INPUT = {
    'names_info': [
        {'name': 'John'},
        {'name': 'Ivan'},
        {'name': 'Mistral'}
    ]
}


WF_INPUT_URLS = {
    'links': [
        'http://google.com',
        'http://openstack.org',
        'http://google.com'
    ]
}

WF_INPUT_ONE_ITEM = {
    'names_info': [
        {'name': 'Guy'}
    ]
}


class RandomSleepEchoAction(action_base.Action):
    def __init__(self, output):
        self.output = output

    def run(self):
        utils.random_sleep(1)

        return self.output

    def test(self):
        utils.random_sleep(1)


class WithItemsEngineTest(base.EngineTestCase):
    def assert_capacity(self, capacity, task_ex):
        self.assertEqual(
            capacity,
            task_ex.runtime_context['with_items_context']['capacity']
        )

    @staticmethod
    def get_incomplete_action_ex(task_ex):
        return [ex for ex in task_ex.executions if not ex.accepted][0]

    @staticmethod
    def get_running_action_exs_number(task_ex):
        return len([ex for ex in task_ex.executions
                   if ex.state == states.RUNNING])

    def test_with_items_simple(self):
        wb_service.create_workbook_v2(WB)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wb1.with_items', WF_INPUT)

        self.await_workflow_success(wf_ex.id)

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        task_execs = wf_ex.task_executions

        task1_ex = self._assert_single_item(task_execs, name='task1')

        with_items_ctx = task1_ex.runtime_context['with_items_context']

        self.assertEqual(3, with_items_ctx['count'])

        # Since we know that we can receive results in random order,
        # check is not depend on order of items.
        with db_api.transaction():
            task1_ex = db_api.get_task_execution(task1_ex.id)

            result = data_flow.get_task_execution_result(task1_ex)

        self.assertIsInstance(result, list)

        self.assertIn('John', result)
        self.assertIn('Ivan', result)
        self.assertIn('Mistral', result)

        published = task1_ex.published

        self.assertIn(published['result'], ['John', 'Ivan', 'Mistral'])

        self.assertEqual(1, len(task_execs))
        self.assertEqual(states.SUCCESS, task1_ex.state)

    def test_with_items_fail(self):
        wf_text = """---
        version: "2.0"

        with_items:
          type: direct

          tasks:
            task1:
              with-items: i in [1, 2, 3]
              action: std.fail
              on-error: task2

            task2:
              action: std.echo output="With-items failed"
        """

        wf_service.create_workflows(wf_text)

        # Start workflow.
        wf_ex = self.engine.start_workflow('with_items', {})

        self.await_workflow_success(wf_ex.id)

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(2, len(wf_ex.task_executions))

    def test_with_items_yaql_fail(self):
        wf_text = """---
        version: "2.0"

        with_items:
          type: direct

          tasks:
            task1:
              with-items: i in <% $.foobar %>
              action: std.noop
        """

        wf_service.create_workflows(wf_text)

        # Start workflow.
        wf_ex = self.engine.start_workflow('with_items', {})

        self.await_workflow_error(wf_ex.id)

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        tasks = wf_ex.task_executions
        task1 = self._assert_single_item(tasks, name='task1')

        with db_api.transaction():
            task1 = db_api.get_task_execution(task1.id)

            result = data_flow.get_task_execution_result(task1)

        self.assertEqual(states.ERROR, task1.state)
        self.assertIsInstance(result, list)
        self.assertListEqual(result, [])

    def test_with_items_sub_workflow_fail(self):
        wb_text = """---
        version: "2.0"

        name: wb1

        workflows:
          with_items:
            type: direct

            tasks:
              task1:
                with-items: i in [1, 2, 3]
                workflow: subworkflow
                on-error: task2

              task2:
                action: std.echo output="With-items failed"

          subworkflow:
            type: direct

            tasks:
              fail:
                action: std.fail
        """

        wb_service.create_workbook_v2(wb_text)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wb1.with_items', {})

        self.await_workflow_success(wf_ex.id)

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(2, len(wf_ex.task_executions))

    def test_with_items_static_var(self):
        wb_service.create_workbook_v2(WB_WITH_STATIC_VAR)

        wf_input = copy.deepcopy(WF_INPUT)
        wf_input.update({'greeting': 'Hello'})

        # Start workflow.
        wf_ex = self.engine.start_workflow('wb1.with_items', wf_input)

        self.await_workflow_success(wf_ex.id)

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        tasks = wf_ex.task_executions
        task1 = self._assert_single_item(tasks, name='task1')

        with db_api.transaction():
            task1 = db_api.get_task_execution(task1.id)

            result = data_flow.get_task_execution_result(task1)

        self.assertIsInstance(result, list)

        self.assertIn('Hello, John!', result)
        self.assertIn('Hello, Ivan!', result)
        self.assertIn('Hello, Mistral!', result)

        self.assertEqual(1, len(tasks))
        self.assertEqual(states.SUCCESS, task1.state)

    def test_with_items_multi_array(self):
        wb_service.create_workbook_v2(WB_MULTI_ARRAY)

        wf_input = {'arrayI': ['a', 'b', 'c'], 'arrayJ': [1, 2, 3]}

        # Start workflow.
        wf_ex = self.engine.start_workflow('wb1.with_items', wf_input)

        self.await_workflow_success(wf_ex.id)

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        task_execs = wf_ex.task_executions

        task1_ex = self._assert_single_item(task_execs, name='task1')

        # Since we know that we can receive results in random order,
        # check is not depend on order of items.
        with db_api.transaction():
            task1_ex = db_api.get_task_execution(task1_ex.id)

            result = data_flow.get_task_execution_result(task1_ex)

        self.assertIsInstance(result, list)

        self.assertIn('a 1', result)
        self.assertIn('b 2', result)
        self.assertIn('c 3', result)

        self.assertEqual(1, len(task_execs))
        self.assertEqual(states.SUCCESS, task1_ex.state)

    def test_with_items_action_context(self):
        wb_service.create_workbook_v2(WB_ACTION_CONTEXT)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wb1.wf1_with_items', WF_INPUT_URLS)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)
        task_ex = wf_ex.task_executions[0]

        act_exs = task_ex.executions

        self.engine.on_action_complete(act_exs[0].id, wf_utils.Result("Ivan"))
        self.engine.on_action_complete(act_exs[1].id, wf_utils.Result("John"))
        self.engine.on_action_complete(
            act_exs[2].id,
            wf_utils.Result("Mistral")
        )

        self.await_workflow_success(wf_ex.id)

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        task_ex = db_api.get_task_execution(task_ex.id)
        result = data_flow.get_task_execution_result(task_ex)

        self.assertIsInstance(result, list)

        self.assertIn('John', result)
        self.assertIn('Ivan', result)
        self.assertIn('Mistral', result)

        self.assertEqual(states.SUCCESS, task_ex.state)

    def test_with_items_empty_list(self):
        wb_text = """---
        version: "2.0"

        name: wb1

        workflows:
          with_items:
            type: direct

            input:
             - names_info

            tasks:
              task1:
                with-items: name_info in <% $.names_info %>
                action: std.echo output=<% $.name_info.name %>
                on-success:
                  - task2

              task2:
                action: std.echo output="Hi!"
        """

        wb_service.create_workbook_v2(wb_text)

        # Start workflow.
        wf_input = {'names_info': []}
        wf_ex = self.engine.start_workflow('wb1.with_items', wf_input)

        self.await_workflow_success(wf_ex.id)

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        task_execs = wf_ex.task_executions

        task1_ex = self._assert_single_item(task_execs, name='task1')
        task2_ex = self._assert_single_item(task_execs, name='task2')

        self.assertEqual(2, len(task_execs))
        self.assertEqual(states.SUCCESS, task1_ex.state)
        self.assertEqual(states.SUCCESS, task2_ex.state)

    def test_with_items_plain_list(self):
        wb_text = """---
        version: "2.0"

        name: wb1

        workflows:
          with_items:
            type: direct

            tasks:
              task1:
                with-items: i in [1, 2, 3]
                action: std.echo output=<% $.i %>
        """

        wb_service.create_workbook_v2(wb_text)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wb1.with_items', {})

        self.await_workflow_success(wf_ex.id)

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        task1_ex = self._assert_single_item(
            wf_ex.task_executions,
            name='task1',
            state=states.SUCCESS
        )

        with db_api.transaction():
            task1_ex = db_api.get_task_execution(task1_ex.id)

            result = data_flow.get_task_execution_result(task1_ex)

        # Since we know that we can receive results in random order,
        # check is not depend on order of items.
        self.assertIn(1, result)
        self.assertIn(2, result)
        self.assertIn(3, result)

    def test_with_items_plain_list_wrong(self):
        wb_text = """---
        version: "2.0"

        name: wb1

        workflows:
          with_items:
            type: direct

            tasks:
              task1:
                with-items: i in [1,,3]
                action: std.echo output=<% $.i %>

        """

        exception = self.assertRaises(
            exc.InvalidModelException,
            wb_service.create_workbook_v2, wb_text
        )

        self.assertIn("Invalid array in 'with-items'", exception.message)

    def test_with_items_results_order(self):
        wb_text = """---
        version: "2.0"

        name: wb1

        workflows:
          with_items:
            type: direct

            tasks:
              task1:
                with-items: i in [1, 2, 3]
                action: sleep_echo output=<% $.i %>
                publish:
                  one_two_three: <% task(task1).result %>
        """
        # Register random sleep action in the DB.
        test_base.register_action_class('sleep_echo', RandomSleepEchoAction)

        wb_service.create_workbook_v2(wb_text)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wb1.with_items', {})

        self.await_workflow_success(wf_ex.id)

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        task1_ex = self._assert_single_item(
            wf_ex.task_executions,
            name='task1',
            state=states.SUCCESS
        )

        published = task1_ex.published

        # Now we can check order of results explicitly.
        self.assertEqual([1, 2, 3], published['one_two_three'])

    def test_with_items_results_one_item_as_list(self):
        wb_service.create_workbook_v2(WB)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wb1.with_items', WF_INPUT_ONE_ITEM)

        self.await_workflow_success(wf_ex.id)

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        task_execs = wf_ex.task_executions

        self.assertEqual(1, len(task_execs))

        task1_ex = self._assert_single_item(
            task_execs,
            name='task1',
            state=states.SUCCESS
        )

        with db_api.transaction():
            task1_ex = db_api.get_task_execution(task1_ex.id)

            result = data_flow.get_task_execution_result(task1_ex)

        self.assertIsInstance(result, list)
        self.assertIn('Guy', result)

        self.assertIn(task1_ex.published['result'], ['Guy'])

    @testtools.skip('Restore concurrency support.')
    def test_with_items_concurrency_1(self):
        wf_with_concurrency_1 = """---
        version: "2.0"

        concurrency_test:
          type: direct

          input:
           - names: ["John", "Ivan", "Mistral"]

          tasks:
            task1:
              action: std.async_noop
              with-items: name in <% $.names %>
              concurrency: 1
        """

        wf_service.create_workflows(wf_with_concurrency_1)

        # Start workflow.
        wf_ex = self.engine.start_workflow('concurrency_test', {})

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        task_ex = wf_ex.task_executions[0]
        task_ex = db_api.get_task_execution(task_ex.id)

        self.assert_capacity(0, task_ex)
        self.assertEqual(1, self.get_running_action_exs_number(task_ex))

        # 1st iteration complete.
        self.engine.on_action_complete(
            self.get_incomplete_action_ex(task_ex).id,
            wf_utils.Result("John")
        )

        task_ex = db_api.get_task_execution(task_ex.id)

        self.assert_capacity(0, task_ex)
        self.assertEqual(1, self.get_running_action_exs_number(task_ex))

        # 2nd iteration complete.
        self.engine.on_action_complete(
            self.get_incomplete_action_ex(task_ex).id,
            wf_utils.Result("Ivan")
        )

        task_ex = db_api.get_task_execution(task_ex.id)

        self.assert_capacity(0, task_ex)
        self.assertEqual(1, self.get_running_action_exs_number(task_ex))

        # 3rd iteration complete.
        self.engine.on_action_complete(
            self.get_incomplete_action_ex(task_ex).id,
            wf_utils.Result("Mistral")
        )

        task_ex = db_api.get_task_execution(task_ex.id)

        self.assert_capacity(1, task_ex)

        self.await_workflow_success(wf_ex.id)

        # Since we know that we can receive results in random order,
        # check is not depend on order of items.
        with db_api.transaction():
            task_ex = db_api.get_task_execution(task_ex.id)

            result = data_flow.get_task_execution_result(task_ex)

        self.assertIsInstance(result, list)

        self.assertIn('John', result)
        self.assertIn('Ivan', result)
        self.assertIn('Mistral', result)

        self.assertEqual(states.SUCCESS, task_ex.state)

    @testtools.skip('Restore concurrency support.')
    def test_with_items_concurrency_yaql(self):
        wf_with_concurrency_yaql = """---
        version: "2.0"

        concurrency_test:
          type: direct

          input:
           - names: ["John", "Ivan", "Mistral"]
           - concurrency

          tasks:
            task1:
              action: std.echo output=<% $.name %>
              with-items: name in <% $.names %>
              concurrency: <% $.concurrency %>
        """

        wf_service.create_workflows(wf_with_concurrency_yaql)

        # Start workflow.
        wf_ex = self.engine.start_workflow(
            'concurrency_test',
            {'concurrency': 2}
        )

        self.await_workflow_success(wf_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        task_ex = wf_ex.task_executions[0]

        self.assertEqual(states.SUCCESS, task_ex.state)

        # Since we know that we can receive results in random order,
        # check is not depend on order of items.
        with db_api.transaction():
            task_ex = db_api.get_task_execution(task_ex.id)

            result = data_flow.get_task_execution_result(task_ex)

        self.assertIsInstance(result, list)

        self.assertIn('John', result)
        self.assertIn('Ivan', result)
        self.assertIn('Mistral', result)

    @testtools.skip('Restore concurrency support.')
    def test_with_items_concurrency_yaql_wrong_type(self):
        wf_with_concurrency_yaql = """---
        version: "2.0"

        concurrency_test:
          type: direct

          input:
           - names: ["John", "Ivan", "Mistral"]
           - concurrency

          tasks:
            task1:
              action: std.echo output=<% $.name %>
              with-items: name in <% $.names %>
              concurrency: <% $.concurrency %>
        """

        wf_service.create_workflows(wf_with_concurrency_yaql)

        # Start workflow.
        wf_ex = self.engine.start_workflow(
            'concurrency_test',
            {'concurrency': '2'}
        )

        self.assertIn(
            'Invalid data type in ConcurrencyPolicy',
            wf_ex.state_info
        )
        self.assertEqual(states.ERROR, wf_ex.state)

    @testtools.skip('Restore concurrency support.')
    def test_with_items_concurrency_2(self):
        wf_with_concurrency_2 = """---
        version: "2.0"

        concurrency_test:
          type: direct

          input:
           - names: ["John", "Ivan", "Mistral", "Hello"]

          tasks:
            task1:
              action: std.async_noop
              with-items: name in <% $.names %>
              concurrency: 2

        """
        wf_service.create_workflows(wf_with_concurrency_2)

        # Start workflow.
        wf_ex = self.engine.start_workflow('concurrency_test', {})

        wf_ex = db_api.get_workflow_execution(wf_ex.id)
        task_ex = wf_ex.task_executions[0]

        self.assert_capacity(0, task_ex)
        self.assertEqual(2, self.get_running_action_exs_number(task_ex))

        # 1st iteration complete.
        self.engine.on_action_complete(
            self.get_incomplete_action_ex(task_ex).id,
            wf_utils.Result("John")
        )

        task_ex = db_api.get_task_execution(task_ex.id)

        self.assert_capacity(0, task_ex)
        self.assertEqual(2, self.get_running_action_exs_number(task_ex))

        # 2nd iteration complete.
        self.engine.on_action_complete(
            self.get_incomplete_action_ex(task_ex).id,
            wf_utils.Result("Ivan")
        )

        task_ex = db_api.get_task_execution(task_ex.id)

        self.assert_capacity(0, task_ex)
        self.assertEqual(2, self.get_running_action_exs_number(task_ex))

        # 3rd iteration complete.
        self.engine.on_action_complete(
            self.get_incomplete_action_ex(task_ex).id,
            wf_utils.Result("Mistral")
        )

        task_ex = db_api.get_task_execution(task_ex.id)

        self.assert_capacity(1, task_ex)

        # 4th iteration complete.
        self.engine.on_action_complete(
            self.get_incomplete_action_ex(task_ex).id,
            wf_utils.Result("Hello")
        )

        task_ex = db_api.get_task_execution(task_ex.id)

        self.assert_capacity(2, task_ex)

        self.await_workflow_success(wf_ex.id)

        # Since we know that we can receive results in random order,
        # check is not depend on order of items.
        with db_api.transaction():
            task_ex = db_api.get_task_execution(task_ex.id)

            result = data_flow.get_task_execution_result(task_ex)

        self.assertIsInstance(result, list)

        self.assertIn('John', result)
        self.assertIn('Ivan', result)
        self.assertIn('Mistral', result)
        self.assertIn('Hello', result)

        self.assertEqual(states.SUCCESS, task_ex.state)

    @testtools.skip('Restore concurrency support.')
    def test_with_items_concurrency_2_fail(self):
        wf_with_concurrency_2_fail = """---
        version: "2.0"

        concurrency_test_fail:
          type: direct

          tasks:
            task1:
              with-items: i in [1, 2, 3, 4]
              action: std.fail
              concurrency: 2
              on-error: task2

            task2:
              action: std.echo output="With-items failed"

        """
        wf_service.create_workflows(wf_with_concurrency_2_fail)

        # Start workflow.
        wf_ex = self.engine.start_workflow('concurrency_test_fail', {})

        self.await_workflow_success(wf_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        task_exs = wf_ex.task_executions

        self.assertEqual(2, len(task_exs))

        task_2 = self._assert_single_item(task_exs, name='task2')

        with db_api.transaction():
            task_2 = db_api.get_task_execution(task_2.id)

            result = data_flow.get_task_execution_result(task_2)

        self.assertEqual('With-items failed', result)

    @testtools.skip('Restore concurrency support.')
    def test_with_items_concurrency_3(self):
        wf_with_concurrency_3 = """---
        version: "2.0"

        concurrency_test:
          type: direct

          input:
           - names: ["John", "Ivan", "Mistral"]

          tasks:
            task1:
              action: std.async_noop
              with-items: name in <% $.names %>
              concurrency: 3

        """

        wf_service.create_workflows(wf_with_concurrency_3)

        # Start workflow.
        wf_ex = self.engine.start_workflow('concurrency_test', {})

        wf_ex = db_api.get_workflow_execution(wf_ex.id)
        task_ex = wf_ex.task_executions[0]

        self.assert_capacity(0, task_ex)
        self.assertEqual(3, self.get_running_action_exs_number(task_ex))

        # 1st iteration complete.
        self.engine.on_action_complete(
            self.get_incomplete_action_ex(task_ex).id,
            wf_utils.Result("John")
        )

        task_ex = db_api.get_task_execution(task_ex.id)

        self.assert_capacity(1, task_ex)

        # 2nd iteration complete.
        self.engine.on_action_complete(
            self.get_incomplete_action_ex(task_ex).id,
            wf_utils.Result("Ivan")
        )

        task_ex = db_api.get_task_execution(task_ex.id)

        self.assert_capacity(2, task_ex)

        # 3rd iteration complete.
        self.engine.on_action_complete(
            self.get_incomplete_action_ex(task_ex).id,
            wf_utils.Result("Mistral")
        )

        task_ex = db_api.get_task_execution(task_ex.id)

        self.assert_capacity(3, task_ex)

        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            task_ex = db_api.get_task_execution(task_ex.id)

            self.assertEqual(states.SUCCESS, task_ex.state)

            # Since we know that we can receive results in random order,
            # check is not depend on order of items.
            result = data_flow.get_task_execution_result(task_ex)

        self.assertIsInstance(result, list)

        self.assertIn('John', result)
        self.assertIn('Ivan', result)
        self.assertIn('Mistral', result)

    @testtools.skip('Restore concurrency support.')
    def test_with_items_concurrency_gt_list_length(self):
        wf_definition = """---
        version: "2.0"

        concurrency_test:
          type: direct

          input:
           - names: ["John", "Ivan"]

          tasks:
            task1:
              with-items: name in <% $.names %>
              action: std.echo output=<% $.name %>
              concurrency: 3
        """

        wf_service.create_workflows(wf_definition)

        # Start workflow.
        wf_ex = self.engine.start_workflow('concurrency_test', {})

        self.await_workflow_success(wf_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        task_ex = self._assert_single_item(
            wf_ex.task_executions,
            name='task1',
            state=states.SUCCESS
        )

        with db_api.transaction():
            task_ex = db_api.get_task_execution(task_ex.id)

            result = data_flow.get_task_execution_result(task_ex)

        self.assertIsInstance(result, list)
        self.assertIn('John', result)
        self.assertIn('Ivan', result)

    def test_with_items_retry_policy(self):
        wf_text = """---
        version: "2.0"

        with_items_retry:
          tasks:
            task1:
              with-items: i in [1, 2, 3]
              action: std.fail
              retry:
                count: 3
                delay: 1
              on-error: task2

            task2:
              action: std.echo output="With-items failed"
        """

        wf_service.create_workflows(wf_text)

        # Start workflow.
        wf_ex = self.engine.start_workflow('with_items_retry', {})

        self.await_workflow_success(wf_ex.id)

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        task_execs = wf_ex.task_executions

        self.assertEqual(2, len(task_execs))

        task1_ex = self._assert_single_item(task_execs, name='task1')

        self.assertEqual(
            2,
            task1_ex.runtime_context['retry_task_policy']['retry_no']
        )
        self.assertEqual(9, len(task1_ex.executions))
        self._assert_multiple_items(task1_ex.executions, 3, accepted=True)

    @testtools.skip('Restore concurrency support.')
    def test_with_items_retry_policy_concurrency(self):
        wf_text = """---
        version: "2.0"

        with_items_retry_concurrency:
          tasks:
            task1:
              with-items: i in [1, 2, 3, 4]
              action: std.fail
              retry:
                count: 3
                delay: 1
              concurrency: 2
              on-error: task2

            task2:
              action: std.echo output="With-items failed"
        """

        wf_service.create_workflows(wf_text)

        # Start workflow.
        wf_ex = self.engine.start_workflow('with_items_retry_concurrency', {})

        self.await_workflow_success(wf_ex.id)

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        task_execs = wf_ex.task_executions

        self.assertEqual(2, len(task_execs))

        task1_ex = self._assert_single_item(task_execs, name='task1')

        self.assertEqual(12, len(task1_ex.executions))
        self._assert_multiple_items(task1_ex.executions, 4, accepted=True)

    def test_with_items_env(self):
        wf_text = """---
        version: "2.0"

        with_items_env:
          tasks:
            task1:
              with-items: i in [1, 2, 3, 4]
              action: std.echo output="<% $.i %>.<% env().name %>"
        """

        wf_service.create_workflows(wf_text)

        # Start workflow.
        wf_ex = self.engine.start_workflow(
            'with_items_env',
            {},
            env={'name': 'Mistral'}
        )

        self.await_workflow_success(wf_ex.id)

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        tasks = wf_ex.task_executions
        task1 = self._assert_single_item(tasks, name='task1')

        with db_api.transaction():
            task1 = db_api.get_task_execution(task1.id)

            result = data_flow.get_task_execution_result(task1)

        self.assertEqual(
            [
                "1.Mistral",
                "2.Mistral",
                "3.Mistral",
                "4.Mistral"
            ],
            result
        )

        self.assertEqual(states.SUCCESS, task1.state)

    def test_with_items_two_tasks_second_starts_on_success(self):
        wb_text = """---
        version: "2.0"

        name: wb1

        workflows:
          with_items:
            type: direct

            tasks:
              task1:
                with-items: i in [1, 2]
                action: std.echo output=<% $.i %>
                on-success: task2
              task2:
                with-items: i in [3, 4]
                action: std.echo output=<% $.i %>
        """

        wb_service.create_workbook_v2(wb_text)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wb1.with_items', {})

        self.await_workflow_success(wf_ex.id)

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        task_execs = wf_ex.task_executions

        task1_ex = self._assert_single_item(
            task_execs,
            name='task1',
            state=states.SUCCESS
        )
        task2_ex = self._assert_single_item(
            task_execs,
            name='task2',
            state=states.SUCCESS
        )

        with db_api.transaction():
            task1_ex = db_api.get_task_execution(task1_ex.id)
            task2_ex = db_api.get_task_execution(task2_ex.id)

            result_task1 = data_flow.get_task_execution_result(task1_ex)
            result_task2 = data_flow.get_task_execution_result(task2_ex)

        # Since we know that we can receive results in random order,
        # check is not depend on order of items.
        self.assertIn(1, result_task1)
        self.assertIn(2, result_task1)
        self.assertIn(3, result_task2)
        self.assertIn(4, result_task2)

    @testtools.skip('Restore concurrency support.')
    def test_with_items_subflow_concurrency_gt_list_length(self):
        wb_text = """---
        version: "2.0"
        name: wb1

        workflows:
          main:
            type: direct

            input:
             - names

            tasks:
              task1:
                with-items: name in <% $.names %>
                workflow: subflow1 name=<% $.name %>
                concurrency: 3

          subflow1:
            type: direct

            input:
                - name
            output:
              result: <% task(task1).result %>

            tasks:
              task1:
                action: std.echo output=<% $.name %>
        """

        wb_service.create_workbook_v2(wb_text)

        # Start workflow.
        names = ["Peter", "Susan", "Edmund", "Lucy", "Aslan", "Caspian"]
        wf_ex = self.engine.start_workflow('wb1.main', {'names': names})

        self.await_workflow_success(wf_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        task_ex = self._assert_single_item(
            wf_ex.task_executions,
            name='task1',
            state=states.SUCCESS
        )

        with db_api.transaction():
            task_ex = db_api.get_task_execution(task_ex.id)

            task_result = data_flow.get_task_execution_result(task_ex)

        result = [item['result'] for item in task_result]

        self.assertListEqual(sorted(result), sorted(names))

    def test_with_items_and_adhoc_action(self):
        wb_text = """---
        version: "2.0"

        name: test

        actions:
          http:
            input:
              - url: http://www.example.com
              - method: GET
              - timeout: 10

            output: <% $.content %>

            base: std.http
            base-input:
              url: <% $.url %>
              method: <% $.method %>
              timeout: <% $.timeout %>

        workflows:
          with_items_default_bug:
            description: Re-create the with-items bug with default values
            type: direct

            tasks:
              get_pages:
                with-items: page in <% range(0, 1) %>
                action: test.http
                input:
                  url: http://www.example.com
                  method: GET
                on-success:
                  - well_done

              well_done:
                action: std.echo output="Well done"
        """

        wb_service.create_workbook_v2(wb_text)

        # Start workflow.
        wf_ex = self.engine.start_workflow('test.with_items_default_bug', {})

        self.await_workflow_success(wf_ex.id)

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        task_execs = wf_ex.task_executions

        task1_ex = self._assert_single_item(task_execs, name='get_pages')
        task2_ex = self._assert_single_item(task_execs, name='well_done')

        self.assertEqual(2, len(task_execs))
        self.assertEqual(states.SUCCESS, task1_ex.state)
        self.assertEqual(states.SUCCESS, task2_ex.state)
