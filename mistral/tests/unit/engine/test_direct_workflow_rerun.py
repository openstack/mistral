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

import mock

from oslo_config import cfg

from mistral.actions import std_actions
from mistral.db.v2 import api as db_api
from mistral import exceptions as exc
from mistral.services import workbooks as wb_service
from mistral.tests.unit.engine import base
from mistral.workflow import states

# Use the set_default method to set value otherwise in certain test cases
# the change in value is not permanent.
cfg.CONF.set_default('auth_enable', False, group='pecan')


SIMPLE_WORKBOOK = """
---
version: '2.0'
name: wb1
workflows:
  wf1:
    type: direct
    tasks:
      t1:
        action: std.echo output="Task 1"
        on-success:
          - t2
      t2:
        action: std.echo output="Task 2"
        on-success:
          - t3
      t3:
        action: std.echo output="Task 3"
"""

WITH_ITEMS_WORKBOOK = """
---
version: '2.0'
name: wb3
workflows:
  wf1:
    type: direct
    tasks:
      t1:
        with-items: i in <% list(range(0, 3)) %>
        action: std.echo output="Task 1.<% $.i %>"
        publish:
          v1: <% $.t1 %>
        on-success:
          - t2
      t2:
        action: std.echo output="Task 2"
"""


WITH_ITEMS_WORKBOOK_CONCURRENCY = """
---
version: '2.0'
name: wb3
workflows:
  wf1:
    type: direct
    tasks:
      t1:
        with-items: i in <% list(range(0, 4)) %>
        action: std.echo output="Task 1.<% $.i %>"
        concurrency: 2
        publish:
          v1: <% $.t1 %>
        on-success:
          - t2
      t2:
        action: std.echo output="Task 2"
"""


JOIN_WORKBOOK = """
---
version: '2.0'
name: wb1
workflows:
  wf1:
    type: direct
    tasks:
      t1:
        action: std.echo output="Task 1"
        on-success:
          - t3
      t2:
        action: std.echo output="Task 2"
        on-success:
          - t3
      t3:
        action: std.echo output="Task 3"
        join: all
"""


