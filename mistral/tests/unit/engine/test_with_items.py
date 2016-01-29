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

WORKBOOK = """
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
          result: <% $.task1[0] %>

"""

WORKBOOK_WITH_STATIC_VAR = """
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
          result: <% $.task1 %>
"""


WORKBOOK_MULTI_ARRAY = """
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
          result: <% $.task1 %>

"""


WORKBOOK_ACTION_CONTEXT = """
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
          result: <% $.task1 %>
"""


WORKFLOW_INPUT = {
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

WORKFLOW_INPUT_ONE_ITEM = {
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
        wb_service.create_workbook_v2(WORKBOOK)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wb1.with_items', WORKFLOW_INPUT)

        self._await(
            lambda: self.is_execution_success(wf_ex.id),
        )

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        tasks = wf_ex.task_executions
        task1 = self._assert_single_item(tasks, name='task1')
        with_items_context = task1.runtime_context['with_items_context']

        self.assertEqual(3, with_items_context['count'])

        # Since we know that we can receive results in random order,
        # check is not depend on order of items.
        result = data_flow.get_task_execution_result(task1)

        self.assertIsInstance(result, list)

        self.assertIn('John', result)
        self.assertIn('Ivan', result)
        self.assertIn('Mistral', result)

        published = task1.published

        self.assertIn(published['result'], ['John', 'Ivan', 'Mistral'])

        self.assertEqual(1, len(tasks))
        self.assertEqual(states.SUCCESS, task1.state)

    def test_with_items_fail(self):
        workflow = """---
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
        wf_service.create_workflows(workflow)

        # Start workflow.
        wf_ex = self.engine.start_workflow('with_items', {})

        self._await(
            lambda: self.is_execution_success(wf_ex.id),
        )

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        tasks = wf_ex.task_executions
        self.assertEqual(2, len(tasks))

    def test_with_items_static_var(self):
        wb_service.create_workbook_v2(WORKBOOK_WITH_STATIC_VAR)

        wf_input = copy.deepcopy(WORKFLOW_INPUT)
        wf_input.update({'greeting': 'Hello'})
        # Start workflow.
        wf_ex = self.engine.start_workflow('wb1.with_items', wf_input)

        self._await(
            lambda: self.is_execution_success(wf_ex.id),
        )

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        tasks = wf_ex.task_executions
        task1 = self._assert_single_item(tasks, name='task1')
        result = data_flow.get_task_execution_result(task1)

        self.assertIsInstance(result, list)

        self.assertIn('Hello, John!', result)
        self.assertIn('Hello, Ivan!', result)
        self.assertIn('Hello, Mistral!', result)

        self.assertEqual(1, len(tasks))
        self.assertEqual(states.SUCCESS, task1.state)

    def test_with_items_multi_array(self):
        wb_service.create_workbook_v2(WORKBOOK_MULTI_ARRAY)

        wf_input = {'arrayI': ['a', 'b', 'c'], 'arrayJ': [1, 2, 3]}

        # Start workflow.
        wf_ex = self.engine.start_workflow('wb1.with_items', wf_input)

        self._await(
            lambda: self.is_execution_success(wf_ex.id),
        )

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        tasks = wf_ex.task_executions
        task1 = self._assert_single_item(tasks, name='task1')

        # Since we know that we can receive results in random order,
        # check is not depend on order of items.
        result = data_flow.get_task_execution_result(task1)

        self.assertIsInstance(result, list)

        self.assertIn('a 1', result)
        self.assertIn('b 2', result)
        self.assertIn('c 3', result)

        self.assertEqual(1, len(tasks))
        self.assertEqual(states.SUCCESS, task1.state)

    def test_with_items_action_context(self):
        wb_service.create_workbook_v2(WORKBOOK_ACTION_CONTEXT)

        # Start workflow.
        wf_ex = self.engine.start_workflow(
            'wb1.wf1_with_items', WF_INPUT_URLS
        )

        wf_ex = db_api.get_workflow_execution(wf_ex.id)
        task_ex = wf_ex.task_executions[0]

        act_exs = task_ex.executions
        self.engine.on_action_complete(act_exs[0].id, wf_utils.Result("Ivan"))
        self.engine.on_action_complete(act_exs[1].id, wf_utils.Result("John"))
        self.engine.on_action_complete(
            act_exs[2].id, wf_utils.Result("Mistral")
        )

        self._await(
            lambda: self.is_execution_success(wf_ex.id),
        )

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
        workbook = """---
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
        wb_service.create_workbook_v2(workbook)

        # Start workflow.
        wf_input = {'names_info': []}
        wf_ex = self.engine.start_workflow('wb1.with_items', wf_input)

        self._await(
            lambda: self.is_execution_success(wf_ex.id),
        )

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        tasks = wf_ex.task_executions
        task1 = self._assert_single_item(tasks, name='task1')
        task2 = self._assert_single_item(tasks, name='task2')

        self.assertEqual(2, len(tasks))
        self.assertEqual(states.SUCCESS, task1.state)
        self.assertEqual(states.SUCCESS, task2.state)

    def test_with_items_plain_list(self):
        workbook = """---
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
        wb_service.create_workbook_v2(workbook)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wb1.with_items', {})

        self._await(lambda: self.is_execution_success(wf_ex.id))

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        tasks = wf_ex.task_executions
        task1 = self._assert_single_item(tasks, name='task1')
        self.assertEqual(states.SUCCESS, task1.state)

        result = data_flow.get_task_execution_result(task1)

        # Since we know that we can receive results in random order,
        # check is not depend on order of items.
        self.assertIn(1, result)
        self.assertIn(2, result)
        self.assertIn(3, result)

    def test_with_items_plain_list_wrong(self):
        workbook = """---
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
            wb_service.create_workbook_v2, workbook
        )

        self.assertIn("Invalid array in 'with-items'", exception.message)

    def test_with_items_results_order(self):
        workbook = """---
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
                  one_two_three: <% $.task1 %>
        """
        # Register random sleep action in the DB.
        test_base.register_action_class('sleep_echo', RandomSleepEchoAction)

        wb_service.create_workbook_v2(workbook)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wb1.with_items', {})

        self._await(
            lambda: self.is_execution_success(wf_ex.id),
        )

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        tasks = wf_ex.task_executions
        task1 = self._assert_single_item(tasks, name='task1')

        self.assertEqual(states.SUCCESS, task1.state)

        published = task1.published

        # Now we can check order of results explicitly.
        self.assertEqual([1, 2, 3], published['one_two_three'])

    def test_with_items_results_one_item_as_list(self):
        wb_service.create_workbook_v2(WORKBOOK)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wb1.with_items',
                                           WORKFLOW_INPUT_ONE_ITEM)

        self._await(
            lambda: self.is_execution_success(wf_ex.id),
        )

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        tasks = wf_ex.task_executions
        task1 = self._assert_single_item(tasks, name='task1')

        result = data_flow.get_task_execution_result(task1)

        self.assertIsInstance(result, list)

        self.assertIn('Guy', result)

        published = task1.published

        self.assertIn(published['result'], ['Guy'])

        self.assertEqual(1, len(tasks))
        self.assertEqual(states.SUCCESS, task1.state)

    def test_with_items_concurrency_1(self):
        workflow_with_concurrency_1 = """---
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
        wf_service.create_workflows(workflow_with_concurrency_1)

        # Start workflow.
        wf_ex = self.engine.start_workflow('concurrency_test', {})
        wf_ex = db_api.get_execution(wf_ex.id)
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

        self._await(
            lambda: self.is_execution_success(wf_ex.id),
        )

        task_ex = db_api.get_task_execution(task_ex.id)
        # Since we know that we can receive results in random order,
        # check is not depend on order of items.
        result = data_flow.get_task_execution_result(task_ex)

        self.assertIsInstance(result, list)

        self.assertIn('John', result)
        self.assertIn('Ivan', result)
        self.assertIn('Mistral', result)

        self.assertEqual(states.SUCCESS, task_ex.state)

    def test_with_items_concurrency_yaql(self):
        workflow_with_concurrency_yaql = """---
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
        wf_service.create_workflows(workflow_with_concurrency_yaql)

        # Start workflow.
        wf_ex = self.engine.start_workflow(
            'concurrency_test',
            {'concurrency': 2}
        )

        self._await(
            lambda: self.is_execution_success(wf_ex.id),
        )

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        task_ex = wf_ex.task_executions[0]
        # Since we know that we can receive results in random order,
        # check is not depend on order of items.
        result = data_flow.get_task_execution_result(task_ex)

        self.assertIsInstance(result, list)

        self.assertIn('John', result)
        self.assertIn('Ivan', result)
        self.assertIn('Mistral', result)

        self.assertEqual(states.SUCCESS, task_ex.state)

    def test_with_items_concurrency_yaql_wrong_type(self):
        workflow_with_concurrency_yaql = """---
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
        wf_service.create_workflows(workflow_with_concurrency_yaql)

        # Start workflow.
        wf_ex = self.engine.start_workflow(
            'concurrency_test',
            {'concurrency': '2'}
        )

        self.assertIn(
            "Invalid data type in ConcurrencyPolicy",
            wf_ex.state_info
        )
        self.assertEqual(states.ERROR, wf_ex.state)

    def test_with_items_concurrency_2(self):
        workflow_with_concurrency_2 = """---
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
        wf_service.create_workflows(workflow_with_concurrency_2)

        # Start workflow.
        wf_ex = self.engine.start_workflow('concurrency_test', {})
        wf_ex = db_api.get_execution(wf_ex.id)
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

        self._await(
            lambda: self.is_execution_success(wf_ex.id),
        )

        task_ex = db_api.get_task_execution(task_ex.id)
        # Since we know that we can receive results in random order,
        # check is not depend on order of items.
        result = data_flow.get_task_execution_result(task_ex)
        self.assertIsInstance(result, list)

        self.assertIn('John', result)
        self.assertIn('Ivan', result)
        self.assertIn('Mistral', result)
        self.assertIn('Hello', result)

        self.assertEqual(states.SUCCESS, task_ex.state)

    def test_with_items_concurrency_2_fail(self):
        workflow_with_concurrency_2_fail = """---
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
        wf_service.create_workflows(workflow_with_concurrency_2_fail)

        # Start workflow.
        wf_ex = self.engine.start_workflow('concurrency_test_fail', {})

        self._await(
            lambda: self.is_execution_success(wf_ex.id),
        )
        wf_ex = db_api.get_execution(wf_ex.id)

        task_exs = wf_ex.task_executions

        self.assertEqual(2, len(task_exs))

        task_2 = self._assert_single_item(task_exs, name='task2')

        self.assertEqual(
            "With-items failed",
            data_flow.get_task_execution_result(task_2)
        )

    def test_with_items_concurrency_3(self):
        workflow_with_concurrency_3 = """---
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
        wf_service.create_workflows(workflow_with_concurrency_3)

        # Start workflow.
        wf_ex = self.engine.start_workflow('concurrency_test', {})
        wf_ex = db_api.get_execution(wf_ex.id)
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

        self._await(
            lambda: self.is_execution_success(wf_ex.id),
        )

        task_ex = db_api.get_task_execution(task_ex.id)
        # Since we know that we can receive results in random order,
        # check is not depend on order of items.
        result = data_flow.get_task_execution_result(task_ex)
        self.assertIsInstance(result, list)

        self.assertIn('John', result)
        self.assertIn('Ivan', result)
        self.assertIn('Mistral', result)

        self.assertEqual(states.SUCCESS, task_ex.state)

    def test_with_items_concurrency_gt_list_length(self):
        workflow_definition = """---
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

        wf_service.create_workflows(workflow_definition)

        # Start workflow.
        wf_ex = self.engine.start_workflow('concurrency_test', {})

        self._await(
            lambda: self.is_execution_success(wf_ex.id),
        )

        wf_ex = db_api.get_execution(wf_ex.id)
        task_ex = self._assert_single_item(wf_ex.task_executions, name='task1')
        result = data_flow.get_task_execution_result(task_ex)

        self.assertEqual(states.SUCCESS, task_ex.state)
        self.assertIsInstance(result, list)
        self.assertIn('John', result)
        self.assertIn('Ivan', result)

    def test_with_items_retry_policy(self):
        workflow = """---
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
        wf_service.create_workflows(workflow)

        # Start workflow.
        wf_ex = self.engine.start_workflow('with_items_retry', {})

        self._await(
            lambda: self.is_execution_success(wf_ex.id)
        )

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        tasks = wf_ex.task_executions
        self.assertEqual(2, len(tasks))

        task1 = self._assert_single_item(tasks, name='task1')

        self.assertEqual(
            2,
            task1.runtime_context['retry_task_policy']['retry_no']
        )
        self.assertEqual(9, len(task1.executions))
        self._assert_multiple_items(task1.executions, 3, accepted=True)

    def test_with_items_retry_policy_concurrency(self):
        workflow = """---
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
        wf_service.create_workflows(workflow)

        # Start workflow.
        wf_ex = self.engine.start_workflow(
            'with_items_retry_concurrency',
            {}
        )

        self._await(
            lambda: self.is_execution_success(wf_ex.id),
        )

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        tasks = wf_ex.task_executions
        self.assertEqual(2, len(tasks))

        task1 = self._assert_single_item(tasks, name='task1')

        self.assertEqual(12, len(task1.executions))
        self._assert_multiple_items(task1.executions, 4, accepted=True)

    def test_with_items_env(self):
        workflow = """---
        version: "2.0"

        with_items_env:
          tasks:
            task1:
              with-items: i in [1, 2, 3, 4]
              action: std.echo output="<% $.i %>.<% env().name %>"
        """
        wf_service.create_workflows(workflow)
        env = {'name': 'Mistral'}

        # Start workflow.
        wf_ex = self.engine.start_workflow(
            'with_items_env',
            {},
            env=env
        )

        self._await(
            lambda: self.is_execution_success(wf_ex.id),
        )

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        tasks = wf_ex.task_executions
        task1 = self._assert_single_item(tasks, name='task1')

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
        workbook = """---
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
        wb_service.create_workbook_v2(workbook)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wb1.with_items', {})

        self._await(lambda: self.is_execution_success(wf_ex.id))

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        tasks = wf_ex.task_executions
        task1 = self._assert_single_item(tasks, name='task1')
        task2 = self._assert_single_item(tasks, name='task2')
        self.assertEqual(states.SUCCESS, task1.state)
        self.assertEqual(states.SUCCESS, task2.state)

        result_task1 = data_flow.get_task_execution_result(task1)
        result_task2 = data_flow.get_task_execution_result(task2)

        # Since we know that we can receive results in random order,
        # check is not depend on order of items.
        self.assertIn(1, result_task1)
        self.assertIn(2, result_task1)
        self.assertIn(3, result_task2)
        self.assertIn(4, result_task2)

    def test_with_items_subflow_concurrency_gt_list_length(self):
        workbook_definition = """---
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

        wb_service.create_workbook_v2(workbook_definition)

        # Start workflow.
        names = ["Peter", "Susan", "Edmund", "Lucy", "Aslan", "Caspian"]
        wf_ex = self.engine.start_workflow('wb1.main', {'names': names})

        self._await(
            lambda: self.is_execution_success(wf_ex.id),
        )

        wf_ex = db_api.get_execution(wf_ex.id)
        task_ex = self._assert_single_item(wf_ex.task_executions, name='task1')

        self.assertEqual(states.SUCCESS, task_ex.state)

        result = [
            item['result']
            for item in data_flow.get_task_execution_result(task_ex)
        ]

        self.assertListEqual(sorted(result), sorted(names))
