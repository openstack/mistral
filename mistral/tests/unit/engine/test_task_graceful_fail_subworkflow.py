# Copyright 2015 - StackStorm, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
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
from mistral.services import workflows as wf_service
from mistral.tests.unit.engine import base
from mistral.workflow import states


# Use the set_default method to set value otherwise in certain test cases
# the change in value is not permanent.
cfg.CONF.set_default('auth_enable', False, group='pecan')

MAIN_WF = """
---
version: '2.0'
main_wf:
  tasks:
    t1:
      description: Task 1
      action: std.noop
      publish:
        task1: some_value
      on-success:
        - t2_l
        - t2
        - t2_r
    t2_l:
      description: Task 2 - Left Branch
      action: std.sleep seconds=2
      publish:
        task2_l: some_value
      on-success:
        - t3_l
    t2:
      description: Task 2 - Fails here
      input:
        wrong_input: true
      workflow: sub_workflow_with_input
      publish:
        task2: some_value
      on-success:
        - t3
    t2_r:
      description: Task 2 - Right Branch
      action: std.sleep seconds=2
      publish:
        task2_r: some_value
      on-success:
        - t3_r
    t3_l:
      description: Task 3 - Left Branch
      action: std.noop
      publish:
        task3_l: some_value
    t3:
      description: Task 3 - Middle Branch
      action: std.noop
      publish:
        task3: some_value
    t3_r:
      description: Task 3 - Right Branch
      action: std.noop
      publish:
        task3_r: some_value
"""
MAIN_WITH_ITEMS_WF = """
---
version: '2.0'
main_wf:
  tasks:
    t1:
      description: Task 1
      action: std.noop
      publish:
        task1: some_value
      on-success:
        - t2_l
        - t2
        - t2_r
    t2_l:
      description: Task 2 - Left Branch
      action: std.sleep seconds=2
      publish:
        task2_l: some_value
      on-success:
        - t3_l
    t2:
      description: Task 2 - Fails here
      with-items: v in <% [1,2,3] %>
      input:
        wrong_input: true
      workflow: sub_workflow_with_input
      publish:
        task2: some_value
      on-success:
        - t3
    t2_r:
      description: Task 2 - Right Branch
      action: std.sleep seconds=2
      publish:
        task2_r: some_value
      on-success:
        - t3_r
    t3_l:
      description: Task 3 - Left Branch
      action: std.noop
      publish:
        task3_l: some_value
    t3:
      description: Task 3 - Middle Branch
      action: std.noop
      publish:
        task3: some_value
    t3_r:
      description: Task 3 - Right Branch
      action: std.noop
      publish:
        task3_r: some_value
"""
SUB_WF = """
---
version: 2.0
sub_workflow_with_input:
  input:
    - my_input
  tasks:
    sub_wf_task:
      action: std.noop
      publish:
        sub_wf_task_result: some_value
"""


class TaskGracefulFailTest(base.EngineTestCase):
    def test_graceful_fail(self):
        wf_service.create_workflows(SUB_WF)
        wf_service.create_workflows(MAIN_WF)

        wf_ex = self.engine.start_workflow('main_wf')

        self.await_workflow_error(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
            task_execs = wf_ex.task_executions

        task_1_ex = self._assert_single_item(task_execs, name='t1')
        task_2_ex = self._assert_single_item(task_execs, name='t2')
        task_2_r_ex = self._assert_single_item(task_execs, name='t2_r')
        task_2_l_ex = self._assert_single_item(task_execs, name='t2_l')
        task_3_r_ex = self._assert_single_item(task_execs, name='t3_r')
        task_3_l_ex = self._assert_single_item(task_execs, name='t3_l')

        self.assertEqual(states.SUCCESS, task_1_ex.state)
        self.assertEqual(states.ERROR, task_2_ex.state)
        self.assertIn('Invalid input', task_2_ex.state_info)
        self.assertEqual(states.SUCCESS, task_2_r_ex.state)
        self.assertEqual(states.SUCCESS, task_2_l_ex.state)
        self.assertEqual(states.SUCCESS, task_3_r_ex.state)
        self.assertEqual(states.SUCCESS, task_3_l_ex.state)

    def test_with_items_graceful_fail(self):
        wf_service.create_workflows(SUB_WF)
        wf_service.create_workflows(MAIN_WITH_ITEMS_WF)

        wf_ex = self.engine.start_workflow('main_wf')

        self.await_workflow_error(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
            task_execs = wf_ex.task_executions

        task_1_ex = self._assert_single_item(task_execs, name='t1')
        task_2_ex = self._assert_single_item(task_execs, name='t2')
        task_2_r_ex = self._assert_single_item(task_execs, name='t2_r')
        task_2_l_ex = self._assert_single_item(task_execs, name='t2_l')
        task_3_r_ex = self._assert_single_item(task_execs, name='t3_r')
        task_3_l_ex = self._assert_single_item(task_execs, name='t3_l')

        self.assertEqual(states.SUCCESS, task_1_ex.state)
        self.assertEqual(states.ERROR, task_2_ex.state)
        self.assertIn('Invalid input', task_2_ex.state_info)
        self.assertEqual(states.SUCCESS, task_2_r_ex.state)
        self.assertEqual(states.SUCCESS, task_2_l_ex.state)
        self.assertEqual(states.SUCCESS, task_3_r_ex.state)
        self.assertEqual(states.SUCCESS, task_3_l_ex.state)
