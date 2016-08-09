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
import testtools

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

SIMPLE_WORKBOOK_DIFF_ENV_VAR = """
---
version: '2.0'

name: wb1

workflows:
  wf1:
    type: direct

    tasks:
      t10:
        action: std.echo output="Task 10"
        on-success:
          - t21
          - t30
      t21:
        action: std.echo output=<% env().var1 %>
        on-success:
          - t22
      t22:
        action: std.echo output="<% env().var2 %>"
        on-success:
          - t30
      t30:
        join: all
        action: std.echo output="<% env().var3 %>"
        wait-before: 1
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
          v1: <% task(t1).result %>
        on-success:
          - t2
      t2:
        action: std.echo output="Task 2"
"""

WITH_ITEMS_WORKBOOK_DIFF_ENV_VAR = """
---
version: '2.0'

name: wb3

workflows:
  wf1:
    type: direct

    tasks:
      t1:
        with-items: i in <% list(range(0, 3)) %>
        action: std.echo output="Task 1.<% $.i %> [<% env().var1 %>]"
        publish:
          v1: <% task(t1).result %>
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
          v1: <% task(t1).result %>
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

SUBFLOW_WORKBOOK = """
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
        workflow: wf2
        on-success:
          - t3
      t3:
        action: std.echo output="Task 3"

  wf2:
    type: direct

    output:
      result: <% task(wf2_t1).result %>

    tasks:
      wf2_t1:
        action: std.echo output="Task 2"
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
            task_execution_id=task_1_ex.id
        )

        self.assertEqual(1, len(task_1_action_exs))
        self.assertEqual(states.SUCCESS, task_1_action_exs[0].state)

        # Check action executions of task 2.
        self.assertEqual(states.SUCCESS, task_2_ex.state)
        self.assertIsNone(task_2_ex.state_info)

        task_2_action_exs = db_api.get_action_executions(
            task_execution_id=task_2_ex.id
        )

        self.assertEqual(2, len(task_2_action_exs))
        self.assertEqual(states.ERROR, task_2_action_exs[0].state)
        self.assertEqual(states.SUCCESS, task_2_action_exs[1].state)

        # Check action executions of task 3.
        self.assertEqual(states.SUCCESS, task_3_ex.state)

        task_3_action_exs = db_api.get_action_executions(
            task_execution_id=task_3_ex.id
        )

        self.assertEqual(1, len(task_3_action_exs))
        self.assertEqual(states.SUCCESS, task_3_action_exs[0].state)

    @mock.patch.object(
        std_actions.EchoAction,
        'run',
        mock.MagicMock(
            side_effect=[
                'Task 10',              # Mock task10 success for first run.
                exc.ActionException(),  # Mock task21 exception for first run.
                'Task 21',              # Mock task21 success for rerun.
                'Task 22',              # Mock task22 success.
                'Task 30'               # Mock task30 success.
            ]
        )
    )
    def test_rerun_diff_env_vars(self):
        wb_service.create_workbook_v2(SIMPLE_WORKBOOK_DIFF_ENV_VAR)

        # Initial environment variables for the workflow execution.
        env = {
            'var1': 'fee fi fo fum',
            'var2': 'mirror mirror',
            'var3': 'heigh-ho heigh-ho'
        }

        # Run workflow and fail task.
        wf_ex = self.engine.start_workflow('wb1.wf1', {}, env=env)

        self.await_workflow_error(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
            task_execs = wf_ex.task_executions

        self.assertEqual(states.ERROR, wf_ex.state)
        self.assertIsNotNone(wf_ex.state_info)
        self.assertEqual(3, len(task_execs))
        self.assertDictEqual(env, wf_ex.params['env'])
        self.assertDictEqual(env, wf_ex.context['__env'])

        task_10_ex = self._assert_single_item(task_execs, name='t10')
        task_21_ex = self._assert_single_item(task_execs, name='t21')
        task_30_ex = self._assert_single_item(task_execs, name='t30')

        self.assertEqual(states.SUCCESS, task_10_ex.state)
        self.assertEqual(states.ERROR, task_21_ex.state)
        self.assertIsNotNone(task_21_ex.state_info)
        self.assertEqual(states.ERROR, task_30_ex.state)

        # Update env in workflow execution with the following.
        updated_env = {
            'var1': 'Task 21',
            'var2': 'Task 22',
            'var3': 'Task 30'
        }

        # Resume workflow and re-run failed task.
        wf_ex = self.engine.rerun_workflow(task_21_ex.id, env=updated_env)

        self.assertEqual(states.RUNNING, wf_ex.state)
        self.assertIsNone(wf_ex.state_info)
        self.assertDictEqual(updated_env, wf_ex.params['env'])
        self.assertDictEqual(updated_env, wf_ex.context['__env'])

        # Await t30 success.
        self.await_task_success(task_30_ex.id)

        # Wait for the workflow to succeed.
        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
            task_execs = wf_ex.task_executions

        self.assertEqual(states.SUCCESS, wf_ex.state)
        self.assertIsNone(wf_ex.state_info)
        self.assertEqual(4, len(task_execs))

        task_10_ex = self._assert_single_item(task_execs, name='t10')
        task_21_ex = self._assert_single_item(task_execs, name='t21')
        task_22_ex = self._assert_single_item(task_execs, name='t22')
        task_30_ex = self._assert_single_item(task_execs, name='t30')

        # Check action executions of task 10.
        self.assertEqual(states.SUCCESS, task_10_ex.state)

        task_10_action_exs = db_api.get_action_executions(
            task_execution_id=task_10_ex.id
        )

        self.assertEqual(1, len(task_10_action_exs))
        self.assertEqual(states.SUCCESS, task_10_action_exs[0].state)

        self.assertDictEqual(
            {'output': 'Task 10'},
            task_10_action_exs[0].input
        )

        # Check action executions of task 21.
        self.assertEqual(states.SUCCESS, task_21_ex.state)
        self.assertIsNone(task_21_ex.state_info)

        task_21_action_exs = db_api.get_action_executions(
            task_execution_id=task_21_ex.id
        )

        self.assertEqual(2, len(task_21_action_exs))
        self.assertEqual(states.ERROR, task_21_action_exs[0].state)
        self.assertEqual(states.SUCCESS, task_21_action_exs[1].state)

        self.assertDictEqual(
            {'output': env['var1']},
            task_21_action_exs[0].input
        )

        self.assertDictEqual(
            {'output': updated_env['var1']},
            task_21_action_exs[1].input
        )

        # Check action executions of task 22.
        self.assertEqual(states.SUCCESS, task_22_ex.state)

        task_22_action_exs = db_api.get_action_executions(
            task_execution_id=task_22_ex.id
        )

        self.assertEqual(1, len(task_22_action_exs))
        self.assertEqual(states.SUCCESS, task_22_action_exs[0].state)

        self.assertDictEqual(
            {'output': updated_env['var2']},
            task_22_action_exs[0].input
        )

        # Check action executions of task 30.
        self.assertEqual(states.SUCCESS, task_30_ex.state)

        task_30_action_exs = db_api.get_action_executions(
            task_execution_id=task_30_ex.id
        )

        self.assertEqual(1, len(task_30_action_exs))
        self.assertEqual(states.SUCCESS, task_30_action_exs[0].state)

        self.assertDictEqual(
            {'output': updated_env['var3']},
            task_30_action_exs[0].input
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
        wf_ex = self.engine.start_workflow('wb1.wf1', {})

        self.await_workflow_error(wf_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.ERROR, wf_ex.state)
        self.assertIsNotNone(wf_ex.state_info)

        task_execs = wf_ex.task_executions

        self.assertEqual(2, len(task_execs))

        task_1_ex = self._assert_single_item(
            task_execs,
            name='t1',
            state=states.SUCCESS
        )
        task_2_ex = self._assert_single_item(
            task_execs,
            name='t2',
            state=states.ERROR
        )

        self.assertIsNotNone(task_2_ex.state_info)

        # Resume workflow and re-run failed task.
        e = self.assertRaises(
            exc.MistralError,
            self.engine.rerun_workflow,
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

        self.await_workflow_error(wf_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.ERROR, wf_ex.state)
        self.assertIsNotNone(wf_ex.state_info)

        task_execs = wf_ex.task_executions

        self.assertEqual(1, len(task_execs))

        task_1_ex = self._assert_single_item(task_execs, name='t1')

        self.assertEqual(states.ERROR, task_1_ex.state)
        self.assertIsNotNone(task_1_ex.state_info)

        task_1_action_exs = db_api.get_action_executions(
            task_execution_id=task_1_ex.id
        )

        self.assertEqual(3, len(task_1_action_exs))

        # Resume workflow and re-run failed task.
        self.engine.rerun_workflow(task_1_ex.id, reset=False)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.RUNNING, wf_ex.state)
        self.assertIsNone(wf_ex.state_info)

        self.await_workflow_success(wf_ex.id, delay=10)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.SUCCESS, wf_ex.state)
        self.assertIsNone(wf_ex.state_info)

        task_execs = wf_ex.task_executions

        self.assertEqual(2, len(task_execs))

        task_1_ex = self._assert_single_item(task_execs, name='t1')
        task_2_ex = self._assert_single_item(task_execs, name='t2')

        # Check action executions of task 1.
        self.assertEqual(states.SUCCESS, task_1_ex.state)
        self.assertIsNone(task_1_ex.state_info)

        task_1_action_exs = db_api.get_action_executions(
            task_execution_id=task_1_ex.id
        )

        # The single action execution that succeeded should not re-run.
        self.assertEqual(5, len(task_1_action_exs))
        self.assertListEqual(
            ['Task 1.0', 'Task 1.1', 'Task 1.2'],
            task_1_ex.published.get('v1')
        )

        # Check action executions of task 2.
        self.assertEqual(states.SUCCESS, task_2_ex.state)

        task_2_action_exs = db_api.get_action_executions(
            task_execution_id=task_2_ex.id
        )

        self.assertEqual(1, len(task_2_action_exs))

    @testtools.skip('Restore concurrency support.')
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

        self.await_workflow_error(wf_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.ERROR, wf_ex.state)
        self.assertIsNotNone(wf_ex.state_info)
        self.assertEqual(1, len(wf_ex.task_executions))

        task_1_ex = self._assert_single_item(wf_ex.task_executions, name='t1')

        self.assertEqual(states.ERROR, task_1_ex.state)

        task_1_action_exs = db_api.get_action_executions(
            task_execution_id=task_1_ex.id
        )

        self.assertEqual(4, len(task_1_action_exs))

        # Resume workflow and re-run failed task.
        self.engine.rerun_workflow(task_1_ex.id, reset=False)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.RUNNING, wf_ex.state)
        self.assertIsNone(wf_ex.state_info)

        self.await_workflow_success(wf_ex.id, delay=10)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.SUCCESS, wf_ex.state)
        self.assertIsNone(wf_ex.state_info)
        self.assertEqual(2, len(wf_ex.task_executions))

        task_1_ex = self._assert_single_item(wf_ex.task_executions, name='t1')
        task_2_ex = self._assert_single_item(wf_ex.task_executions, name='t2')

        # Check action executions of task 1.
        self.assertEqual(states.SUCCESS, task_1_ex.state)
        self.assertIsNone(task_1_ex.state_info)

        task_1_action_exs = db_api.get_action_executions(
            task_execution_id=task_1_ex.id
        )

        # The action executions that succeeded should not re-run.
        self.assertEqual(6, len(task_1_action_exs))
        self.assertListEqual(['Task 1.0', 'Task 1.1', 'Task 1.2', 'Task 1.3'],
                             task_1_ex.published.get('v1'))

        # Check action executions of task 2.
        self.assertEqual(states.SUCCESS, task_2_ex.state)

        task_2_action_exs = db_api.get_action_executions(
            task_execution_id=task_2_ex.id
        )

        self.assertEqual(1, len(task_2_action_exs))

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
    def test_rerun_with_items_diff_env_vars(self):
        wb_service.create_workbook_v2(WITH_ITEMS_WORKBOOK_DIFF_ENV_VAR)

        # Initial environment variables for the workflow execution.
        env = {'var1': 'fee fi fo fum'}

        # Run workflow and fail task.
        wf_ex = self.engine.start_workflow('wb3.wf1', {}, env=env)

        self.await_workflow_error(wf_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.ERROR, wf_ex.state)
        self.assertIsNotNone(wf_ex.state_info)
        self.assertEqual(1, len(wf_ex.task_executions))

        task_1_ex = self._assert_single_item(wf_ex.task_executions, name='t1')

        self.assertEqual(states.ERROR, task_1_ex.state)
        self.assertIsNotNone(task_1_ex.state_info)

        task_1_action_exs = db_api.get_action_executions(
            task_execution_id=task_1_ex.id
        )

        self.assertEqual(3, len(task_1_action_exs))

        # Update env in workflow execution with the following.
        updated_env = {
            'var1': 'foobar'
        }

        # Resume workflow and re-run failed task.
        self.engine.rerun_workflow(
            task_1_ex.id,
            reset=False,
            env=updated_env
        )

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.RUNNING, wf_ex.state)
        self.assertIsNone(wf_ex.state_info)

        self.await_workflow_success(wf_ex.id, delay=10)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.SUCCESS, wf_ex.state)
        self.assertIsNone(wf_ex.state_info)
        self.assertEqual(2, len(wf_ex.task_executions))

        task_1_ex = self._assert_single_item(wf_ex.task_executions, name='t1')
        task_2_ex = self._assert_single_item(wf_ex.task_executions, name='t2')

        # Check action executions of task 1.
        self.assertEqual(states.SUCCESS, task_1_ex.state)
        self.assertIsNone(task_1_ex.state_info)

        task_1_action_exs = db_api.get_action_executions(
            task_execution_id=task_1_ex.id
        )

        expected_inputs = [
            'Task 1.0 [%s]' % env['var1'],          # Task 1 item 0 (error).
            'Task 1.1 [%s]' % env['var1'],          # Task 1 item 1.
            'Task 1.2 [%s]' % env['var1'],          # Task 1 item 2 (error).
            'Task 1.0 [%s]' % updated_env['var1'],  # Task 1 item 0 (rerun).
            'Task 1.2 [%s]' % updated_env['var1']   # Task 1 item 2 (rerun).
        ]

        result = zip(task_1_action_exs, expected_inputs)

        for (action_ex, expected_input) in result:
            self.assertDictEqual(
                {'output': expected_input},
                action_ex.input
            )

        # Check action executions of task 2.
        self.assertEqual(states.SUCCESS, task_2_ex.state)

        task_2_action_exs = db_api.get_action_executions(
            task_execution_id=task_2_ex.id
        )

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

        self.await_workflow_error(wf_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.ERROR, wf_ex.state)
        self.assertIsNotNone(wf_ex.state_info)
        self.assertEqual(3, len(wf_ex.task_executions))

        task_1_ex = self._assert_single_item(wf_ex.task_executions, name='t1')
        task_2_ex = self._assert_single_item(wf_ex.task_executions, name='t2')
        task_3_ex = self._assert_single_item(wf_ex.task_executions, name='t3')

        self.assertEqual(states.SUCCESS, task_1_ex.state)
        self.assertEqual(states.SUCCESS, task_2_ex.state)
        self.assertEqual(states.ERROR, task_3_ex.state)
        self.assertIsNotNone(task_3_ex.state_info)

        # Resume workflow and re-run failed task.
        self.engine.rerun_workflow(task_3_ex.id)

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
            task_execution_id=task_1_ex.id
        )

        self.assertEqual(1, len(task_1_action_exs))
        self.assertEqual(states.SUCCESS, task_1_action_exs[0].state)

        # Check action executions of task 2.
        self.assertEqual(states.SUCCESS, task_2_ex.state)

        task_2_action_exs = db_api.get_action_executions(
            task_execution_id=task_2_ex.id
        )

        self.assertEqual(1, len(task_2_action_exs))
        self.assertEqual(states.SUCCESS, task_2_action_exs[0].state)

        # Check action executions of task 3.
        self.assertEqual(states.SUCCESS, task_3_ex.state)
        self.assertIsNone(task_3_ex.state_info)

        task_3_action_exs = db_api.get_action_executions(
            task_execution_id=wf_ex.task_executions[2].id
        )

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
                'Task 1',               # Mock task1 success for rerun.
                'Task 2',               # Mock task2 success for rerun.
                'Task 3'                # Mock task3 success.
            ]
        )
    )
    def test_rerun_join_with_branch_errors(self):
        wb_service.create_workbook_v2(JOIN_WORKBOOK)

        # Run workflow and fail task.
        wf_ex = self.engine.start_workflow('wb1.wf1', {})

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
            task_execs = wf_ex.task_executions

        task_1_ex = self._assert_single_item(task_execs, name='t1')
        task_2_ex = self._assert_single_item(task_execs, name='t2')

        self.await_task_error(task_1_ex.id)
        self.await_task_error(task_2_ex.id)

        self.await_workflow_error(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
            task_execs = wf_ex.task_executions

        self.assertEqual(states.ERROR, wf_ex.state)
        self.assertIsNotNone(wf_ex.state_info)
        self.assertEqual(2, len(task_execs))

        task_1_ex = self._assert_single_item(task_execs, name='t1')

        self.assertEqual(states.ERROR, task_1_ex.state)
        self.assertIsNotNone(task_1_ex.state_info)

        task_2_ex = self._assert_single_item(task_execs, name='t2')

        self.assertEqual(states.ERROR, task_2_ex.state)
        self.assertIsNotNone(task_2_ex.state_info)

        # Resume workflow and re-run failed task.
        wf_ex = self.engine.rerun_workflow(task_1_ex.id)

        self.assertEqual(states.RUNNING, wf_ex.state)
        self.assertIsNone(wf_ex.state_info)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
            task_execs = wf_ex.task_executions

        # Wait for the task to succeed.
        task_1_ex = self._assert_single_item(task_execs, name='t1')

        self.await_task_success(task_1_ex.id)

        self.await_workflow_error(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
            task_execs = wf_ex.task_executions

        self.assertEqual(states.ERROR, wf_ex.state)
        self.assertIsNotNone(wf_ex.state_info)
        self.assertEqual(3, len(task_execs))

        task_1_ex = self._assert_single_item(task_execs, name='t1')
        task_2_ex = self._assert_single_item(task_execs, name='t2')
        task_3_ex = self._assert_single_item(task_execs, name='t3')

        self.assertEqual(states.SUCCESS, task_1_ex.state)
        self.assertEqual(states.ERROR, task_2_ex.state)
        self.assertEqual(states.ERROR, task_3_ex.state)

        # Resume workflow and re-run failed task.
        wf_ex = self.engine.rerun_workflow(task_2_ex.id)

        self.assertEqual(states.RUNNING, wf_ex.state)
        self.assertIsNone(wf_ex.state_info)

        # Join now should finally complete.
        self.await_task_success(task_3_ex.id)

        # Wait for the workflow to succeed.
        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
            task_execs = wf_ex.task_executions

        self.assertEqual(states.SUCCESS, wf_ex.state)
        self.assertIsNone(wf_ex.state_info)
        self.assertEqual(3, len(task_execs))

        task_1_ex = self._assert_single_item(task_execs, name='t1')
        task_2_ex = self._assert_single_item(task_execs, name='t2')
        task_3_ex = self._assert_single_item(task_execs, name='t3')

        # Check action executions of task 1.
        self.assertEqual(states.SUCCESS, task_1_ex.state)
        self.assertIsNone(task_1_ex.state_info)

        task_1_action_exs = db_api.get_action_executions(
            task_execution_id=task_1_ex.id
        )

        self.assertEqual(2, len(task_1_action_exs))
        self.assertEqual(states.ERROR, task_1_action_exs[0].state)
        self.assertEqual(states.SUCCESS, task_1_action_exs[1].state)

        # Check action executions of task 2.
        self.assertEqual(states.SUCCESS, task_2_ex.state)
        self.assertIsNone(task_2_ex.state_info)

        task_2_action_exs = db_api.get_action_executions(
            task_execution_id=task_2_ex.id
        )

        self.assertEqual(2, len(task_2_action_exs))
        self.assertEqual(states.ERROR, task_2_action_exs[0].state)
        self.assertEqual(states.SUCCESS, task_2_action_exs[1].state)

        # Check action executions of task 3.
        self.assertEqual(states.SUCCESS, task_3_ex.state)

        task_3_action_exs = db_api.get_action_executions(
            task_execution_id=task_execs[2].id
        )

        self.assertEqual(1, len(task_3_action_exs))
        self.assertEqual(states.SUCCESS, task_3_action_exs[0].state)

    @mock.patch.object(
        std_actions.EchoAction,
        'run',
        mock.MagicMock(
            side_effect=[
                exc.ActionException(),  # Mock task 1.0 error for run.
                'Task 1.1',             # Mock task 1.1 success for run.
                exc.ActionException(),  # Mock task 1.2 error for run.
                exc.ActionException(),  # Mock task 1.0 error for 1st rerun.
                exc.ActionException(),  # Mock task 1.2 error for 1st rerun.
                exc.ActionException(),  # Mock task 1.0 error for 2nd run.
                'Task 1.1',             # Mock task 1.1 success for 2nd run.
                exc.ActionException(),  # Mock task 1.2 error for 2nd run.
                exc.ActionException(),  # Mock task 1.0 error for 3rd rerun.
                exc.ActionException(),  # Mock task 1.2 error for 3rd rerun.
                'Task 1.0',             # Mock task 1.0 success for 4th rerun.
                'Task 1.2',             # Mock task 1.2 success for 4th rerun.
                'Task 2'                # Mock task 2 success.
            ]
        )
    )
    def test_multiple_reruns_with_items(self):
        wb_service.create_workbook_v2(WITH_ITEMS_WORKBOOK)

        # Run workflow and fail task.
        wf_ex = self.engine.start_workflow('wb3.wf1', {})

        self.await_workflow_error(wf_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.ERROR, wf_ex.state)
        self.assertIsNotNone(wf_ex.state_info)
        self.assertEqual(1, len(wf_ex.task_executions))

        task_1_ex = self._assert_single_item(wf_ex.task_executions, name='t1')

        self.await_task_error(task_1_ex.id)

        self.assertIsNotNone(task_1_ex.state_info)

        task_1_action_exs = db_api.get_action_executions(
            task_execution_id=task_1_ex.id
        )

        self.assertEqual(3, len(task_1_action_exs))

        # Resume workflow and re-run failed task. Re-run #1 with no reset.
        wf_ex = self.engine.rerun_workflow(task_1_ex.id, reset=False)

        self.assertEqual(states.RUNNING, wf_ex.state)
        self.assertIsNone(wf_ex.state_info)

        self.await_workflow_error(wf_ex.id, delay=10)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.ERROR, wf_ex.state)
        self.assertIsNotNone(wf_ex.state_info)

        task_1_action_exs = db_api.get_action_executions(
            task_execution_id=task_1_ex.id
        )

        self.assertEqual(5, len(task_1_action_exs))

        # Resume workflow and re-run failed task. Re-run #2 with reset.
        self.engine.rerun_workflow(task_1_ex.id, reset=True)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.RUNNING, wf_ex.state)
        self.assertIsNone(wf_ex.state_info)

        self.await_workflow_error(wf_ex.id, delay=10)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.ERROR, wf_ex.state)
        self.assertIsNotNone(wf_ex.state_info)

        task_1_action_exs = db_api.get_action_executions(
            task_execution_id=task_1_ex.id
        )

        self.assertEqual(8, len(task_1_action_exs))

        # Resume workflow and re-run failed task. Re-run #3 with no reset.
        self.engine.rerun_workflow(task_1_ex.id, reset=False)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.RUNNING, wf_ex.state)
        self.assertIsNone(wf_ex.state_info)

        self.await_workflow_error(wf_ex.id, delay=10)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.ERROR, wf_ex.state)
        self.assertIsNotNone(wf_ex.state_info)

        task_1_action_exs = db_api.get_action_executions(
            task_execution_id=task_1_ex.id
        )

        self.assertEqual(10, len(task_1_action_exs))

        # Resume workflow and re-run failed task. Re-run #4 with no reset.
        self.engine.rerun_workflow(task_1_ex.id, reset=False)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.RUNNING, wf_ex.state)
        self.assertIsNone(wf_ex.state_info)

        self.await_workflow_success(wf_ex.id, delay=10)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.SUCCESS, wf_ex.state)
        self.assertIsNone(wf_ex.state_info)
        self.assertEqual(2, len(wf_ex.task_executions))

        task_1_ex = self._assert_single_item(wf_ex.task_executions, name='t1')
        task_2_ex = self._assert_single_item(wf_ex.task_executions, name='t2')

        # Check action executions of task 1.
        self.assertEqual(states.SUCCESS, task_1_ex.state)
        self.assertIsNone(task_1_ex.state_info)

        task_1_action_exs = db_api.get_action_executions(
            task_execution_id=task_1_ex.id
        )

        # The single action execution that succeeded should not re-run.
        self.assertEqual(12, len(task_1_action_exs))

        self.assertListEqual(['Task 1.0', 'Task 1.1', 'Task 1.2'],
                             task_1_ex.published.get('v1'))

        # Check action executions of task 2.
        self.assertEqual(states.SUCCESS, task_2_ex.state)

        task_2_action_exs = db_api.get_action_executions(
            task_execution_id=task_2_ex.id
        )

        self.assertEqual(1, len(task_2_action_exs))

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
    def test_rerun_subflow(self):
        wb_service.create_workbook_v2(SUBFLOW_WORKBOOK)

        # Run workflow and fail task.
        wf_ex = self.engine.start_workflow('wb1.wf1', {})

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

        task_2_action_exs = db_api.get_workflow_executions(
            task_execution_id=task_2_ex.id
        )

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
    def test_rerun_subflow_task(self):
        wb_service.create_workbook_v2(SUBFLOW_WORKBOOK)

        # Run workflow and fail task.
        wf_ex = self.engine.start_workflow('wb1.wf1', {})

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

        # Get subworkflow and related task
        sub_wf_exs = db_api.get_workflow_executions(
            task_execution_id=task_2_ex.id
        )

        sub_wf_ex = sub_wf_exs[0]

        self.assertEqual(states.ERROR, sub_wf_ex.state)
        self.assertIsNotNone(sub_wf_ex.state_info)
        self.assertEqual(1, len(sub_wf_ex.task_executions))

        sub_wf_task_ex = self._assert_single_item(
            sub_wf_ex.task_executions,
            name='wf2_t1'
        )

        self.assertEqual(states.ERROR, sub_wf_task_ex.state)
        self.assertIsNotNone(sub_wf_task_ex.state_info)

        # Resume workflow and re-run failed subworkflow task.
        self.engine.rerun_workflow(sub_wf_task_ex.id)

        sub_wf_ex = db_api.get_workflow_execution(sub_wf_ex.id)

        self.assertEqual(states.RUNNING, sub_wf_ex.state)
        self.assertIsNone(sub_wf_ex.state_info)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.RUNNING, wf_ex.state)
        self.assertIsNone(wf_ex.state_info)

        # Wait for the subworkflow to succeed.
        self.await_workflow_success(sub_wf_ex.id)

        sub_wf_ex = db_api.get_workflow_execution(sub_wf_ex.id)

        self.assertEqual(states.SUCCESS, sub_wf_ex.state)
        self.assertIsNone(sub_wf_ex.state_info)
        self.assertEqual(1, len(sub_wf_ex.task_executions))

        sub_wf_task_ex = self._assert_single_item(
            sub_wf_ex.task_executions,
            name='wf2_t1'
        )

        # Check action executions of subworkflow task.
        self.assertEqual(states.SUCCESS, sub_wf_task_ex.state)
        self.assertIsNone(sub_wf_task_ex.state_info)

        sub_wf_task_ex_action_exs = db_api.get_action_executions(
            task_execution_id=sub_wf_task_ex.id)

        self.assertEqual(2, len(sub_wf_task_ex_action_exs))
        self.assertEqual(states.ERROR, sub_wf_task_ex_action_exs[0].state)
        self.assertEqual(states.SUCCESS, sub_wf_task_ex_action_exs[1].state)

        # Wait for the main workflow to succeed.
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

        task_2_action_exs = db_api.get_workflow_executions(
            task_execution_id=task_2_ex.id
        )

        self.assertEqual(1, len(task_2_action_exs))
        self.assertEqual(states.SUCCESS, task_1_action_exs[0].state)

        # Check action executions of task 3.
        self.assertEqual(states.SUCCESS, task_3_ex.state)

        task_3_action_exs = db_api.get_action_executions(
            task_execution_id=task_3_ex.id)

        self.assertEqual(1, len(task_3_action_exs))
        self.assertEqual(states.SUCCESS, task_3_action_exs[0].state)
