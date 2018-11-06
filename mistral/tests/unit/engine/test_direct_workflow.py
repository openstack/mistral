# Copyright 2014 - Mirantis, Inc.
# Copyright 2015 - StackStorm, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

import six

from oslo_config import cfg

from mistral.db.v2 import api as db_api
from mistral import exceptions as exc
from mistral.lang import parser as spec_parser
from mistral.services import workflows as wf_service
from mistral.tests.unit.engine import base
from mistral.workflow import states
from mistral_lib import actions as ml_actions


# Use the set_default method to set value otherwise in certain test cases
# the change in value is not permanent.
cfg.CONF.set_default('auth_enable', False, group='pecan')


class DirectWorkflowEngineTest(base.EngineTestCase):
    def _run_workflow(self, wf_text, expected_state=states.ERROR):
        wf_service.create_workflows(wf_text)

        wf_ex = self.engine.start_workflow('wf')

        self.await_workflow_state(wf_ex.id, expected_state)

        return db_api.get_workflow_execution(wf_ex.id)

    def test_on_closures(self):
        wf_text = """
        version: '2.0'

        wf:
          # type: direct - 'direct' is default

          tasks:
            task1:
              description: |
                Explicit 'succeed' command should lead to workflow success.
              action: std.echo output="Echo"
              on-success:
                - task2
                - succeed
              on-complete:
                - task3
                - task4
                - fail
                - never_gets_here

            task2:
              action: std.noop

            task3:
              action: std.noop

            task4:
              action: std.noop

            never_gets_here:
              action: std.noop
        """

        wf_ex = self._run_workflow(wf_text, expected_state=states.SUCCESS)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            tasks = wf_ex.task_executions

        task1 = self._assert_single_item(tasks, name='task1')
        task2 = self._assert_single_item(tasks, name='task2')

        self.assertEqual(2, len(tasks))

        self.await_task_success(task1.id)
        self.await_task_success(task2.id)

        self.assertTrue(wf_ex.state, states.ERROR)

    def test_condition_transition_not_triggering(self):
        wf_text = """---
        version: '2.0'

        wf:
          input:
            - var: null

          tasks:
            task1:
              action: std.fail
              on-success:
                - task2
              on-error:
                - task3: <% $.var != null %>

            task2:
              action: std.noop

            task3:
              action: std.noop
        """

        wf_service.create_workflows(wf_text)
        wf_ex = self.engine.start_workflow('wf')

        self.await_workflow_error(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            tasks = wf_ex.task_executions

        task1 = self._assert_single_item(tasks, name='task1')

        self.assertEqual(1, len(tasks))

        self.await_task_error(task1.id)

        self.assertTrue(wf_ex.state, states.ERROR)

    def test_change_state_after_success(self):
        wf_text = """
        version: '2.0'

        wf:
          tasks:
            task1:
              action: std.echo output="Echo"
              on-success:
                - task2

            task2:
              action: std.noop
        """

        wf_service.create_workflows(wf_text)

        wf_ex = self.engine.start_workflow('wf')

        self.await_workflow_success(wf_ex.id)

        self.assertEqual(
            states.SUCCESS,
            self.engine.resume_workflow(wf_ex.id).state
        )

        self.assertRaises(
            exc.WorkflowException,
            self.engine.pause_workflow, wf_ex.id
        )

        self.assertEqual(
            states.SUCCESS,
            self.engine.stop_workflow(wf_ex.id, states.ERROR).state
        )

    def test_task_not_updated(self):
        wf_text = """
        version: 2.0

        wf:
          tasks:
            task1:
              action: std.echo
              input:
                output: <% task().result.content %>
        """

        wf_service.create_workflows(wf_text)

        wf_ex = self.engine.start_workflow('wf')

        self.await_workflow_success(wf_ex.id)

        self.assertEqual(
            states.SUCCESS,
            self.engine.resume_workflow(wf_ex.id).state
        )

        self.assertRaises(
            exc.WorkflowException,
            self.engine.pause_workflow, wf_ex.id
        )

        self.assertEqual(
            states.SUCCESS,
            self.engine.stop_workflow(wf_ex.id, states.ERROR).state
        )

    def test_wrong_task_input(self):
        wf_text = """
        version: '2.0'

        wf:
          type: direct

          tasks:
            task1:
              action: std.echo output="Echo"
              on-complete:
                - task2

            task2:
              description: Wrong task output should lead to workflow failure
              action: std.echo wrong_input="Hahaha"
        """

        wf_ex = self._run_workflow(wf_text)

        self.assertIn('Invalid input', wf_ex.state_info)
        self.assertTrue(wf_ex.state, states.ERROR)

    def test_wrong_first_task_input(self):
        wf_text = """
        version: '2.0'

        wf:
          type: direct

          tasks:
            task1:
              action: std.echo wrong_input="Ha-ha"
        """

        wf_ex = self._run_workflow(wf_text)

        self.assertIn("Invalid input", wf_ex.state_info)
        self.assertEqual(states.ERROR, wf_ex.state)

    def test_wrong_action(self):
        wf_text = """
        version: '2.0'

        wf:
          type: direct

          tasks:
            task1:
              action: std.echo output="Echo"
              on-complete:
                - task2

            task2:
              action: action.doesnt_exist
        """

        wf_ex = self._run_workflow(wf_text)

        # TODO(dzimine): Catch tasks caused error, and set them to ERROR:
        # TODO(dzimine): self.assertTrue(task_ex.state, states.ERROR)

        self.assertTrue(wf_ex.state, states.ERROR)
        self.assertIn("Failed to find action", wf_ex.state_info)

    def test_wrong_action_first_task(self):
        wf_text = """
        version: '2.0'

        wf:
          type: direct

          tasks:
            task1:
              action: wrong.task
        """

        wf_service.create_workflows(wf_text)

        wf_ex = self.engine.start_workflow('wf')

        self.assertIn(
            "Failed to find action [action_name=wrong.task]",
            wf_ex.state_info
        )
        self.assertEqual(states.ERROR, wf_ex.state)

    def test_next_task_with_input_yaql_error(self):
        wf_text = """
        version: '2.0'

        wf:
          type: direct

          tasks:
            task1:
              action: std.echo output="Echo"
              on-complete:
                - task2

            task2:
              action: std.echo output=<% wrong(yaql) %>
        """

        # Invoke workflow and assert workflow is in ERROR.
        wf_ex = self._run_workflow(wf_text)

        self.assertEqual(states.ERROR, wf_ex.state)
        self.assertIn('Can not evaluate YAQL expression', wf_ex.state_info)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_execs = wf_ex.task_executions

        self.assertEqual(2, len(task_execs))

        # 'task1' should be in SUCCESS.
        task_1_ex = self._assert_single_item(
            task_execs,
            name='task1',
            state=states.SUCCESS
        )

        # 'task1' should have exactly one action execution (in SUCCESS).
        task_1_action_exs = db_api.get_action_executions(
            task_execution_id=task_1_ex.id
        )

        self.assertEqual(1, len(task_1_action_exs))
        self.assertEqual(states.SUCCESS, task_1_action_exs[0].state)

        # 'task2' should exist but in ERROR.
        task_2_ex = self._assert_single_item(
            task_execs,
            name='task2',
            state=states.ERROR
        )

        # 'task2' must not have action executions.
        self.assertEqual(
            0,
            len(db_api.get_action_executions(task_execution_id=task_2_ex.id))
        )

    def test_async_next_task_with_input_yaql_error(self):
        wf_text = """
        version: '2.0'

        wf:
          type: direct

          tasks:
            task1:
              action: std.async_noop
              on-complete:
                - task2

            task2:
              action: std.echo output=<% wrong(yaql) %>
        """

        # Invoke workflow and assert workflow, task,
        # and async action execution are RUNNING.
        wf_ex = self._run_workflow(wf_text, states.RUNNING)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_execs = wf_ex.task_executions

        self.assertEqual(states.RUNNING, wf_ex.state)
        self.assertEqual(1, len(task_execs))

        task_1_ex = self._assert_single_item(task_execs, name='task1')

        self.assertEqual(states.RUNNING, task_1_ex.state)

        task_1_action_exs = db_api.get_action_executions(
            task_execution_id=task_1_ex.id
        )

        self.assertEqual(1, len(task_1_action_exs))
        self.assertEqual(states.RUNNING, task_1_action_exs[0].state)

        # Update async action execution result.
        self.engine.on_action_complete(
            task_1_action_exs[0].id,
            ml_actions.Result(data='foobar')
        )

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_execs = wf_ex.task_executions

        self.assertEqual(states.ERROR, wf_ex.state)
        self.assertIn('Can not evaluate YAQL expression', wf_ex.state_info)

        self.assertEqual(2, len(task_execs))

        # 'task1' must be in SUCCESS.
        task_1_ex = self._assert_single_item(
            task_execs,
            name='task1',
            state=states.SUCCESS
        )

        # 'task1' must have exactly one action execution (in SUCCESS).
        task_1_action_exs = db_api.get_action_executions(
            task_execution_id=task_1_ex.id
        )

        self.assertEqual(1, len(task_1_action_exs))
        self.assertEqual(states.SUCCESS, task_1_action_exs[0].state)

        # 'task2' must be in ERROR.
        task_2_ex = self._assert_single_item(
            task_execs,
            name='task2',
            state=states.ERROR
        )

        # 'task2' must not have action executions.
        self.assertEqual(
            0,
            len(db_api.get_action_executions(task_execution_id=task_2_ex.id))
        )

    def test_join_all_task_with_input_jinja_error(self):
        wf_def = """---
        version: '2.0'
        wf:
          tasks:
            task_1_1:
              action: std.sleep seconds=1
              on-success:
                - task_2
            task_1_2:
              on-success:
                - task_2
            task_2:
              action: std.echo
              join: all
              input:
                output: |
                  !! {{ _.nonexistent_variable }} !!"""

        wf_service.create_workflows(wf_def)
        wf_ex = self.engine.start_workflow('wf')

        self.await_workflow_error(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
            tasks = wf_ex.task_executions

        self.assertEqual(3, len(tasks))

        task_1_1 = self._assert_single_item(
            tasks, name="task_1_1", state=states.SUCCESS
        )
        task_1_2 = self._assert_single_item(
            tasks, name="task_1_2", state=states.SUCCESS
        )

        task_2 = self._assert_single_item(
            tasks, name="task_2", state=states.ERROR
        )

        with db_api.transaction():
            task_1_1_action_exs = db_api.get_action_executions(
                task_execution_id=task_1_1.id)
            task_1_2_action_exs = db_api.get_action_executions(
                task_execution_id=task_1_2.id)

            task_2_action_exs = db_api.get_action_executions(
                task_execution_id=task_2.id)

        self.assertEqual(1, len(task_1_1_action_exs))
        self.assertEqual(states.SUCCESS, task_1_1_action_exs[0].state)

        self.assertEqual(1, len(task_1_2_action_exs))
        self.assertEqual(states.SUCCESS, task_1_2_action_exs[0].state)

        self.assertEqual(0, len(task_2_action_exs))

    def test_second_task_with_input_jinja_error(self):
        wf_def = """---
        version: '2.0'
        wf:
          tasks:
            first:
              on-success:
                - second
            second:
              action: std.echo
              input:
                output: |
                  !! {{ _.nonexistent_variable }} !!"""

        wf_service.create_workflows(wf_def)
        wf_ex = self.engine.start_workflow('wf')

        self.await_workflow_error(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
            tasks = wf_ex.task_executions

        self.assertEqual(2, len(tasks))

        task_first = self._assert_single_item(
            tasks, name="first", state=states.SUCCESS
        )
        task_second = self._assert_single_item(
            tasks, name="second", state=states.ERROR
        )

        with db_api.transaction():
            first_tasks_action_exs = db_api.get_action_executions(
                task_execution_id=task_first.id)
            second_tasks_action_exs = db_api.get_action_executions(
                task_execution_id=task_second.id)

        self.assertEqual(1, len(first_tasks_action_exs))
        self.assertEqual(states.SUCCESS, first_tasks_action_exs[0].state)

        self.assertEqual(0, len(second_tasks_action_exs))

    def test_messed_yaql_in_first_task(self):
        wf_text = """
        version: '2.0'

        wf:
          type: direct
          tasks:
            task1:
              action: std.echo output=<% wrong(yaql) %>
        """

        wf_service.create_workflows(wf_text)

        wf_ex = self.engine.start_workflow('wf')

        self.assertIn(
            "Can not evaluate YAQL expression [expression=wrong(yaql)",
            wf_ex.state_info
        )
        self.assertEqual(states.ERROR, wf_ex.state)

    def test_mismatched_yaql_in_first_task(self):
        wf_text = """
        version: '2.0'

        wf:
          input:
            - var

          tasks:
            task1:
              action: std.echo output=<% $.var + $.var2 %>
        """

        wf_service.create_workflows(wf_text)

        wf_ex = self.engine.start_workflow('wf', wf_input={'var': 2})

        self.assertIn("Can not evaluate YAQL expression", wf_ex.state_info)
        self.assertEqual(states.ERROR, wf_ex.state)

    def test_one_line_syntax_in_on_clauses(self):
        wf_text = """
        version: '2.0'

        wf:
          type: direct

          tasks:
            task1:
              action: std.echo output=1
              on-success: task2

            task2:
              action: std.echo output=1
              on-complete: task3

            task3:
              action: std.fail
              on-error: task4

            task4:
              action: std.echo output=4
        """

        wf_service.create_workflows(wf_text)

        wf_ex = self.engine.start_workflow('wf')

        self.await_workflow_success(wf_ex.id)

    def test_task_on_clause_has_yaql_error(self):
        wf_text = """
        version: '2.0'

        wf:
          type: direct

          tasks:
            task1:
              action: std.noop
              on-success:
                - task2: <% wrong(yaql) %>

            task2:
              action: std.noop
        """

        # Invoke workflow and assert workflow is in ERROR.
        wf_ex = self._run_workflow(wf_text)

        self.assertEqual(states.ERROR, wf_ex.state)
        self.assertIn('Can not evaluate YAQL expression', wf_ex.state_info)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_execs = wf_ex.task_executions

        # Assert that there is only one task execution and it's SUCCESS.
        self.assertEqual(1, len(task_execs))

        task_1_ex = self._assert_single_item(
            task_execs,
            name='task1'
        )

        self.assertEqual(states.ERROR, task_1_ex.state)

        # Assert that there is only one action execution and it's SUCCESS.
        task_1_action_exs = db_api.get_action_executions(
            task_execution_id=task_1_ex.id
        )

        self.assertEqual(1, len(task_1_action_exs))
        self.assertEqual(states.SUCCESS, task_1_action_exs[0].state)

    def test_async_task_on_clause_has_yaql_error(self):
        wf_text = """
        version: '2.0'

        wf:
          type: direct

          tasks:
            task1:
              action: std.async_noop
              on-complete:
                - task2: <% wrong(yaql) %>

            task2:
              action: std.noop
        """

        # Invoke workflow and assert workflow, task,
        # and async action execution are RUNNING.
        wf_ex = self._run_workflow(wf_text, states.RUNNING)

        self.assertEqual(states.RUNNING, wf_ex.state)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_execs = wf_ex.task_executions

        self.assertEqual(1, len(task_execs))

        task_1_ex = self._assert_single_item(task_execs, name='task1')

        self.assertEqual(states.RUNNING, task_1_ex.state)

        task_1_action_exs = db_api.get_action_executions(
            task_execution_id=task_1_ex.id
        )

        self.assertEqual(1, len(task_1_action_exs))
        self.assertEqual(states.RUNNING, task_1_action_exs[0].state)

        # Update async action execution result.
        self.engine.on_action_complete(
            task_1_action_exs[0].id,
            ml_actions.Result(data='foobar')
        )

        # Assert that task1 is SUCCESS and workflow is ERROR.
        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_execs = wf_ex.task_executions

        self.assertEqual(states.ERROR, wf_ex.state)
        self.assertIn('Can not evaluate YAQL expression', wf_ex.state_info)
        self.assertEqual(1, len(task_execs))

        task_1_ex = self._assert_single_item(task_execs, name='task1')

        self.assertEqual(states.ERROR, task_1_ex.state)

        task_1_action_exs = db_api.get_action_executions(
            task_execution_id=task_1_ex.id
        )

        self.assertEqual(1, len(task_1_action_exs))
        self.assertEqual(states.SUCCESS, task_1_action_exs[0].state)

    def test_inconsistent_task_names(self):
        wf_text = """
        version: '2.0'

        wf:
          tasks:
            task1:
              action: std.noop
              on-success: task3

            task2:
              action: std.noop
        """

        exception = self.assertRaises(
            exc.InvalidModelException,
            wf_service.create_workflows,
            wf_text
        )

        self.assertIn("Task 'task3' not found", str(exception))

    def test_delete_workflow_completion_check_on_stop(self):
        wf_text = """---
        version: '2.0'

        wf:
          tasks:
            async_task:
              action: std.async_noop
        """

        wf_service.create_workflows(wf_text)

        wf_ex = self.engine.start_workflow('wf')

        calls = db_api.get_delayed_calls()

        mtd_name = 'mistral.engine.workflow_handler._check_and_fix_integrity'

        self._assert_single_item(calls, target_method_name=mtd_name)

        self.engine.stop_workflow(wf_ex.id, state=states.CANCELLED)

        self._await(
            lambda:
            len(db_api.get_delayed_calls(target_method_name=mtd_name)) == 0
        )

    def test_delete_workflow_completion_on_execution_delete(self):
        wf_text = """---
        version: '2.0'

        wf:
          tasks:
            async_task:
              action: std.async_noop
        """

        wf_service.create_workflows(wf_text)

        wf_ex = self.engine.start_workflow('wf')

        calls = db_api.get_delayed_calls()

        mtd_name = 'mistral.engine.workflow_handler._check_and_fix_integrity'

        self._assert_single_item(calls, target_method_name=mtd_name)

        db_api.delete_workflow_execution(wf_ex.id)

        self._await(
            lambda:
            len(db_api.get_delayed_calls(target_method_name=mtd_name)) == 0
        )

    def test_output(self):
        wf_text = """---
        version: '2.0'

        wf:
          tasks:
            task1:
              action: std.echo output="Hi Mistral!"
              on-success: task2

            task2:
              action: std.noop
        """

        wf_service.create_workflows(wf_text)

        wf_ex = self.engine.start_workflow('wf')

        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            self.assertDictEqual({}, wf_ex.output)

    def test_output_expression(self):
        wf_text = """---
        version: '2.0'

        wf:
          output:
            continue_flag: <% $.continue_flag %>

          task-defaults:
            on-error:
              - task2

          tasks:
            task1:
              action: std.fail
              on-success: task3

            task2:
              action: std.noop
              publish:
                continue_flag: false

            task3:
              action: std.noop
        """

        wf_service.create_workflows(wf_text)

        wf_ex = self.engine.start_workflow('wf')

        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            self.assertEqual(2, len(wf_ex.task_executions))
            self.assertDictEqual({'continue_flag': False}, wf_ex.output)

    def test_triggered_by(self):
        wf_text = """---
        version: '2.0'

        wf:
          tasks:
            task1:
              action: std.noop
              on-success: task2

            task2:
              action: std.fail
              on-error: task3

            task3:
              action: std.fail
              on-error: noop
              on-success: task4
              on-complete: task4

            task4:
              action: std.noop
        """

        wf_service.create_workflows(wf_text)

        wf_ex = self.engine.start_workflow('wf')

        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_execs = wf_ex.task_executions

        task1 = self._assert_single_item(task_execs, name='task1')
        task2 = self._assert_single_item(task_execs, name='task2')
        task3 = self._assert_single_item(task_execs, name='task3')
        task4 = self._assert_single_item(task_execs, name='task4')

        key = 'triggered_by'

        self.assertIsNone(task1.runtime_context.get(key))

        self.assertListEqual(
            [
                {
                    "task_id": task1.id,
                    "event": "on-success"
                }
            ],
            task2.runtime_context.get(key)
        )

        self.assertListEqual(
            [
                {
                    "task_id": task2.id,
                    "event": "on-error"
                }
            ],
            task3.runtime_context.get(key)
        )

        self.assertListEqual(
            [
                {
                    "task_id": task3.id,
                    "event": "on-complete"
                }
            ],
            task4.runtime_context.get(key)
        )

    def test_task_in_context_immutability(self):
        wf_text = """---
        version: '2.0'

        wf:
          description: |
            The idea of this workflow is to have two parallel branches and
            publish different data in these branches. When the workflow
            completed we need to check that during internal manipulations
            with workflow contexts belonging to different branches the inbound
            contexts of all tasks keep their initial values.

          tasks:
            # Start task.
            task0:
              publish:
                var0: val0
              on-success:
                - task1_1
                - task2_1

            task1_1:
              publish:
                var1: val1
              on-success: task1_2

            # The last task in the 1st branch.
            task1_2:
              action: std.noop

            task2_1:
              publish:
                var2: val2
              on-success: task2_2

            # The last task in the 2nd branch.
            task2_2:
              action: std.noop
        """

        wf_service.create_workflows(wf_text)

        wf_ex = self.engine.start_workflow('wf')

        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            tasks_execs = wf_ex.task_executions

        task0_ex = self._assert_single_item(tasks_execs, name='task0')
        task1_1_ex = self._assert_single_item(tasks_execs, name='task1_1')
        task1_2_ex = self._assert_single_item(tasks_execs, name='task1_2')
        task2_1_ex = self._assert_single_item(tasks_execs, name='task2_1')
        task2_2_ex = self._assert_single_item(tasks_execs, name='task2_2')

        self.assertDictEqual({}, task0_ex.in_context)
        self.assertDictEqual({'var0': 'val0'}, task1_1_ex.in_context)
        self.assertDictEqual(
            {
                'var0': 'val0',
                'var1': 'val1'
            },
            task1_2_ex.in_context
        )
        self.assertDictEqual({'var0': 'val0'}, task2_1_ex.in_context)
        self.assertDictEqual(
            {
                'var0': 'val0',
                'var2': 'val2'
            },
            task2_2_ex.in_context
        )

    def test_big_on_closures(self):
        # The idea of the test is to run a workflow with a big 'on-success'
        # list of tasks and big task inbound context ('task_ex.in_context)
        # and observe how it influences memory consumption and performance.
        # The test doesn't have any assertions related to memory(CPU) usage
        # because it's quite difficult to do them. Particular metrics may
        # vary from run to run and also depend on the platform.

        sub_wf_text = """
        version: '2.0'

        sub_wf:
          tasks:
            task1:
              action: std.noop
        """

        wf_text = """
        version: '2.0'

        wf:
          tasks:
            task01:
              action: std.noop
              on-success: task02

            task02:
              action: std.test_dict size=1000 key_prefix='key' val='val'
              publish:
                continue_flag: true
                data: <% task().result %>
              on-success: task0

            task0:
              workflow: sub_wf
              on-success: {{{__ON_SUCCESS_LIST__}}}

            {{{__TASK_LIST__}}}
        """

        # Generate the workflow text.
        task_cnt = 50

        on_success_list_str = ''

        for i in range(1, task_cnt + 1):
            on_success_list_str += (
                '\n                - task{}: '
                '<% $.continue_flag = true %>'.format(i)
            )

        wf_text = wf_text.replace(
            '{{{__ON_SUCCESS_LIST__}}}',
            on_success_list_str
        )

        task_list_str = ''

        task_template = """
            task{}:
              action: std.noop
        """

        for i in range(1, task_cnt + 1):
            task_list_str += task_template.format(i)

        wf_text = wf_text.replace('{{{__TASK_LIST__}}}', task_list_str)

        wf_service.create_workflows(sub_wf_text)
        wf_service.create_workflows(wf_text)

        # Start the workflow.
        wf_ex = self.engine.start_workflow('wf')

        self.await_workflow_success(wf_ex.id, timeout=60)

        self.assertEqual(2, spec_parser.get_wf_execution_spec_cache_size())

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_execs = wf_ex.task_executions

        self.assertEqual(task_cnt + 3, len(task_execs))

        self._assert_single_item(task_execs, name='task0')
        self._assert_single_item(task_execs, name='task{}'.format(task_cnt))

    def test_action_error_with_array_result(self):
        wf_text = """---
        version: '2.0'

        wf:
          tasks:
            task1:
              action: std.fail error_data=[1,2,3]
        """

        wf_service.create_workflows(wf_text)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wf')

        self.await_workflow_error(wf_ex.id)

        with db_api.transaction():
            # Note: We need to reread execution to access related tasks.
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_ex = self._assert_single_item(
                wf_ex.task_executions,
                name='task1',
                state=states.ERROR
            )

            a_ex = self._assert_single_item(
                task_ex.action_executions,
                name='std.fail'
            )

            self.assertIsInstance(a_ex.output.get('result'), list)

            # NOTE(rakhmerov): This was previously failing but only Python 2.7
            # probably because SQLAlchemy works differently on different
            # versions of Python. On Python 3 this field's value was always
            # converted into a string no matter what we tried to assign. But
            # that didn't happen on Python 2.7 which caused an SQL exception.
            self.assertIsInstance(task_ex.state_info, six.string_types)
