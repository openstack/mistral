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
from oslo.config import cfg
import testtools

from mistral.db.v2 import api as db_api
from mistral.engine import states
from mistral.openstack.common import log as logging
from mistral.services import workbooks as wb_service
from mistral.tests.unit.engine1 import base
from mistral.workflow import utils as wf_utils

# TODO(nmakhotkin) Need to write more tests.

LOG = logging.getLogger(__name__)
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
          result: <% $.task1 %>

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
        action: std.mistral_http url=<% $.link %>
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


class WithItemsEngineTest(base.EngineTestCase):
    @testtools.skip("Fix 'with-items'.")
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
        with_items_context = task1.runtime_context['with_items']

        self.assertEqual(3, with_items_context['count'])
        self.assertEqual(3, with_items_context['index'])

        # Since we know that we can receive results in random order,
        # check is not depend on order of items.
        result = task1.result['result']

        self.assertTrue(isinstance(result, list))

        self.assertIn('John', result)
        self.assertIn('Ivan', result)
        self.assertIn('Mistral', result)

        self.assertEqual(1, len(tasks))
        self.assertEqual(states.SUCCESS, task1.state)

    @testtools.skip("Fix 'with-items'.")
    def test_with_items_static_var(self):
        wb_service.create_workbook_v2(WORKBOOK_WITH_STATIC_VAR)

        wf_input = copy.copy(WORKFLOW_INPUT)
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
        result = task1.result['result']

        self.assertTrue(isinstance(result, list))

        self.assertIn('Hello, John!', result)
        self.assertIn('Hello, Ivan!', result)
        self.assertIn('Hello, Mistral!', result)

        self.assertEqual(1, len(tasks))
        self.assertEqual(states.SUCCESS, task1.state)

    @testtools.skip("Fix 'with-items'.")
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
        result = task1.result['result']

        self.assertTrue(isinstance(result, list))

        self.assertIn('a 1', result)
        self.assertIn('b 2', result)
        self.assertIn('c 3', result)

        self.assertEqual(1, len(tasks))
        self.assertEqual(states.SUCCESS, task1.state)

    @testtools.skip("Fix 'with-items'.")
    def test_with_items_action_context(self):
        wb_service.create_workbook_v2(WORKBOOK_ACTION_CONTEXT)

        # Start workflow.
        wf_ex = self.engine.start_workflow(
            'wb1.wf1_with_items', WF_INPUT_URLS
        )

        wf_ex = db_api.get_workflow_execution(wf_ex.id)
        task_ex = wf_ex.task_executions[0]

        self.engine.on_task_result(task_ex.id, wf_utils.Result("Ivan"))
        self.engine.on_task_result(task_ex.id, wf_utils.Result("John"))
        self.engine.on_task_result(task_ex.id, wf_utils.Result("Mistral"))

        self._await(
            lambda: self.is_execution_success(wf_ex.id),
        )

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        task_ex = db_api.get_task_execution(task_ex.id)
        result = task_ex.result['result']

        self.assertTrue(isinstance(result, list))

        self.assertIn('John', result)
        self.assertIn('Ivan', result)
        self.assertIn('Mistral', result)

        self.assertEqual(states.SUCCESS, task_ex.state)
