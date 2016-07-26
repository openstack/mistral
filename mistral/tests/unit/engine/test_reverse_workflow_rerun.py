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
    type: reverse
    tasks:
      t1:
        action: std.echo output="Task 1"
      t2:
        action: std.echo output="Task 2"
        requires:
          - t1
      t3:
        action: std.echo output="Task 3"
        requires:
          - t2
"""

SIMPLE_WORKBOOK_DIFF_ENV_VAR = """
---
version: '2.0'
name: wb1
workflows:
  wf1:
    type: reverse
    tasks:
      t1:
        action: std.echo output="Task 1"
      t2:
        action: std.echo output=<% env().var1 %>
        requires:
          - t1
      t3:
        action: std.echo output=<% env().var2 %>
        requires:
          - t2
"""


class ReverseWorkflowRerunTest(base.EngineTestCase):

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
        wf_ex = self.engine.start_workflow('wb1.wf1', {}, task_name='t3')
        self.await_workflow_error(wf_ex.id)
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.ERROR, wf_ex.state)
        self.assertIsNotNone(wf_ex.state_info)
        self.assertEqual(2, len(wf_ex.task_executions))

        task_1_ex = self._assert_single_item(wf_ex.task_executions, name='t1')
        task_2_ex = self._assert_single_item(wf_ex.task_executions, name='t2')

        self.assertEqual(states.SUCCESS, task_1_ex.state)
        self.assertEqual(states.ERROR, task_2_ex.state)
        self.assertIsNotNone(task_2_ex.state_info)

        # Resume workflow and re-run failed task.
        self.engine.rerun_workflow(task_2_ex.id)
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.RUNNING, wf_ex.state)
        self.assertIsNone(wf_ex.state_info)

        # Wait for the workflow to succeed.
        self.await_workflow_success(wf_ex.id)
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.SUCCESS, wf_ex.state)
        self.assertIsNone(wf_ex.state_info)
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
        self.assertIsNone(task_2_ex.state_info)

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
                exc.ActionException(),  # Mock task2 exception for initial run.
                'Task 2',               # Mock task2 success for rerun.
                'Task 3'                # Mock task3 success.
            ]
        )
    )
    def test_rerun_diff_env_vars(self):
        wb_service.create_workbook_v2(SIMPLE_WORKBOOK_DIFF_ENV_VAR)

        # Initial environment variables for the workflow execution.
        env = {
            'var1': 'fee fi fo fum',
            'var2': 'foobar'
        }

        # Run workflow and fail task.
        wf_ex = self.engine.start_workflow(
            'wb1.wf1',
            {},
            task_name='t3',
            env=env
        )

        self.await_workflow_error(wf_ex.id)
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.ERROR, wf_ex.state)
        self.assertIsNotNone(wf_ex.state_info)
        self.assertEqual(2, len(wf_ex.task_executions))
        self.assertDictEqual(env, wf_ex.params['env'])
        self.assertDictEqual(env, wf_ex.context['__env'])

        task_1_ex = self._assert_single_item(wf_ex.task_executions, name='t1')
        task_2_ex = self._assert_single_item(wf_ex.task_executions, name='t2')

        self.assertEqual(states.SUCCESS, task_1_ex.state)
        self.assertEqual(states.ERROR, task_2_ex.state)
        self.assertIsNotNone(task_2_ex.state_info)

        # Update env in workflow execution with the following.
        updated_env = {
            'var1': 'Task 2',
            'var2': 'Task 3'
        }

        # Resume workflow and re-run failed task.
        self.engine.rerun_workflow(task_2_ex.id, env=updated_env)
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.RUNNING, wf_ex.state)
        self.assertIsNone(wf_ex.state_info)
        self.assertDictEqual(updated_env, wf_ex.params['env'])
        self.assertDictEqual(updated_env, wf_ex.context['__env'])

        # Wait for the workflow to succeed.
        self.await_workflow_success(wf_ex.id)
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.SUCCESS, wf_ex.state)
        self.assertIsNone(wf_ex.state_info)
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

        self.assertDictEqual(
            {'output': 'Task 1'},
            task_1_action_exs[0].input
        )

        # Check action executions of task 2.
        self.assertEqual(states.SUCCESS, task_2_ex.state)
        self.assertIsNone(task_2_ex.state_info)

        task_2_action_exs = db_api.get_action_executions(
            task_execution_id=task_2_ex.id)

        self.assertEqual(2, len(task_2_action_exs))
        self.assertEqual(states.ERROR, task_2_action_exs[0].state)
        self.assertEqual(states.SUCCESS, task_2_action_exs[1].state)

        self.assertDictEqual(
            {'output': env['var1']},
            task_2_action_exs[0].input
        )

        self.assertDictEqual(
            {'output': updated_env['var1']},
            task_2_action_exs[1].input
        )

        # Check action executions of task 3.
        self.assertEqual(states.SUCCESS, task_3_ex.state)

        task_3_action_exs = db_api.get_action_executions(
            task_execution_id=task_3_ex.id)

        self.assertEqual(1, len(task_3_action_exs))
        self.assertEqual(states.SUCCESS, task_3_action_exs[0].state)

        self.assertDictEqual(
            {'output': updated_env['var2']},
            task_3_action_exs[0].input
        )

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
        wf_ex = self.engine.start_workflow('wb1.wf1', {}, task_name='t3')
        self.await_workflow_error(wf_ex.id)
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.ERROR, wf_ex.state)
        self.assertIsNotNone(wf_ex.state_info)
        self.assertEqual(2, len(wf_ex.task_executions))

        task_1_ex = self._assert_single_item(wf_ex.task_executions, name='t1')
        task_2_ex = self._assert_single_item(wf_ex.task_executions, name='t2')

        self.assertEqual(states.SUCCESS, task_1_ex.state)
        self.assertEqual(states.ERROR, task_2_ex.state)
        self.assertIsNotNone(task_2_ex.state_info)

        # Resume workflow and re-run failed task.
        e = self.assertRaises(
            exc.MistralError,
            self.engine.rerun_workflow,
            task_1_ex.id
        )

        self.assertIn('not supported', str(e))
