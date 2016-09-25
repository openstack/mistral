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

from oslo_config import cfg

from mistral.db.v2 import api as db_api
from mistral import exceptions as exc
from mistral.services import workflows as wf_service
from mistral.tests.unit.engine import base
from mistral.workflow import states
from mistral.workflow import utils as wf_utils


# Use the set_default method to set value otherwise in certain test cases
# the change in value is not permanent.
cfg.CONF.set_default('auth_enable', False, group='pecan')


class DirectWorkflowEngineTest(base.EngineTestCase):
    def _run_workflow(self, wf_text, expected_state=states.ERROR):
        wf_service.create_workflows(wf_text)

        wf_ex = self.engine.start_workflow('wf', {})

        self.await_workflow_state(wf_ex.id, expected_state)

        return db_api.get_workflow_execution(wf_ex.id)

    def test_direct_workflow_on_closures(self):
        wf_text = """
        version: '2.0'

        wf:
          # type: direct - 'direct' is default

          tasks:
            task1:
              description: |
                Explicit 'fail' command should lead to workflow failure.
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

        wf_ex = self._run_workflow(wf_text)

        tasks = wf_ex.task_executions

        task1 = self._assert_single_item(tasks, name='task1')
        task3 = self._assert_single_item(tasks, name='task3')
        task4 = self._assert_single_item(tasks, name='task4')

        self.assertEqual(3, len(tasks))

        self.await_task_success(task1.id)
        self.await_task_success(task3.id)
        self.await_task_success(task4.id)

        self.assertTrue(wf_ex.state, states.ERROR)

    def test_direct_workflow_condition_transition_not_triggering(self):
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
        wf_ex = self.engine.start_workflow('wf', {})

        self.await_workflow_error(wf_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)
        tasks = wf_ex.task_executions

        task1 = self._assert_single_item(tasks, name='task1')

        self.assertEqual(1, len(tasks))

        self.await_task_error(task1.id)

        self.assertTrue(wf_ex.state, states.ERROR)

    def test_direct_workflow_change_state_after_success(self):
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

        wf_ex = self.engine.start_workflow('wf', {})

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

        wf_ex = self.engine.start_workflow('wf', None)

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

        self.assertEqual(states.RUNNING, wf_ex.state)
        self.assertEqual(1, len(wf_ex.task_executions))

        task_1_ex = self._assert_single_item(
            wf_ex.task_executions,
            name='task1'
        )

        self.assertEqual(states.RUNNING, task_1_ex.state)

        task_1_action_exs = db_api.get_action_executions(
            task_execution_id=task_1_ex.id
        )

        self.assertEqual(1, len(task_1_action_exs))
        self.assertEqual(states.RUNNING, task_1_action_exs[0].state)

        # Update async action execution result.
        self.engine.on_action_complete(
            task_1_action_exs[0].id,
            wf_utils.Result(data='foobar')
        )

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.ERROR, wf_ex.state)
        self.assertIn('Can not evaluate YAQL expression', wf_ex.state_info)

        task_execs = wf_ex.task_executions

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

        wf_ex = self.engine.start_workflow('wf', None)

        self.assertIn(
            "Can not evaluate YAQL expression:  wrong(yaql)",
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

        wf_ex = self.engine.start_workflow('wf', {'var': 2})

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

        wf_ex = self.engine.start_workflow('wf', {})

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

        # Assert that there is only one task execution and it's SUCCESS.
        self.assertEqual(1, len(wf_ex.task_executions))

        task_1_ex = self._assert_single_item(
            wf_ex.task_executions,
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
        self.assertEqual(1, len(wf_ex.task_executions))

        task_1_ex = self._assert_single_item(
            wf_ex.task_executions,
            name='task1'
        )

        self.assertEqual(states.RUNNING, task_1_ex.state)

        task_1_action_exs = db_api.get_action_executions(
            task_execution_id=task_1_ex.id
        )

        self.assertEqual(1, len(task_1_action_exs))
        self.assertEqual(states.RUNNING, task_1_action_exs[0].state)

        # Update async action execution result.
        self.engine.on_action_complete(
            task_1_action_exs[0].id,
            wf_utils.Result(data='foobar')
        )

        # Assert that task1 is SUCCESS and workflow is ERROR.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.ERROR, wf_ex.state)
        self.assertIn('Can not evaluate YAQL expression', wf_ex.state_info)
        self.assertEqual(1, len(wf_ex.task_executions))

        task_1_ex = self._assert_single_item(
            wf_ex.task_executions,
            name='task1'
        )

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

        self.assertIn("Task 'task3' not found", exception.message)

    def test_delete_workflow_completion_check_on_stop(self):
        wf_text = """---
        version: '2.0'

        wf:
          tasks:
            async_task:
              action: std.async_noop
        """

        wf_service.create_workflows(wf_text)

        wf_ex = self.engine.start_workflow('wf', {})

        calls = db_api.get_delayed_calls()

        mtd_name = 'mistral.engine.workflow_handler._check_and_complete'

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

        wf_ex = self.engine.start_workflow('wf', {})

        calls = db_api.get_delayed_calls()

        mtd_name = 'mistral.engine.workflow_handler._check_and_complete'

        self._assert_single_item(calls, target_method_name=mtd_name)

        db_api.delete_workflow_execution(wf_ex.id)

        self._await(
            lambda:
            len(db_api.get_delayed_calls(target_method_name=mtd_name)) == 0
        )
