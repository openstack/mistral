# Copyright 2016 - Nokia Networks.
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


# Use the set_default method to set value otherwise in certain test cases
# the change in value is not permanent.
cfg.CONF.set_default('auth_enable', False, group='pecan')


class ErrorHandlingEngineTest(base.EngineTestCase):
    def test_invalid_workflow_input(self):
        # Check that in case of invalid input workflow objects aren't even
        # created.
        wf_text = """
        version: '2.0'

        wf:
          input:
            - param1
            - param2

          tasks:
            task1:
              action: std.noop
        """

        wf_service.create_workflows(wf_text)

        self.assertRaises(
            exc.InputException,
            self.engine.start_workflow,
            'wf',
            {'wrong_param': 'some_value'}
        )

        self.assertEqual(0, len(db_api.get_workflow_executions()))
        self.assertEqual(0, len(db_api.get_task_executions()))
        self.assertEqual(0, len(db_api.get_action_executions()))

    def test_first_task_error(self):
        # Check that in case of an error in first task workflow objects are
        # still persisted properly.
        wf_text = """
        version: '2.0'

        wf:
          tasks:
            task1:
              action: std.fail
              on-success: task2

            task2:
              action: std.noop
        """

        wf_service.create_workflows(wf_text)

        wf_ex = self.engine.start_workflow('wf', {})

        self.assertEqual(states.RUNNING, wf_ex.state)
        self.assertIsNotNone(db_api.get_workflow_execution(wf_ex.id))

        self.await_workflow_error(wf_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        task_execs = wf_ex.task_executions

        self.assertEqual(1, len(task_execs))

        self._assert_single_item(task_execs, name='task1', state=states.ERROR)

    def test_action_error(self):
        # Check that state of all workflow objects (workflow executions,
        # task executions, action executions) is properly persisted in case
        # of action error.
        wf_text = """
        version: '2.0'

        wf:
          tasks:
            task1:
              action: std.fail
        """

        wf_service.create_workflows(wf_text)

        wf_ex = self.engine.start_workflow('wf', {})

        self.await_workflow_error(wf_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        task_execs = wf_ex.task_executions

        self.assertEqual(1, len(task_execs))

        self._assert_single_item(task_execs, name='task1', state=states.ERROR)

    def test_task_error(self):
        # Check that state of all workflow objects (workflow executions,
        # task executions, action executions) is properly persisted in case
        # of an error at task level.
        wf_text = """
        version: '2.0'

        wf:
          tasks:
            task1:
              action: std.noop
              publish:
                my_var: <% invalid_yaql_function() %>
        """

        wf_service.create_workflows(wf_text)

        wf_ex = self.engine.start_workflow('wf', {})

        self.await_workflow_error(wf_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        # Now we need to make sure that task is in ERROR state but action
        # is in SUCCESS because error occurred in 'publish' clause which
        # must not affect action state.
        task_execs = wf_ex.task_executions

        self.assertEqual(1, len(task_execs))

        task_ex = self._assert_single_item(
            task_execs,
            name='task1',
            state=states.ERROR
        )

        action_execs = task_ex.executions

        self.assertEqual(1, len(action_execs))

        self._assert_single_item(
            action_execs,
            name='std.noop',
            state=states.SUCCESS
        )

    def test_task_error_with_on_handlers(self):
        # Check that state of all workflow objects (workflow executions,
        # task executions, action executions) is properly persisted in case
        # of an error at task level and this task has on-XXX handlers.
        wf_text = """
        version: '2.0'

        wf:
          tasks:
            task1:
              action: std.noop
              publish:
                my_var: <% invalid_yaql_function() %>
              on-success:
                - task2
              on-error:
                - task3

            task2:
              description: This task must never run.
              action: std.noop

            task3:
              action: std.noop
        """

        wf_service.create_workflows(wf_text)

        wf_ex = self.engine.start_workflow('wf', {})

        self.await_workflow_error(wf_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        # Now we need to make sure that task is in ERROR state but action
        # is in SUCCESS because error occurred in 'publish' clause which
        # must not affect action state.
        task_execs = wf_ex.task_executions

        # NOTE: task3 must not run because on-error handler triggers only
        # on error outcome of an action (or workflow) associated with a task.
        self.assertEqual(1, len(task_execs))

        task_ex = self._assert_single_item(
            task_execs,
            name='task1',
            state=states.ERROR
        )

        action_execs = task_ex.executions

        self.assertEqual(1, len(action_execs))

        self._assert_single_item(
            action_execs,
            name='std.noop',
            state=states.SUCCESS
        )

    def test_workflow_error(self):
        # Check that state of all workflow objects (workflow executions,
        # task executions, action executions) is properly persisted in case
        # of an error at task level.
        wf_text = """
        version: '2.0'

        wf:
          output:
            my_output: <% $.invalid_yaql_variable %>

          tasks:
            task1:
              action: std.noop
        """

        wf_service.create_workflows(wf_text)

        wf_ex = self.engine.start_workflow('wf', {})

        self.await_workflow_error(wf_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        # Now we need to make sure that task and action are in SUCCESS
        # state because mistake at workflow level (output evaluation)
        # must not affect them.
        task_execs = wf_ex.task_executions

        self.assertEqual(1, len(task_execs))

        task_ex = self._assert_single_item(
            task_execs,
            name='task1',
            state=states.SUCCESS
        )

        action_execs = task_ex.executions

        self.assertEqual(1, len(action_execs))

        self._assert_single_item(
            action_execs,
            name='std.noop',
            state=states.SUCCESS
        )

    def test_action_error_with_wait_before_policy(self):
        # Check that state of all workflow objects (workflow executions,
        # task executions, action executions) is properly persisted in case
        # of action error and task has 'wait-before' policy. It is an
        # implicit test for task continuation because 'wait-before' inserts
        # a delay between preparing task execution object and scheduling
        # actions. If an an error happens during scheduling actions (e.g.
        # invalid YAQL in action parameters) then we also need to handle
        # this properly, meaning that task and workflow state should go
        # into ERROR state.
        wf_text = """
        version: '2.0'

        wf:
          tasks:
            task1:
              action: std.echo output=<% invalid_yaql_function() %>
              wait-before: 1
        """

        wf_service.create_workflows(wf_text)

        wf_ex = self.engine.start_workflow('wf', {})

        self.await_workflow_error(wf_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        task_execs = wf_ex.task_executions

        self.assertEqual(1, len(task_execs))

        task_ex = self._assert_single_item(
            task_execs,
            name='task1',
            state=states.ERROR
        )

        action_execs = task_ex.executions

        self.assertEqual(0, len(action_execs))

    def test_action_error_with_wait_after_policy(self):
        # Check that state of all workflow objects (workflow executions,
        # task executions, action executions) is properly persisted in case
        # of action error and task has 'wait-after' policy. It is an
        # implicit test for task completion because 'wait-after' inserts
        # a delay between actual task completion and logic that calculates
        # next workflow commands. If an an error happens while calculating
        # next commands (e.g. invalid YAQL in on-XXX clauses) then we also
        # need to handle this properly, meaning that task and workflow state
        # should go into ERROR state.
        wf_text = """
        version: '2.0'

        wf:
          tasks:
            task1:
              action: std.noop
              wait-after: 1
              on-success:
                - task2: <% invalid_yaql_function() %>

            task2:
              action: std.noop
        """

        wf_service.create_workflows(wf_text)

        wf_ex = self.engine.start_workflow('wf', {})

        self.await_workflow_error(wf_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        task_execs = wf_ex.task_executions

        self.assertEqual(1, len(task_execs))

        task_ex = self._assert_single_item(
            task_execs,
            name='task1',
            state=states.ERROR
        )

        action_execs = task_ex.executions

        self.assertEqual(1, len(action_execs))

        self._assert_single_item(
            action_execs,
            name='std.noop',
            state=states.SUCCESS
        )
