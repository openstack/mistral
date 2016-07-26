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

from oslo_config import cfg

from mistral.actions import base as actions_base
from mistral.db.v2 import api as db_api
from mistral.services import workflows as wf_service
from mistral.tests.unit import base as test_base
from mistral.tests.unit.engine import base
from mistral.workflow import data_flow
from mistral.workflow import states
from mistral.workflow import utils as wf_utils


# Use the set_default method to set value otherwise in certain test cases
# the change in value is not permanent.
cfg.CONF.set_default('auth_enable', False, group='pecan')


WF = """
---
version: '2.0'

wf:
  input:
    - success_result
    - error_result

  tasks:
    task1:
      action: my_action
      input:
        success_result: <% $.success_result %>
        error_result: <% $.error_result %>
      publish:
        p_var: <% task(task1).result %>
      on-error:
        - task2: <% task(task1).result = 2 %>
        - task3: <% task(task1).result = 3 %>

    task2:
      action: std.noop

    task3:
      action: std.noop
"""


class MyAction(actions_base.Action):
    def __init__(self, success_result, error_result):
        self.success_result = success_result
        self.error_result = error_result

    def run(self):
        return wf_utils.Result(
            data=self.success_result,
            error=self.error_result
        )

    def test(self):
        raise NotImplementedError


class ErrorResultTest(base.EngineTestCase):
    def setUp(self):
        super(ErrorResultTest, self).setUp()

        test_base.register_action_class('my_action', MyAction)

    def test_error_result1(self):
        wf_service.create_workflows(WF)

        # Start workflow.
        wf_ex = self.engine.start_workflow(
            'wf',
            {
                'success_result': None,
                'error_result': 2
            }
        )

        self.await_workflow_success(wf_ex.id)

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        tasks = wf_ex.task_executions

        self.assertEqual(2, len(tasks))

        task1 = self._assert_single_item(tasks, name='task1')
        task2 = self._assert_single_item(tasks, name='task2')

        self.assertEqual(states.ERROR, task1.state)
        self.assertEqual(states.SUCCESS, task2.state)

        # "publish" clause is ignored in case of ERROR so task execution field
        # must be empty.
        self.assertDictEqual({}, task1.published)
        self.assertEqual(2, data_flow.get_task_execution_result(task1))

    def test_error_result2(self):
        wf_service.create_workflows(WF)

        # Start workflow.
        wf_ex = self.engine.start_workflow(
            'wf',
            {
                'success_result': None,
                'error_result': 3
            }
        )

        self.await_workflow_success(wf_ex.id)

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        tasks = wf_ex.task_executions

        self.assertEqual(2, len(tasks))

        task1 = self._assert_single_item(tasks, name='task1')
        task3 = self._assert_single_item(tasks, name='task3')

        self.assertEqual(states.ERROR, task1.state)
        self.assertEqual(states.SUCCESS, task3.state)

        # "publish" clause is ignored in case of ERROR so task execution field
        # must be empty.
        self.assertDictEqual({}, task1.published)
        self.assertEqual(3, data_flow.get_task_execution_result(task1))

    def test_success_result(self):
        wf_service.create_workflows(WF)

        # Start workflow.
        wf_ex = self.engine.start_workflow(
            'wf',
            {
                'success_result': 'success',
                'error_result': None
            }
        )

        self.await_workflow_success(wf_ex.id)

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        tasks = wf_ex.task_executions

        self.assertEqual(1, len(tasks))

        task1 = self._assert_single_item(tasks, name='task1')

        self.assertEqual(states.SUCCESS, task1.state)

        # "publish" clause is ignored in case of ERROR so task execution field
        # must be empty.
        self.assertDictEqual({'p_var': 'success'}, task1.published)
        self.assertEqual('success', data_flow.get_task_execution_result(task1))
