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

from unittest import mock

from oslo_config import cfg

from mistral.actions import std_actions
from mistral.db.v2 import api as db_api
from mistral.engine import default_engine
from mistral import exceptions as exc
from mistral.services import workbooks as wb_service
from mistral.services import workflows as wf_service
from mistral.tests.unit.engine import base
from mistral.workflow import direct_workflow as d_wf
from mistral.workflow import states
from mistral_lib import actions as ml_actions

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

WITH_ITEMS_WORKBOOK_ENV_ITEMS = """
---
version: '2.0'

name: wb3

workflows:
  wf1:
    type: direct

    tasks:
      t1:
        with-items: i in <% env().items %>
        action: std.echo output="<% $.i %>"
"""

JOIN_WORKBOOK = """
---
version: '2.0'

name: wb1

workflows:
  wf1:
    type: direct

    tasks:
      t0:
        action: std.noop
        on-success:
          - t3
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

ON_COMPLETE_WORKBOOK = """
---
version: '2.0'

name: wb1

workflows:
  wf1:
    type: direct

    tasks:
      t1:
        action: std.echo output="Task 1"
        on-complete:
          - t2
      t2:
        action: std.echo output="Task 2"
        on-complete:
          - t3
      t3:
        action: std.echo output="Task 3"
        on-success:
          - t4
      t4:
        action: std.echo output="Task 4"
"""

ON_COMPLETE_WITH_ITEMS_WORKBOOK = """
---
version: '2.0'

name: wb1

workflows:
  wf1:
    type: direct

    tasks:
      t1:
        action: std.echo output="Task 1"
        publish:
          items: [1, 2, 3]
        publish-on-error:
          items: [1]
        on-complete:
          - t2
      t2:
        with-items: i in <% $.items %>
        action: std.echo output="<% $.i %>"
"""

ON_COMPLETE_TWICE_WORKBOOK = """
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
        on-complete:
          - t2
      t2:
        action: std.echo output="Task 2"
"""

ON_COMPLETE_WITH_ITEMS_SHRINK_WORKBOOK = """
---
version: '2.0'

name: wb1

workflows:
  wf1:
    type: direct

    tasks:
      t1:
        action: std.echo output="Task 1"
        publish:
          items: [1]
        publish-on-error:
          items: [1, 2, 3]
        on-complete:
          - t2
      t2:
        with-items: i in <% $.items %>
        action: std.echo output="<% $.i %>"
"""

ON_COMPLETE_PAUSE_WORKBOOK = """
---
version: '2.0'

name: wb1

workflows:
  wf1:
    type: direct

    tasks:
      t1:
        action: std.echo output="Task 1"
        on-complete:
          - pause
          - t2
      t2:
        action: std.echo output="Task 2"
"""

ON_COMPLETE_PUBLISH_ON_ERROR_WORKBOOK = """
---
version: '2.0'

name: wb1

workflows:
  wf1:
    type: direct

    tasks:
      t1:
        action: std.echo output="Task 1"
        publish:
          ok: 1
        publish-on-error:
          err: 1
        on-complete:
          - t2
      t2:
        action: std.echo output="Task 2"
"""

ON_COMPLETE_ASYNC_WORKBOOK = """
---
version: '2.0'

name: wb1

workflows:
  wf1:
    type: direct

    tasks:
      t1:
        action: std.echo output="Task 1"
        on-complete:
          - t2
      t2:
        action: std.async_noop
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


JOIN_LOOP_WF = """---
version: '2.0'

wf:
  vars:
    cnt: 0

  tasks:
    init:
      action: std.noop
      on-success: task1

    task1:
      action: std.noop
      publish:
        cnt: <% $.cnt + 1 %>
      on-success: [task2, task3]

    task2:
      action: std.noop
      on-success: join_task

    task3:
      action: std.noop
      on-success: join_task

    join_task:
      join: all
      action: JOIN_ACTION
      JOIN_TRANSITION: side

    side:
      action: std.echo output=<% $.cnt %>
      on-error:
        - task1: <% $.cnt < 2 %>
"""