class DirectWorkflowRerunTest(base.EngineTestCase):

    @mock.patch.object(
        std_actions.EchoAction,
        'run',
        mock.MagicMock(
            side_effect=[
                'Task 1',               # Mock task1 success for initial run.
                exc.ActionException(),  # Mock task2 exception for initial run.
                'Task 2',               # Mock task2 success for rerun.
                'Task 3'                # Mock task3 success.
            ]
        )
    )
    def test_rerun(self):
        wb_service.create_workbook_v2(SIMPLE_WORKBOOK)

        # Run workflow and fail task.
        wf_ex = self.engine.start_workflow('wb1.wf1', {})
        self._await(lambda: self.is_execution_error(wf_ex.id))
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.ERROR, wf_ex.state)
        self.assertEqual(2, len(wf_ex.task_executions))

        task_1_ex = self._assert_single_item(wf_ex.task_executions, name='t1')
        task_2_ex = self._assert_single_item(wf_ex.task_executions, name='t2')

        self.assertEqual(states.SUCCESS, task_1_ex.state)
        self.assertEqual(states.ERROR, task_2_ex.state)

        # Resume workflow and re-run failed task.
        self.engine.rerun_workflow(wf_ex.id, task_2_ex.id)
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.RUNNING, wf_ex.state)

        # Wait for the workflow to succeed.
        self._await(lambda: self.is_execution_success(wf_ex.id))
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.SUCCESS, wf_ex.state)
        self.assertEqual(3, len(wf_ex.task_executions))

        task_1_ex = self._assert_single_item(wf_ex.task_executions, name='t1')
        task_2_ex = self._assert_single_item(wf_ex.task_executions, name='t2')
        task_3_ex = self._assert_single_item(wf_ex.task_executions, name='t3')

        # Check action executions of task 1.
        self.assertEqual(states.SUCCESS, task_1_ex.state)

        task_1_action_exs = db_api.get_action_executions(
            task_execution_id=task_1_ex.id)

        self.assertEqual(1, len(task_1_action_exs))
        self.assertEqual(states.SUCCESS, task_1_action_exs[0].state)

        # Check action executions of task 2.
        self.assertEqual(states.SUCCESS, task_2_ex.state)

        task_2_action_exs = db_api.get_action_executions(
            task_execution_id=task_2_ex.id)

        self.assertEqual(2, len(task_2_action_exs))
        self.assertEqual(states.ERROR, task_2_action_exs[0].state)
        self.assertEqual(states.SUCCESS, task_2_action_exs[1].state)

        # Check action executions of task 3.
        self.assertEqual(states.SUCCESS, task_3_ex.state)

        task_3_action_exs = db_api.get_action_executions(
            task_execution_id=task_3_ex.id)

        self.assertEqual(1, len(task_3_action_exs))
        self.assertEqual(states.SUCCESS, task_3_action_exs[0].state)

    @mock.patch.object(
        std_actions.EchoAction,
        'run',
        mock.MagicMock(
            side_effect=[
                'Task 1',               # Mock task1 success for initial run.
                exc.ActionException()   # Mock task2 exception for initial run.
            ]
        )
    )
    def test_rerun_from_prev_step(self):
        wb_service.create_workbook_v2(SIMPLE_WORKBOOK)

        # Run workflow and fail task.
        wf_ex = self.engine.start_workflow('wb1.wf1', {})
        self._await(lambda: self.is_execution_error(wf_ex.id))
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.ERROR, wf_ex.state)
        self.assertEqual(2, len(wf_ex.task_executions))

        task_1_ex = self._assert_single_item(wf_ex.task_executions, name='t1')
        task_2_ex = self._assert_single_item(wf_ex.task_executions, name='t2')

        self.assertEqual(states.SUCCESS, task_1_ex.state)
        self.assertEqual(states.ERROR, task_2_ex.state)

        # Resume workflow and re-run failed task.
        e = self.assertRaises(
            exc.EngineException,
            self.engine.rerun_workflow,
            wf_ex.id,
            task_1_ex.id
        )

        self.assertIn('not supported', str(e))

    @mock.patch.object(
        std_actions.EchoAction,
        'run',
        mock.MagicMock(
            side_effect=[
                exc.ActionException(),  # Mock task1 exception for initial run.
                'Task 1.1',             # Mock task1 success for initial run.
                exc.ActionException(),  # Mock task1 exception for initial run.
                'Task 1.0',             # Mock task1 success for rerun.
                'Task 1.2',             # Mock task1 success for rerun.
                'Task 2'                # Mock task2 success.
            ]
        )
    )
    def test_rerun_with_items(self):
        wb_service.create_workbook_v2(WITH_ITEMS_WORKBOOK)

        # Run workflow and fail task.
        wf_ex = self.engine.start_workflow('wb3.wf1', {})
        self._await(lambda: self.is_execution_error(wf_ex.id))
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.ERROR, wf_ex.state)
        self.assertEqual(1, len(wf_ex.task_executions))

        task_1_ex = self._assert_single_item(wf_ex.task_executions, name='t1')

        self.assertEqual(states.ERROR, task_1_ex.state)

        task_1_action_exs = db_api.get_action_executions(
            task_execution_id=task_1_ex.id)

        self.assertEqual(3, len(task_1_action_exs))

        # Resume workflow and re-run failed task.
        self.engine.rerun_workflow(wf_ex.id, task_1_ex.id, reset=False)
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.RUNNING, wf_ex.state)

        self._await(lambda: self.is_execution_success(wf_ex.id), delay=10)
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.SUCCESS, wf_ex.state)
        self.assertEqual(2, len(wf_ex.task_executions))

        task_1_ex = self._assert_single_item(wf_ex.task_executions, name='t1')
        task_2_ex = self._assert_single_item(wf_ex.task_executions, name='t2')

        # Check action executions of task 1.
        self.assertEqual(states.SUCCESS, task_1_ex.state)

        task_1_action_exs = db_api.get_action_executions(
            task_execution_id=task_1_ex.id)

        # The single action execution that succeeded should not re-run.
        self.assertEqual(5, len(task_1_action_exs))

        self.assertListEqual(['Task 1.0', 'Task 1.1', 'Task 1.2'],
                             task_1_ex.published.get('v1'))

        # Check action executions of task 2.
        self.assertEqual(states.SUCCESS, task_2_ex.state)

        task_2_action_exs = db_api.get_action_executions(
            task_execution_id=task_2_ex.id)

        self.assertEqual(1, len(task_2_action_exs))

    @mock.patch.object(
        std_actions.EchoAction,
        'run',
        mock.MagicMock(
            side_effect=[
                exc.ActionException(),  # Mock task1 exception for initial run.
                'Task 1.1',             # Mock task1 success for initial run.
                exc.ActionException(),  # Mock task1 exception for initial run.
                'Task 1.3',             # Mock task1 success for initial run.
                'Task 1.0',             # Mock task1 success for rerun.
                'Task 1.2',             # Mock task1 success for rerun.
                'Task 2'                # Mock task2 success.
            ]
        )
    )
    def test_rerun_with_items_concurrency(self):
        wb_service.create_workbook_v2(WITH_ITEMS_WORKBOOK_CONCURRENCY)

        # Run workflow and fail task.
        wf_ex = self.engine.start_workflow('wb3.wf1', {})
        self._await(lambda: self.is_execution_error(wf_ex.id))

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.ERROR, wf_ex.state)
        self.assertEqual(1, len(wf_ex.task_executions))

        task_1_ex = self._assert_single_item(wf_ex.task_executions, name='t1')

        self.assertEqual(states.ERROR, task_1_ex.state)

        task_1_action_exs = db_api.get_action_executions(
            task_execution_id=task_1_ex.id
        )

        self.assertEqual(4, len(task_1_action_exs))

        # Resume workflow and re-run failed task.
        self.engine.rerun_workflow(wf_ex.id, task_1_ex.id, reset=False)
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.RUNNING, wf_ex.state)

        self._await(lambda: self.is_execution_success(wf_ex.id), delay=10)
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.SUCCESS, wf_ex.state)
        self.assertEqual(2, len(wf_ex.task_executions))

        task_1_ex = self._assert_single_item(wf_ex.task_executions, name='t1')
        task_2_ex = self._assert_single_item(wf_ex.task_executions, name='t2')

        # Check action executions of task 1.
        self.assertEqual(states.SUCCESS, task_1_ex.state)

        task_1_action_exs = db_api.get_action_executions(
            task_execution_id=task_1_ex.id)

        # The action executions that succeeded should not re-run.
        self.assertEqual(6, len(task_1_action_exs))
        self.assertListEqual(['Task 1.0', 'Task 1.1', 'Task 1.2', 'Task 1.3'],
                             task_1_ex.published.get('v1'))

        # Check action executions of task 2.
        self.assertEqual(states.SUCCESS, task_2_ex.state)

        task_2_action_exs = db_api.get_action_executions(
            task_execution_id=task_2_ex.id)

        self.assertEqual(1, len(task_2_action_exs))

    @mock.patch.object(
        std_actions.EchoAction,
        'run',
        mock.MagicMock(
            side_effect=[
                'Task 1',               # Mock task1 success for initial run.
                'Task 2',               # Mock task2 success for initial run.
                exc.ActionException(),  # Mock task3 exception for initial run.
                'Task 3'                # Mock task3 success for rerun.
            ]
        )
    )
    def test_rerun_on_join_task(self):
        wb_service.create_workbook_v2(JOIN_WORKBOOK)

        # Run workflow and fail task.
        wf_ex = self.engine.start_workflow('wb1.wf1', {})
        wf_ex = db_api.get_workflow_execution(wf_ex.id)
        self._await(lambda: self.is_execution_error(wf_ex.id))
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.ERROR, wf_ex.state)
        self.assertEqual(3, len(wf_ex.task_executions))

        task_1_ex = self._assert_single_item(wf_ex.task_executions, name='t1')
        task_2_ex = self._assert_single_item(wf_ex.task_executions, name='t2')
        task_3_ex = self._assert_single_item(wf_ex.task_executions, name='t3')

        self.assertEqual(states.SUCCESS, task_1_ex.state)
        self.assertEqual(states.SUCCESS, task_2_ex.state)
        self.assertEqual(states.ERROR, task_3_ex.state)

        # Resume workflow and re-run failed task.
        self.engine.rerun_workflow(wf_ex.id, task_3_ex.id)
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.RUNNING, wf_ex.state)

        # Wait for the workflow to succeed.
        self._await(lambda: self.is_execution_success(wf_ex.id))
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.SUCCESS, wf_ex.state)
        self.assertEqual(3, len(wf_ex.task_executions))

        task_1_ex = self._assert_single_item(wf_ex.task_executions, name='t1')
        task_2_ex = self._assert_single_item(wf_ex.task_executions, name='t2')
        task_3_ex = self._assert_single_item(wf_ex.task_executions, name='t3')

        # Check action executions of task 1.
        task_1_action_exs = db_api.get_action_executions(
            task_execution_id=task_1_ex.id)

        self.assertEqual(1, len(task_1_action_exs))
        self.assertEqual(states.SUCCESS, task_1_action_exs[0].state)

        # Check action executions of task 2.
        task_2_action_exs = db_api.get_action_executions(
            task_execution_id=task_2_ex.id)

        self.assertEqual(1, len(task_2_action_exs))
        self.assertEqual(states.SUCCESS, task_2_action_exs[0].state)

        # Check action executions of task 3.
        task_3_action_exs = db_api.get_action_executions(
            task_execution_id=wf_ex.task_executions[2].id)

        self.assertEqual(2, len(task_3_action_exs))
        self.assertEqual(states.ERROR, task_3_action_exs[0].state)
        self.assertEqual(states.SUCCESS, task_3_action_exs[1].state)

    @mock.patch.object(
        std_actions.EchoAction,
        'run',
        mock.MagicMock(
            side_effect=[
                exc.ActionException(),  # Mock task1 exception for initial run.
                exc.ActionException(),  # Mock task2 exception for initial run.
                'Task 1',               # Mock task2 success for rerun.
                'Task 2',               # Mock task2 success for rerun.
                'Task 3'                # Mock task3 success.
            ]
        )
    )
    def test_rerun_join_with_branch_errors(self):
        wb_service.create_workbook_v2(JOIN_WORKBOOK)

        # Run workflow and fail task.
        wf_ex = self.engine.start_workflow('wb1.wf1', {})
        wf_ex = db_api.get_workflow_execution(wf_ex.id)
        task_1_ex = self._assert_single_item(wf_ex.task_executions, name='t1')
        task_2_ex = self._assert_single_item(wf_ex.task_executions, name='t2')
        self._await(lambda: self.is_task_in_state(task_1_ex.id, states.ERROR))
        self._await(lambda: self.is_task_in_state(task_2_ex.id, states.ERROR))
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.ERROR, wf_ex.state)
        self.assertEqual(2, len(wf_ex.task_executions))

        task_1_ex = self._assert_single_item(wf_ex.task_executions, name='t1')
        task_2_ex = self._assert_single_item(wf_ex.task_executions, name='t2')

        self.assertEqual(states.ERROR, task_1_ex.state)
        self.assertEqual(states.ERROR, task_2_ex.state)

        # Resume workflow and re-run failed task.
        self.engine.rerun_workflow(wf_ex.id, task_1_ex.id)
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.RUNNING, wf_ex.state)

        # Wait for the task to succeed.
        task_1_ex = self._assert_single_item(wf_ex.task_executions, name='t1')
        self._await(lambda: self.is_task_in_state(task_1_ex.id,
                                                  states.SUCCESS))
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.RUNNING, wf_ex.state)
        self.assertEqual(3, len(wf_ex.task_executions))

        task_1_ex = self._assert_single_item(wf_ex.task_executions, name='t1')
        task_2_ex = self._assert_single_item(wf_ex.task_executions, name='t2')
        task_3_ex = self._assert_single_item(wf_ex.task_executions, name='t3')

        self.assertEqual(states.SUCCESS, task_1_ex.state)
        self.assertEqual(states.ERROR, task_2_ex.state)
        self.assertEqual(states.WAITING, task_3_ex.state)

        # Resume workflow and re-run failed task.
        self.engine.rerun_workflow(wf_ex.id, task_2_ex.id)
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.RUNNING, wf_ex.state)

        # Wait for the workflow to succeed.
        self._await(lambda: self.is_execution_success(wf_ex.id))
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.SUCCESS, wf_ex.state)
        self.assertEqual(3, len(wf_ex.task_executions))

        task_1_ex = self._assert_single_item(wf_ex.task_executions, name='t1')
        task_2_ex = self._assert_single_item(wf_ex.task_executions, name='t2')
        task_3_ex = self._assert_single_item(wf_ex.task_executions, name='t3')

        # Check action executions of task 1.
        task_1_action_exs = db_api.get_action_executions(
            task_execution_id=task_1_ex.id)

        self.assertEqual(2, len(task_1_action_exs))
        self.assertEqual(states.ERROR, task_1_action_exs[0].state)
        self.assertEqual(states.SUCCESS, task_1_action_exs[1].state)

        # Check action executions of task 2.
        task_2_action_exs = db_api.get_action_executions(
            task_execution_id=task_2_ex.id)

        self.assertEqual(2, len(task_2_action_exs))
        self.assertEqual(states.ERROR, task_2_action_exs[0].state)
        self.assertEqual(states.SUCCESS, task_2_action_exs[1].state)

        # Check action executions of task 3.
        task_3_action_exs = db_api.get_action_executions(
            task_execution_id=wf_ex.task_executions[2].id)

        self.assertEqual(1, len(task_3_action_exs))
        self.assertEqual(states.SUCCESS, task_3_action_exs[0].state)
