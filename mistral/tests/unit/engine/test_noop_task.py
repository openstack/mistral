# Copyright 2014 - Mirantis, Inc.
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

from oslo_config import cfg

from mistral.db.v2 import api as db_api
from mistral.services import workflows as wf_service
from mistral.tests.unit.engine import base
from mistral.workflow import states

# Use the set_default method to set value otherwise in certain test cases
# the change in value is not permanent.
cfg.CONF.set_default('auth_enable', False, group='pecan')

WF = """
---
version: '2.0'

wf:
  type: direct

  input:
    - num1
    - num2

  output:
    result: <% $.result %>

  tasks:
    task1:
      action: std.echo output=<% $.num1 %>
      publish:
        result1: <% task(task1).result %>
      on-complete:
        - task3

    task2:
      action: std.echo output=<% $.num2 %>
      publish:
        result2: <% task(task2).result %>
      on-complete:
        - task3

    task3:
      description: |
        This task doesn't "action" or "workflow" property. It works as "no-op"
        task and serves just a decision point in the workflow.
      join: all
      on-complete:
        - task4: <% $.num1 + $.num2 = 2 %>
        - task5: <% $.num1 + $.num2 = 3 %>

    task4:
      action: std.echo output=4
      publish:
        result: <% task(task4).result %>

    task5:
      action: std.echo output=5
      publish:
        result: <% task(task5).result %>
"""


class NoopTaskEngineTest(base.EngineTestCase):
    def test_noop_task1(self):
        wf_service.create_workflows(WF)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wf', {'num1': 1, 'num2': 1})

        self.await_workflow_success(wf_ex.id)

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        tasks = wf_ex.task_executions

        self.assertEqual(4, len(tasks))

        task1 = self._assert_single_item(tasks, name='task1')
        task2 = self._assert_single_item(tasks, name='task2')
        task3 = self._assert_single_item(tasks, name='task3')
        task4 = self._assert_single_item(tasks, name='task4')

        self.assertEqual(states.SUCCESS, task1.state)
        self.assertEqual(states.SUCCESS, task2.state)
        self.assertEqual(states.SUCCESS, task3.state)
        self.assertEqual(states.SUCCESS, task4.state)

        self.assertDictEqual({'result': 4}, wf_ex.output)

    def test_noop_task2(self):
        wf_service.create_workflows(WF)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wf', {'num1': 1, 'num2': 2})

        self.await_workflow_success(wf_ex.id)

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        tasks = wf_ex.task_executions

        self.assertEqual(4, len(tasks))

        task1 = self._assert_single_item(tasks, name='task1')
        task2 = self._assert_single_item(tasks, name='task2')
        task3 = self._assert_single_item(tasks, name='task3')
        task5 = self._assert_single_item(tasks, name='task5')

        self.assertEqual(states.SUCCESS, task1.state)
        self.assertEqual(states.SUCCESS, task2.state)
        self.assertEqual(states.SUCCESS, task3.state)
        self.assertEqual(states.SUCCESS, task5.state)

        self.assertDictEqual({'result': 5}, wf_ex.output)