class DirectWorkflowRerunTest(base.EngineTestCase):
    @mock.patch.object(
        std_actions.EchoAction,
        'run',
        mock.MagicMock(
            side_effect=[
                'Task 1',  # Mock task1 success for initial run.
                exc.ActionException(),  # Mock task2 exception for initial run.
                'Task 2',  # Mock task2 success for rerun.
                'Task 3',  # Mock task3 success.
            ]
        ),
    )
    def test_rerun(self):
        wb_service.create_workbook_v2(SIMPLE_WORKBOOK)

        # Run workflow and fail task.
        wf_ex = self.engine.start_workflow('wb1.wf1')

        self.await_workflow_error(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_execs = wf_ex.task_executions

        self.assertEqual(states.ERROR, wf_ex.state)
        self.assertIsNotNone(wf_ex.state_info)
        self.assertEqual(2, len(task_execs))

        task_1_ex = self._assert_single_item(task_execs, name='t1')
        task_2_ex = self._assert_single_item(task_execs, name='t2')

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
        # Check there is exactly 1 action in Success and 1 in error state.
        # Order doesn't matter.
        self._assert_single_item(task_2_action_exs, state=states.SUCCESS)
        self._assert_single_item(task_2_action_exs, state=states.ERROR)

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
                'Task 10',  # Mock task10 success for first run.
                exc.ActionException(),  # Mock task21 exception for first run.
                'Task 21',  # Mock task21 success for rerun.
                'Task 22',  # Mock task22 success.
                'Task 30',  # Mock task30 success.
            ]
        ),
    )
    def test_rerun_diff_env_vars(self):
        wb_service.create_workbook_v2(SIMPLE_WORKBOOK_DIFF_ENV_VAR)

        # Initial environment variables for the workflow execution.
        env = {
            'var1': 'fee fi fo fum',
            'var2': 'mirror mirror',
            'var3': 'heigh-ho heigh-ho',
        }

        # Run workflow and fail task.
        wf_ex = self.engine.start_workflow('wb1.wf1', env=env)

        self.await_workflow_error(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
            task_execs = wf_ex.task_executions

            self.assertEqual(states.ERROR, wf_ex.state)
            self.assertIsNotNone(wf_ex.state_info)
            self.assertEqual(3, len(task_execs))
            self.assertDictEqual(env, wf_ex.params['env'])

        task_10_ex = self._assert_single_item(task_execs, name='t10')
        task_21_ex = self._assert_single_item(task_execs, name='t21')
        task_30_ex = self._assert_single_item(task_execs, name='t30')

        self.assertEqual(states.SUCCESS, task_10_ex.state)
        self.assertEqual(states.ERROR, task_21_ex.state)
        self.assertIsNotNone(task_21_ex.state_info)
        self.assertEqual(states.ERROR, task_30_ex.state)

        # Update env in workflow execution with the following.
        updated_env = {'var1': 'Task 21', 'var2': 'Task 22', 'var3': 'Task 30'}

        # Resume workflow and re-run failed task.
        wf_ex = self.engine.rerun_workflow(task_21_ex.id, env=updated_env)

        self.assertEqual(states.RUNNING, wf_ex.state)
        self.assertIsNone(wf_ex.state_info)
        self.assertDictEqual(updated_env, wf_ex.params['env'])

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
            {'output': 'Task 10'}, task_10_action_exs[0].input
        )

        # Check action executions of task 21.
        self.assertEqual(states.SUCCESS, task_21_ex.state)
        self.assertIsNone(task_21_ex.state_info)

        task_21_action_exs = db_api.get_action_executions(
            task_execution_id=task_21_ex.id
        )

        self.assertEqual(2, len(task_21_action_exs))
        # Check there is exactly 1 action in Success and 1 in error state.
        # Order doesn't matter.
        task_21_action_exs_1 = self._assert_single_item(
            task_21_action_exs, state=states.ERROR
        )
        task_21_action_exs_2 = self._assert_single_item(
            task_21_action_exs, state=states.SUCCESS
        )

        self.assertDictEqual(
            {'output': env['var1']}, task_21_action_exs_1.input
        )

        self.assertDictEqual(
            {'output': updated_env['var1']}, task_21_action_exs_2.input
        )

        # Check action executions of task 22.
        self.assertEqual(states.SUCCESS, task_22_ex.state)

        task_22_action_exs = db_api.get_action_executions(
            task_execution_id=task_22_ex.id
        )

        self.assertEqual(1, len(task_22_action_exs))
        self.assertEqual(states.SUCCESS, task_22_action_exs[0].state)

        self.assertDictEqual(
            {'output': updated_env['var2']}, task_22_action_exs[0].input
        )

        # Check action executions of task 30.
        self.assertEqual(states.SUCCESS, task_30_ex.state)

        task_30_action_exs = db_api.get_action_executions(
            task_execution_id=task_30_ex.id
        )

        self.assertEqual(1, len(task_30_action_exs))
        self.assertEqual(states.SUCCESS, task_30_action_exs[0].state)

        self.assertDictEqual(
            {'output': updated_env['var3']}, task_30_action_exs[0].input
        )

    @mock.patch.object(
        std_actions.EchoAction,
        'run',
        mock.MagicMock(
            side_effect=[
                exc.ActionException(),  # Mock task1 exception for initial run.
                'Task 1.1',  # Mock task1 success for initial run.
                exc.ActionException(),  # Mock task1 exception for initial run.
                'Task 1.0',  # Mock task1 success for rerun.
                'Task 1.2',  # Mock task1 success for rerun.
                'Task 2',  # Mock task2 success.
            ]
        ),
    )
    def test_rerun_with_items(self):
        wb_service.create_workbook_v2(WITH_ITEMS_WORKBOOK)

        # Run workflow and fail task.
        wf_ex = self.engine.start_workflow('wb3.wf1')

        self.await_workflow_error(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_execs = wf_ex.task_executions

        self.assertEqual(states.ERROR, wf_ex.state)
        self.assertIsNotNone(wf_ex.state_info)

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

        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_execs = wf_ex.task_executions

        self.assertEqual(states.SUCCESS, wf_ex.state)
        self.assertIsNone(wf_ex.state_info)

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
            ['Task 1.0', 'Task 1.1', 'Task 1.2'], task_1_ex.published.get('v1')
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
                exc.ActionException(),  # Mock task1 exception for initial run.
                'Task 1.1',  # Mock task1 success for initial run.
                exc.ActionException(),  # Mock task1 exception for initial run.
                'Task 1.0',  # Mock task1 success for rerun.
                'Task 1.2',  # Mock task1 success for rerun.
                'Task 2',  # Mock task2 success.
            ]
        ),
    )
    def test_rerun_with_items_diff_env_vars(self):
        wb_service.create_workbook_v2(WITH_ITEMS_WORKBOOK_DIFF_ENV_VAR)

        # Initial environment variables for the workflow execution.
        env = {'var1': 'fee fi fo fum'}

        # Run workflow and fail task.
        wf_ex = self.engine.start_workflow('wb3.wf1', env=env)

        self.await_workflow_error(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_execs = wf_ex.task_executions

        self.assertEqual(states.ERROR, wf_ex.state)
        self.assertIsNotNone(wf_ex.state_info)
        self.assertEqual(1, len(task_execs))

        task_1_ex = self._assert_single_item(task_execs, name='t1')

        self.assertEqual(states.ERROR, task_1_ex.state)
        self.assertIsNotNone(task_1_ex.state_info)

        task_1_action_exs = db_api.get_action_executions(
            task_execution_id=task_1_ex.id
        )

        self.assertEqual(3, len(task_1_action_exs))

        # Update env in workflow execution with the following.
        updated_env = {'var1': 'foobar'}

        # Resume workflow and re-run failed task.
        self.engine.rerun_workflow(task_1_ex.id, reset=False, env=updated_env)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.RUNNING, wf_ex.state)
        self.assertIsNone(wf_ex.state_info)

        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_execs = wf_ex.task_executions

        self.assertEqual(states.SUCCESS, wf_ex.state)
        self.assertIsNone(wf_ex.state_info)
        self.assertEqual(2, len(task_execs))

        task_1_ex = self._assert_single_item(task_execs, name='t1')
        task_2_ex = self._assert_single_item(task_execs, name='t2')

        # Check action executions of task 1.
        self.assertEqual(states.SUCCESS, task_1_ex.state)
        self.assertIsNone(task_1_ex.state_info)

        task_1_action_exs = db_api.get_action_executions(
            task_execution_id=task_1_ex.id
        )

        expected_inputs = [
            'Task 1.0 [%s]' % env['var1'],  # Task 1 item 0 (error).
            'Task 1.1 [%s]' % env['var1'],  # Task 1 item 1.
            'Task 1.2 [%s]' % env['var1'],  # Task 1 item 2 (error).
            'Task 1.0 [%s]' % updated_env['var1'],  # Task 1 item 0 (rerun).
            'Task 1.2 [%s]' % updated_env['var1'],  # Task 1 item 2 (rerun).
        ]

        # Assert that every expected input is in actual task input.
        for action_ex in task_1_action_exs:
            self.assertIn(action_ex.input['output'], expected_inputs)

        # Assert that there was same number of unique inputs as action execs.
        self.assertEqual(
            len(task_1_action_exs),
            len(
                set(
                    [
                        action_ex.input['output']
                        for action_ex in task_1_action_exs
                    ]
                )
            ),
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
                'a',  # Mock task1 success for initial run.
                'b',  # Mock task1 success for initial run.
                exc.ActionException(),  # Mock task1 exception for initial run.
                'a',  # Mock task1 success for rerun.
            ]
        ),
    )
    def test_rerun_with_items_less_items(self):
        wb_service.create_workbook_v2(WITH_ITEMS_WORKBOOK_ENV_ITEMS)

        wf_ex = self.engine.start_workflow(
            'wb3.wf1', env={'items': ['a', 'b', 'c']}
        )

        self.await_workflow_error(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_execs = wf_ex.task_executions

        task_1_ex = self._assert_single_item(task_execs, name='t1')

        self.engine.rerun_workflow(task_1_ex.id, env={'items': ['a']})

        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_execs = wf_ex.task_executions

        self.assertEqual(1, len(task_execs))

        task_1_ex = self._assert_single_item(
            task_execs, name='t1', state=states.SUCCESS
        )

        task_1_action_exs = db_api.get_action_executions(
            task_execution_id=task_1_ex.id, accepted=True
        )

        self.assertEqual(1, len(task_1_action_exs))
        self.assertEqual(0, task_1_action_exs[0].runtime_context['index'])

    @mock.patch.object(
        std_actions.EchoAction,
        'run',
        mock.MagicMock(
            side_effect=[
                'Task 1',  # Mock task1 success for initial run.
                'Task 2',  # Mock task2 success for initial run.
                exc.ActionException(),  # Mock task3 exception for initial run.
                'Task 3',  # Mock task3 success for rerun.
            ]
        ),
    )
    def test_rerun_on_join_task(self):
        wb_service.create_workbook_v2(JOIN_WORKBOOK)

        # Run workflow and fail task.
        wf_ex = self.engine.start_workflow('wb1.wf1')

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.await_workflow_error(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_execs = wf_ex.task_executions

        self.assertEqual(states.ERROR, wf_ex.state)
        self.assertIsNotNone(wf_ex.state_info)
        self.assertEqual(4, len(task_execs))

        task_0_ex = self._assert_single_item(task_execs, name='t0')
        task_1_ex = self._assert_single_item(task_execs, name='t1')
        task_2_ex = self._assert_single_item(task_execs, name='t2')
        task_3_ex = self._assert_single_item(task_execs, name='t3')

        self.assertEqual(states.SUCCESS, task_0_ex.state)
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

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_execs = wf_ex.task_executions

        self.assertEqual(states.SUCCESS, wf_ex.state)
        self.assertIsNone(wf_ex.state_info)
        self.assertEqual(4, len(task_execs))

        task_0_ex = self._assert_single_item(task_execs, name='t0')
        task_1_ex = self._assert_single_item(task_execs, name='t1')
        task_2_ex = self._assert_single_item(task_execs, name='t2')
        task_3_ex = self._assert_single_item(task_execs, name='t3')

        # Check action executions of task 0.
        self.assertEqual(states.SUCCESS, task_0_ex.state)

        task_0_action_exs = db_api.get_action_executions(
            task_execution_id=task_0_ex.id
        )

        self.assertEqual(1, len(task_0_action_exs))
        self.assertEqual(states.SUCCESS, task_0_action_exs[0].state)

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
            task_execution_id=task_3_ex.id
        )

        self.assertEqual(2, len(task_3_action_exs))
        # Check there is exactly 1 action in Success and 1 in error state.
        # Order doesn't matter.
        self._assert_single_item(task_3_action_exs, state=states.SUCCESS)
        self._assert_single_item(task_3_action_exs, state=states.ERROR)

    @mock.patch.object(
        std_actions.EchoAction,
        'run',
        mock.MagicMock(
            side_effect=[
                exc.ActionException(),  # Mock task1 exception for initial run.
                exc.ActionException(),  # Mock task2 exception for initial run.
                'Task 1',  # Mock task1 success for rerun.
                'Task 2',  # Mock task2 success for rerun.
                'Task 3',  # Mock task3 success.
            ]
        ),
    )
    def test_rerun_join_with_branch_errors(self):
        wb_service.create_workbook_v2(JOIN_WORKBOOK)

        # Run workflow and fail task.
        wf_ex = self.engine.start_workflow('wb1.wf1')

        self.await_workflow_error(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
            task_execs = wf_ex.task_executions

        # NOTE(arnaud): we used to tests the tasks results here but we can't
        # be sure about which one is failing, which one has succeeded or is
        # still in waiting state.
        # What we know is that, when a task fails, and if there is no condition
        # to continue the worflow (like on-complete), then the workflow will
        # fail and all other tasks may be blocked in WAITING state.

        # Resume workflow and re-run t1/t2 failed tasks
        # t3 will be resumed automatically by t1/t2, so no need to resume it
        for task_exec in task_execs:
            if task_exec.state == states.ERROR and task_exec.name in [
                't1',
                't2',
            ]:
                wf_ex = self.engine.rerun_workflow(task_exec.id)

        # This is prone to race conditions, but let's see if that works
        self.await_workflow_running(wf_ex.id)
        self.assertIsNone(wf_ex.state_info)

        # Now wait for the workflow to finish
        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
            task_execs = wf_ex.task_executions

        self.assertEqual(states.SUCCESS, wf_ex.state)
        self.assertIsNone(wf_ex.state_info)
        self.assertEqual(4, len(task_execs))

        task_0_ex = self._assert_single_item(task_execs, name='t0')
        task_1_ex = self._assert_single_item(task_execs, name='t1')
        task_2_ex = self._assert_single_item(task_execs, name='t2')
        task_3_ex = self._assert_single_item(task_execs, name='t3')

        # Check action executions of task 0.
        self.assertEqual(states.SUCCESS, task_0_ex.state)
        self.assertIsNone(task_0_ex.state_info)

        task_0_action_exs = db_api.get_action_executions(
            task_execution_id=task_0_ex.id
        )

        self.assertEqual(1, len(task_0_action_exs))
        # Check action executions of task 1.
        self.assertEqual(states.SUCCESS, task_1_ex.state)
        self.assertIsNone(task_1_ex.state_info)

        task_1_action_exs = db_api.get_action_executions(
            task_execution_id=task_1_ex.id
        )

        self.assertEqual(2, len(task_1_action_exs))
        # Check there is exactly 1 action in Success and 1 in error state.
        # Order doesn't matter.
        self._assert_single_item(task_1_action_exs, state=states.SUCCESS)
        self._assert_single_item(task_1_action_exs, state=states.ERROR)

        # Check action executions of task 2.
        self.assertEqual(states.SUCCESS, task_2_ex.state)
        self.assertIsNone(task_2_ex.state_info)

        task_2_action_exs = db_api.get_action_executions(
            task_execution_id=task_2_ex.id
        )

        self.assertEqual(2, len(task_2_action_exs))
        # Check there is exactly 1 action in Success and 1 in error state.
        # Order doesn't matter.
        self._assert_single_item(task_2_action_exs, state=states.SUCCESS)
        self._assert_single_item(task_2_action_exs, state=states.ERROR)

        # Check there is exactly 1 action execution of task 3.
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
                'Task 1',  # Mock task1 success for initial run.
                exc.ActionException(),  # Mock task2 exception for initial run.
                exc.ActionException(),  # Mock task3 exception for initial run.
                'Task 2',  # Mock task2 success for rerun.
                'Task 3',  # Mock task3 success for rerun.
                'Task 4',  # Mock task4 success.
            ]
        ),
    )
    def test_rerun_on_complete_task(self):
        wb_service.create_workbook_v2(ON_COMPLETE_WORKBOOK)

        wf_ex = self.engine.start_workflow('wb1.wf1')

        self.await_workflow_error(wf_ex.id)

        task_execs = self._task_execs(wf_ex.id)

        self.assertEqual(3, len(task_execs))

        task_2_ex = self._assert_single_item(task_execs, name='t2')
        task_3_ex = self._assert_single_item(task_execs, name='t3')

        self.assertEqual(states.ERROR, task_2_ex.state)
        self.assertEqual(states.ERROR, task_3_ex.state)

        self.engine.rerun_workflow(task_2_ex.id)

        self.await_workflow_success(wf_ex.id)

        task_execs = self._task_execs(wf_ex.id)

        self.assertEqual(4, len(task_execs))

        for name in ('t1', 't2', 't3', 't4'):
            t_ex = self._assert_single_item(task_execs, name=name)

            self.assertEqual(states.SUCCESS, t_ex.state)

        task_3_action_exs = db_api.get_action_executions(
            task_execution_id=task_3_ex.id
        )

        self.assertEqual(2, len(task_3_action_exs))

    @mock.patch.object(
        std_actions.EchoAction,
        'run',
        mock.MagicMock(
            side_effect=[
                exc.ActionException(),  # Mock task1 exception for initial run.
                exc.ActionException(),  # Mock task2.0 exception.
                'Task 1',  # Mock task1 success for rerun.
                '1',  # Mock task2.0 success for rerun.
                '2',  # Mock task2.1 success for rerun.
                '3',  # Mock task2.2 success for rerun.
            ]
        ),
    )
    def test_rerun_on_complete_with_items_task(self):
        wb_service.create_workbook_v2(ON_COMPLETE_WITH_ITEMS_WORKBOOK)

        wf_ex = self.engine.start_workflow('wb1.wf1')

        self.await_workflow_error(wf_ex.id)

        task_execs = self._task_execs(wf_ex.id)

        task_1_ex = self._assert_single_item(task_execs, name='t1')

        self.engine.rerun_workflow(task_1_ex.id)

        self.await_workflow_success(wf_ex.id)

        task_execs = self._task_execs(wf_ex.id)

        self.assertEqual(2, len(task_execs))

        task_2_ex = self._assert_single_item(
            task_execs, name='t2', state=states.SUCCESS
        )

        task_2_action_exs = db_api.get_action_executions(
            task_execution_id=task_2_ex.id, accepted=True
        )

        self.assertEqual(3, len(task_2_action_exs))

    @mock.patch.object(
        std_actions.EchoAction,
        'run',
        mock.MagicMock(
            side_effect=[
                exc.ActionException(),  # Mock task1 exception for initial run.
                exc.ActionException(),  # Mock task2.0 exception.
                '2',  # Mock task2.1 success.
                '3',  # Mock task2.2 success.
                'Task 1',  # Mock task1 success for rerun.
                '1',  # Mock task2.0 success for rerun.
            ]
        ),
    )
    def test_rerun_on_complete_with_less_items(self):
        wb_service.create_workbook_v2(ON_COMPLETE_WITH_ITEMS_SHRINK_WORKBOOK)

        wf_ex = self.engine.start_workflow('wb1.wf1')

        self.await_workflow_error(wf_ex.id)

        task_execs = self._task_execs(wf_ex.id)

        task_1_ex = self._assert_single_item(task_execs, name='t1')

        self.engine.rerun_workflow(task_1_ex.id)

        self.await_workflow_success(wf_ex.id)

        task_execs = self._task_execs(wf_ex.id)

        self.assertEqual(2, len(task_execs))

        task_2_ex = self._assert_single_item(
            task_execs, name='t2', state=states.SUCCESS
        )

        task_2_action_exs = db_api.get_action_executions(
            task_execution_id=task_2_ex.id, accepted=True
        )

        self.assertEqual(1, len(task_2_action_exs))

    @mock.patch.object(
        std_actions.EchoAction,
        'run',
        mock.MagicMock(
            side_effect=[
                exc.ActionException(),  # Mock task1 exception for initial run.
                exc.ActionException(),  # Mock task2 exception for initial run.
                'Task 1',  # Mock task1 success for rerun.
                'Task 2',  # Mock task2 success for rerun.
            ]
        ),
    )
    def test_rerun_on_complete_task_with_pause(self):
        wb_service.create_workbook_v2(ON_COMPLETE_PAUSE_WORKBOOK)

        wf_ex = self.engine.start_workflow('wb1.wf1')

        self.await_workflow_paused(wf_ex.id)

        self.engine.resume_workflow(wf_ex.id)

        self.await_workflow_error(wf_ex.id)

        task_execs = self._task_execs(wf_ex.id)

        task_1_ex = self._assert_single_item(task_execs, name='t1')
        task_2_ex = self._assert_single_item(task_execs, name='t2')

        self.engine.rerun_workflow(task_1_ex.id)

        self.await_workflow_paused(wf_ex.id)

        self.engine.resume_workflow(wf_ex.id)

        self.await_workflow_success(wf_ex.id)

        task_execs = self._task_execs(wf_ex.id)

        self.assertEqual(2, len(task_execs))

        t_ex = self._assert_single_item(task_execs, name='t2')

        self.assertEqual(task_2_ex.id, t_ex.id)
        self.assertEqual(states.SUCCESS, t_ex.state)

    @mock.patch.object(
        std_actions.EchoAction,
        'run',
        mock.MagicMock(
            side_effect=[
                exc.ActionException(),  # Mock task1 exception for initial run.
                exc.ActionException(),  # Mock task2 exception for initial run.
                'Task 1',  # Mock task1 success for rerun.
                'Task 2',  # Mock task2 success for rerun.
            ]
        ),
    )
    def test_rerun_on_complete_task_refreshes_context(self):
        wb_service.create_workbook_v2(ON_COMPLETE_PUBLISH_ON_ERROR_WORKBOOK)

        wf_ex = self.engine.start_workflow('wb1.wf1')

        self.await_workflow_error(wf_ex.id)

        task_execs = self._task_execs(wf_ex.id)

        task_1_ex = self._assert_single_item(task_execs, name='t1')

        self.engine.rerun_workflow(task_1_ex.id)

        self.await_workflow_success(wf_ex.id)

        task_execs = self._task_execs(wf_ex.id)

        task_2_ex = self._assert_single_item(task_execs, name='t2')

        self.assertNotIn('err', task_2_ex.in_context)
        self.assertIn('ok', task_2_ex.in_context)

    @mock.patch.object(
        std_actions.EchoAction,
        'run',
        mock.MagicMock(
            side_effect=[
                exc.ActionException(),  # Mock task1 exception for initial run.
                exc.ActionException(),  # Mock task2 exception for initial run.
                'Task 1',  # Mock task1 success for rerun.
                'Task 2',  # Mock task2 success for 1st trigger.
                'Task 2',  # Mock task2 success for 2nd trigger.
            ]
        ),
    )
    def test_rerun_task_with_two_transitions_to_failed_task(self):
        wb_service.create_workbook_v2(ON_COMPLETE_TWICE_WORKBOOK)

        wf_ex = self.engine.start_workflow('wb1.wf1')

        self.await_workflow_error(wf_ex.id)

        task_execs = self._task_execs(wf_ex.id)

        task_1_ex = self._assert_single_item(task_execs, name='t1')
        task_2_ex = self._assert_single_item(task_execs, name='t2')

        self.engine.rerun_workflow(task_1_ex.id)

        self.await_workflow_success(wf_ex.id)

        task_execs = self._task_execs(wf_ex.id)

        task_2_execs = [t for t in task_execs if t.name == 't2']

        self.assertEqual(2, len(task_2_execs))
        self.assertIn(task_2_ex.id, [t.id for t in task_2_execs])

        for t_ex in task_2_execs:
            self.assertEqual(states.SUCCESS, t_ex.state)

    @mock.patch.object(
        std_actions.EchoAction,
        'run',
        mock.MagicMock(
            side_effect=[
                exc.ActionException(),  # Mock task1 exception for initial run.
                'Task 1',  # Mock task1 success for rerun.
            ]
        ),
    )
    def test_rerun_on_complete_task_with_cancelled_downstream(self):
        wb_service.create_workbook_v2(ON_COMPLETE_ASYNC_WORKBOOK)

        wf_ex = self.engine.start_workflow('wb1.wf1')

        task_execs = self._task_execs(wf_ex.id)

        task_1_ex = self._assert_single_item(task_execs, name='t1')

        self.await_task_error(task_1_ex.id)

        task_execs = self._task_execs(wf_ex.id)

        task_2_ex = self._assert_single_item(task_execs, name='t2')

        self.await_task_running(task_2_ex.id)

        action_ex = db_api.get_action_executions(
            task_execution_id=task_2_ex.id
        )[0]

        self.engine.on_action_complete(
            action_ex.id, ml_actions.Result(cancel=True)
        )

        self.await_workflow_cancelled(wf_ex.id)

        self.engine.rerun_workflow(task_1_ex.id)

        self.await_task_running(task_2_ex.id)

        action_ex = db_api.get_action_executions(
            task_execution_id=task_2_ex.id, state=states.RUNNING
        )[0]

        self.engine.on_action_complete(action_ex.id, ml_actions.Result())

        self.await_workflow_success(wf_ex.id)

        task_execs = self._task_execs(wf_ex.id)

        self.assertEqual(2, len(task_execs))

        t_ex = self._assert_single_item(task_execs, name='t2')

        self.assertEqual(task_2_ex.id, t_ex.id)
        self.assertEqual(states.SUCCESS, t_ex.state)

    @mock.patch.object(
        std_actions.EchoAction,
        'run',
        mock.MagicMock(
            side_effect=[
                exc.ActionException(),  # Mock task 1.0 error for run.
                'Task 1.1',  # Mock task 1.1 success for run.
                exc.ActionException(),  # Mock task 1.2 error for run.
                exc.ActionException(),  # Mock task 1.0 error for 1st rerun.
                exc.ActionException(),  # Mock task 1.2 error for 1st rerun.
                exc.ActionException(),  # Mock task 1.0 error for 2nd run.
                'Task 1.1',  # Mock task 1.1 success for 2nd run.
                exc.ActionException(),  # Mock task 1.2 error for 2nd run.
                exc.ActionException(),  # Mock task 1.0 error for 3rd rerun.
                exc.ActionException(),  # Mock task 1.2 error for 3rd rerun.
                'Task 1.0',  # Mock task 1.0 success for 4th rerun.
                'Task 1.2',  # Mock task 1.2 success for 4th rerun.
                'Task 2',  # Mock task 2 success.
            ]
        ),
    )
    def test_multiple_reruns_with_items(self):
        wb_service.create_workbook_v2(WITH_ITEMS_WORKBOOK)

        # Run workflow and fail task.
        wf_ex = self.engine.start_workflow('wb3.wf1')

        self.await_workflow_error(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_execs = wf_ex.task_executions

        self.assertEqual(states.ERROR, wf_ex.state)
        self.assertIsNotNone(wf_ex.state_info)
        self.assertEqual(1, len(task_execs))

        task_1_ex = self._assert_single_item(task_execs, name='t1')

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

        self.await_workflow_error(wf_ex.id)

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

        self.await_workflow_error(wf_ex.id)

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

        self.await_workflow_error(wf_ex.id)

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

        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_execs = wf_ex.task_executions

        self.assertEqual(states.SUCCESS, wf_ex.state)
        self.assertIsNone(wf_ex.state_info)
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
        self.assertEqual(12, len(task_1_action_exs))

        self.assertListEqual(
            ['Task 1.0', 'Task 1.1', 'Task 1.2'], task_1_ex.published.get('v1')
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
                'Task 1',  # Mock task1 success for initial run.
                exc.ActionException(),  # Mock task2 exception for initial run.
                'Task 2',  # Mock task2 success for rerun.
                'Task 3',  # Mock task3 success.
            ]
        ),
    )
    def test_rerun_subflow(self):
        wb_service.create_workbook_v2(SUBFLOW_WORKBOOK)

        # Run workflow and fail task.
        wf_ex = self.engine.start_workflow('wb1.wf1')

        self.await_workflow_error(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_execs = wf_ex.task_executions

        self.assertEqual(states.ERROR, wf_ex.state)
        self.assertIsNotNone(wf_ex.state_info)
        self.assertEqual(2, len(task_execs))

        task_1_ex = self._assert_single_item(task_execs, name='t1')
        task_2_ex = self._assert_single_item(task_execs, name='t2')

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

        task_1_action_exs = db_api.get_action_executions(
            task_execution_id=task_1_ex.id
        )

        self.assertEqual(1, len(task_1_action_exs))
        self.assertEqual(states.SUCCESS, task_1_action_exs[0].state)

        # Check action executions of task 2.
        self.assertEqual(states.SUCCESS, task_2_ex.state)
        self.assertIsNone(task_2_ex.state_info)

        task_2_action_exs = db_api.get_workflow_executions(
            task_execution_id=task_2_ex.id
        )

        self.assertEqual(2, len(task_2_action_exs))
        # Check there is exactly 1 action in Success and 1 in error state.
        # Order doesn't matter.
        self._assert_single_item(task_2_action_exs, state=states.SUCCESS)
        self._assert_single_item(task_2_action_exs, state=states.ERROR)

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
                'Task 1',  # Mock task1 success for initial run.
                exc.ActionException(),  # Mock task2 exception for initial run.
                'Task 2',  # Mock task2 success for rerun.
                'Task 3',  # Mock task3 success.
            ]
        ),
    )
    def test_rerun_subflow_task(self):
        wb_service.create_workbook_v2(SUBFLOW_WORKBOOK)

        # Run workflow and fail task.
        wf_ex = self.engine.start_workflow('wb1.wf1')

        self.await_workflow_error(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_execs = wf_ex.task_executions

        self.assertEqual(states.ERROR, wf_ex.state)
        self.assertIsNotNone(wf_ex.state_info)
        self.assertEqual(2, len(task_execs))

        task_1_ex = self._assert_single_item(task_execs, name='t1')
        task_2_ex = self._assert_single_item(task_execs, name='t2')

        self.assertEqual(states.SUCCESS, task_1_ex.state)
        self.assertEqual(states.ERROR, task_2_ex.state)
        self.assertIsNotNone(task_2_ex.state_info)

        with db_api.transaction():
            # Get subworkflow and related task
            sub_wf_exs = db_api.get_workflow_executions(
                task_execution_id=task_2_ex.id
            )

            sub_wf_ex = sub_wf_exs[0]
            sub_wf_task_execs = sub_wf_ex.task_executions

        self.assertEqual(states.ERROR, sub_wf_ex.state)
        self.assertIsNotNone(sub_wf_ex.state_info)
        self.assertEqual(1, len(sub_wf_task_execs))

        sub_wf_task_ex = self._assert_single_item(
            sub_wf_task_execs, name='wf2_t1'
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

        with db_api.transaction():
            sub_wf_ex = db_api.get_workflow_execution(sub_wf_ex.id)

            sub_wf_task_execs = sub_wf_ex.task_executions

        self.assertEqual(states.SUCCESS, sub_wf_ex.state)
        self.assertIsNone(sub_wf_ex.state_info)
        self.assertEqual(1, len(sub_wf_task_execs))

        sub_wf_task_ex = self._assert_single_item(
            sub_wf_task_execs, name='wf2_t1'
        )

        # Check action executions of subworkflow task.
        self.assertEqual(states.SUCCESS, sub_wf_task_ex.state)
        self.assertIsNone(sub_wf_task_ex.state_info)

        sub_wf_task_ex_action_exs = db_api.get_action_executions(
            task_execution_id=sub_wf_task_ex.id
        )

        self.assertEqual(2, len(sub_wf_task_ex_action_exs))
        # Check there is exactly 1 action in Success and 1 in error state.
        # Order doesn't matter.
        self._assert_single_item(
            sub_wf_task_ex_action_exs, state=states.SUCCESS
        )
        self._assert_single_item(sub_wf_task_ex_action_exs, state=states.ERROR)

        # Wait for the main workflow to succeed.
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

        task_1_action_exs = db_api.get_action_executions(
            task_execution_id=task_1_ex.id
        )

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
            task_execution_id=task_3_ex.id
        )

        self.assertEqual(1, len(task_3_action_exs))
        self.assertEqual(states.SUCCESS, task_3_action_exs[0].state)

    def test_rerun_task_with_retry_policy(self):
        wf_service.create_workflows("""---
        version: '2.0'
        wf_fail:
          tasks:
            task1:
              action: std.fail
              retry:
                delay: 0
                count: 2""")

        wf_ex = self.engine.start_workflow("wf_fail")

        self.await_workflow_error(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_ex = self._assert_single_item(
                wf_ex.task_executions, name="task1"
            )
            action_executions = task_ex.executions

        self.assertEqual(states.ERROR, wf_ex.state)
        self.assertIsNotNone(wf_ex.state_info)
        self.assertEqual(3, len(action_executions))
        self.assertTrue(
            all(a.state == states.ERROR for a in action_executions)
        )

        self.engine.rerun_workflow(task_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.RUNNING, wf_ex.state)

        self.await_workflow_error(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_ex = self._assert_single_item(
                wf_ex.task_executions, name="task1"
            )
            action_executions = task_ex.executions

        self.assertEqual(states.ERROR, wf_ex.state)
        self.assertIsNotNone(wf_ex.state_info)
        self.assertEqual(6, len(action_executions))
        self.assertTrue(
            all(a.state == states.ERROR for a in action_executions)
        )

    @mock.patch.object(
        std_actions.NoOpAction,
        'run',
        mock.MagicMock(side_effect=[exc.ActionException(), 'Success']),
    )
    def test_rerun_sub_workflow(self):
        wf_service.create_workflows("""---
        version: '2.0'
        wf1:
          tasks:
            task1:
              workflow: wf2
        wf2:
          tasks:
            task2:
              workflow: wf3
        wf3:
          tasks:
            task3:
              action: std.noop""")

        # Run workflow and fail task.
        wf1_ex = self.engine.start_workflow('wf1')

        self.await_workflow_error(wf1_ex.id)

        with db_api.transaction():
            wf_exs = db_api.get_workflow_executions()
            task_exs = db_api.get_task_executions()

            self.assertEqual(
                3, len(wf_exs), 'The number of workflow executions'
            )
            self.assertEqual(3, len(task_exs), 'The number of task executions')

            for wf_ex in wf_exs:
                self.assertEqual(
                    states.ERROR,
                    wf_ex.state,
                    'The executions must fail the first time',
                )
            for task_ex in task_exs:
                self.assertEqual(
                    states.ERROR,
                    task_ex.state,
                    'The tasks must fail the first time',
                )

            wf3_ex = self._assert_single_item(wf_exs, name='wf3')
            task3_ex = self._assert_single_item(
                wf3_ex.task_executions, name="task3"
            )

        self.engine.rerun_workflow(task3_ex.id)

        self.await_workflow_success(wf1_ex.id)

        with db_api.transaction():
            wf_exs = db_api.get_workflow_executions()
            task_exs = db_api.get_task_executions()

            self.assertEqual(
                3, len(wf_exs), 'The number of workflow executions'
            )
            self.assertEqual(3, len(task_exs), 'The number of task executions')

            for wf_ex in wf_exs:
                self.assertEqual(
                    states.SUCCESS,
                    wf_ex.state,
                    'The executions must success the second time',
                )
            for task_ex in task_exs:
                self.assertEqual(
                    states.SUCCESS,
                    task_ex.state,
                    'The tasks must success the second time',
                )

    def _task_execs(self, wf_ex_id):
        with db_api.transaction():
            return db_api.get_workflow_execution(wf_ex_id).task_executions

    def _start_join_loop(self, transition):
        wf_service.create_workflows(
            """---
        version: '2.0'

        wf:
          vars:
            cnt: 0

          tasks:
            init:
              action: std.noop
              on-success: task1

            task1:
              action: std.noop
              publish:
                cnt: <% $.cnt + 1 %>
              on-success: [task2, task3]

            task2:
              action: std.noop
              on-success: join_task

            task3:
              action: std.noop
              on-success: join_task

            join_task:
              join: all
              action: std.noop
              TRANSITION: [side, loop]

            side:
              action: std.echo output=<% $.cnt %>

            loop:
              action: std.noop
              on-success:
                - task1: <% $.cnt < 2 %>
        """.replace('TRANSITION', transition)
        )

        return self.engine.start_workflow('wf')

    def _assert_join_loop_keeps_failed_downstream_task(self, transition):
        wf_ex = self._start_join_loop(transition)

        self.await_workflow_error(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            sides = [t for t in wf_ex.task_executions if t.name == 'side']

            self.assertEqual(
                [states.ERROR, states.SUCCESS], sorted(t.state for t in sides)
            )

    @mock.patch.object(
        std_actions.EchoAction,
        'run',
        mock.MagicMock(side_effect=[exc.ActionException(), 'ok']),
    )
    def test_join_in_loop_on_success_keeps_failed_downstream_task(self):
        self._assert_join_loop_keeps_failed_downstream_task('on-success')

    @mock.patch.object(
        std_actions.EchoAction,
        'run',
        mock.MagicMock(side_effect=[exc.ActionException(), 'ok']),
    )
    def test_join_in_loop_on_complete_keeps_failed_downstream_task(self):
        self._assert_join_loop_keeps_failed_downstream_task('on-complete')

    @mock.patch.object(
        std_actions.EchoAction,
        'run',
        mock.MagicMock(side_effect=[exc.ActionException(), 'ok']),
    )
    def test_join_in_loop_does_not_reuse_handled_downstream_task(self):
        wf_service.create_workflows(
            JOIN_LOOP_WF.replace('JOIN_ACTION', 'std.noop').replace(
                'JOIN_TRANSITION', 'on-success'
            )
        )

        wf_ex = self.engine.start_workflow('wf')

        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            sides = [t for t in wf_ex.task_executions if t.name == 'side']

            self.assertEqual(
                [states.ERROR, states.SUCCESS], sorted(t.state for t in sides)
            )

    @mock.patch.object(
        std_actions.SleepAction,
        'run',
        mock.MagicMock(side_effect=[None, exc.ActionException(), None]),
    )
    @mock.patch.object(
        std_actions.EchoAction,
        'run',
        mock.MagicMock(
            side_effect=[exc.ActionException(), exc.ActionException(), 'ok']
        ),
    )
    def test_rerun_join_in_loop_reruns_unhandled_downstream_task(self):
        wf_service.create_workflows(
            JOIN_LOOP_WF.replace('JOIN_ACTION', 'std.sleep seconds=0').replace(
                'JOIN_TRANSITION', 'on-complete'
            )
        )

        wf_ex = self.engine.start_workflow('wf')

        self.await_workflow_error(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            join_task_ex = self._assert_single_item(
                wf_ex.task_executions, name='join_task'
            )
            sides = [t for t in wf_ex.task_executions if t.name == 'side']

        self.assertEqual(2, len(sides))

        unhandled = [t.id for t in sides if not t.error_handled]

        self.assertEqual(1, len(unhandled))

        ctrl_cls = d_wf.DirectWorkflowController
        find = ctrl_cls._find_failed_downstream_task_execution

        def _handled_first(ctrl, *args):
            get_task_executions = ctrl._get_task_executions

            def _sorted(**kwargs):
                return sorted(
                    get_task_executions(**kwargs),
                    key=lambda t: not t.error_handled,
                )

            with mock.patch.object(ctrl, '_get_task_executions', _sorted):
                return find(ctrl, *args)

        with mock.patch.object(
            d_wf.DirectWorkflowController,
            '_find_failed_downstream_task_execution',
            _handled_first,
        ):
            self.engine.rerun_workflow(join_task_ex.id)

            self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            side_ex = db_api.get_task_execution(unhandled[0])

            self.assertEqual(states.SUCCESS, side_ex.state)

    @mock.patch.object(
        std_actions.EchoAction,
        'run',
        mock.MagicMock(
            side_effect=[
                exc.ActionException(),  # Mock task1 exception.
                exc.ActionException(),  # Mock task2 exception.
                'Task 1',  # Mock task1 success for rerun.
                'Task 2',  # Mock task2 success for rerun.
            ]
        ),
    )
    def test_rerun_downstream_task_parallel_branch_completes_first(self):
        wf_service.create_workflows("""---
        version: '2.0'

        wf:
          tasks:
            task1:
              action: std.echo output="task1"
              on-complete: [task2, task3]

            task2:
              action: std.echo output="task2"

            task3:
              action: std.noop
        """)

        wf_ex = self.engine.start_workflow('wf')

        self.await_workflow_error(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task1_ex = self._assert_single_item(
                wf_ex.task_executions, name='task1'
            )
            task2_ex = self._assert_single_item(
                wf_ex.task_executions, name='task2'
            )

        start_task = default_engine.DefaultEngine.start_task

        def _task3_done():
            with db_api.transaction():
                return (
                    len(
                        db_api.get_task_executions(
                            workflow_execution_id=wf_ex.id,
                            name='task3',
                            state=states.SUCCESS,
                        )
                    )
                    == 2
                )

        def _start_task(engine, task_ex_id, *args, **kwargs):
            if task_ex_id == task2_ex.id:
                self._await(_task3_done, delay=0.1)

            return start_task(engine, task_ex_id, *args, **kwargs)

        with mock.patch.object(
            default_engine.DefaultEngine, 'start_task', _start_task
        ):
            self.engine.rerun_workflow(task1_ex.id)

            self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task2_exs = [t for t in wf_ex.task_executions if t.name == 'task2']

            self.assertEqual([task2_ex.id], [t.id for t in task2_exs])

    def _complete_running_action(self, task_name, count, result):
        def _running_action_ids():
            with db_api.transaction():
                t_execs = db_api.get_task_executions(name=task_name)

                if not t_execs:
                    return []

                a_execs = t_execs[0].action_executions

                if len(a_execs) != count:
                    return []

                return [a.id for a in a_execs if a.state == states.RUNNING]

        self._await(_running_action_ids)

        self.engine.on_action_complete(_running_action_ids()[0], result)

    def _run_join_loop_pass_while_paused(self, wf_text):
        wf_service.create_workflows(wf_text)

        wf_ex = self.engine.start_workflow('wf')

        self._complete_running_action('join_task', 1, ml_actions.Result())

        self._await(
            lambda: (
                len(
                    db_api.get_task_executions(name='side', state=states.ERROR)
                )
                == 1
            )
        )

        def _join_pass_2_started():
            with db_api.transaction():
                t_ex = db_api.get_task_executions(name='join_task')[0]

                return len(t_ex.action_executions) == 2

        self._await(_join_pass_2_started)

        self.engine.pause_workflow(wf_ex.id)

        self.await_workflow_paused(wf_ex.id)

        self._complete_running_action('join_task', 2, ml_actions.Result())

        self._await(
            lambda: (
                db_api.get_task_executions(name='join_task')[0].state
                == states.SUCCESS
            )
        )

        self.engine.resume_workflow(wf_ex.id)

        return wf_ex

    def test_join_in_loop_pass_completed_while_paused(self):
        wf_ex = self._run_join_loop_pass_while_paused("""---
        version: '2.0'

        wf:
          vars:
            cnt: 0

          tasks:
            init:
              action: std.noop
              on-success: task1

            task1:
              action: std.noop
              publish:
                cnt: <% $.cnt + 1 %>
              on-success: join_task

            join_task:
              join: all
              action: std.async_noop
              on-complete: side

            side:
              action: std.noop
              fail-on: <% $.cnt < 2 %>
              on-error:
                - task1: <% $.cnt < 2 %>
        """)

        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            sides = db_api.get_task_executions(name='side')

            self.assertEqual(
                [states.ERROR, states.SUCCESS], sorted(t.state for t in sides)
            )

    def test_join_in_loop_pass_completed_while_paused_keeps_error(self):
        wf_ex = self._run_join_loop_pass_while_paused("""---
        version: '2.0'

        wf:
          vars:
            cnt: 0

          tasks:
            init:
              action: std.noop
              on-success: task1

            task1:
              action: std.noop
              publish:
                cnt: <% $.cnt + 1 %>
              on-success: join_task

            join_task:
              join: all
              action: std.async_noop
              on-complete: [side, loop]

            side:
              action: std.noop
              fail-on: <% $.cnt < 2 %>

            loop:
              action: std.noop
              on-success:
                - task1: <% $.cnt < 2 %>
        """)

        self.await_workflow_error(wf_ex.id)

        with db_api.transaction():
            sides = db_api.get_task_executions(name='side')

            self.assertEqual(
                [states.ERROR, states.SUCCESS], sorted(t.state for t in sides)
            )

    def test_rerun_completed_while_paused_reruns_downstream_task(self):
        wf_service.create_workflows("""---
        version: '2.0'

        wf:
          tasks:
            task1:
              action: std.async_noop
              on-complete: task2

            task2:
              action: std.noop
              fail-on: <% task(task1).result != 'ok' %>
        """)

        wf_ex = self.engine.start_workflow('wf')

        self._complete_running_action(
            'task1', 1, ml_actions.Result(error='error')
        )

        self.await_workflow_error(wf_ex.id)

        task1_ex = db_api.get_task_executions(name='task1')[0]
        task2_ex = db_api.get_task_executions(name='task2')[0]

        self.engine.rerun_workflow(task1_ex.id)

        def _rerun_started():
            with db_api.transaction():
                t_ex = db_api.get_task_execution(task1_ex.id)

                return len(t_ex.action_executions) == 2

        self._await(_rerun_started)

        self.engine.pause_workflow(wf_ex.id)

        self.await_workflow_paused(wf_ex.id)

        self._complete_running_action('task1', 2, ml_actions.Result('ok'))

        self._await(
            lambda: (
                db_api.get_task_execution(task1_ex.id).state == states.SUCCESS
            )
        )

        self.engine.resume_workflow(wf_ex.id)

        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            task2_execs = db_api.get_task_executions(name='task2')

            self.assertEqual([task2_ex.id], [t.id for t in task2_execs])
