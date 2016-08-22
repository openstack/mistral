# Copyright 2014 - Mirantis, Inc.
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

from mistral.db.v2 import api as db_api
from mistral import exceptions as exc
from mistral.services import workbooks as wb_service
from mistral.tests.unit.engine import base
from mistral.workbook import parser as spec_parser
from mistral.workflow import data_flow
from mistral.workflow import states
from mistral.workflow import utils


# Use the set_default method to set value otherwise in certain test cases
# the change in value is not permanent.
cfg.CONF.set_default('auth_enable', False, group='pecan')


RESUME_WORKBOOK = """
---
version: '2.0'

name: wb

workflows:
  wf1:
    type: direct

    tasks:
      task1:
        action: std.echo output="Hi!"
        on-complete:
          - task2
          - pause

      task2:
        action: std.echo output="Task 2"
"""


RESUME_WORKBOOK_DIFF_ENV_VAR = """
---
version: '2.0'

name: wb

workflows:
  wf1:
    type: direct

    tasks:
      task1:
        action: std.echo output="Hi!"
        on-complete:
          - task2

      task2:
        action: std.echo output=<% env().var1 %>
        pause-before: true
        on-complete:
          - task3

      task3:
        action: std.echo output=<% env().var2 %>
"""


RESUME_WORKBOOK_REVERSE = """
---
version: '2.0'

name: resume_reverse

workflows:
  wf:
    type: reverse

    tasks:
      task1:
        action: std.echo output="Hi!"
        wait-after: 1

      task2:
        action: std.echo output="Task 2"
        requires: [task1]
"""


WORKBOOK_TWO_BRANCHES = """
---
version: '2.0'

name: wb

workflows:
  wf1:
    type: direct

    tasks:
      task1:
        action: std.echo output="Hi!"
        on-complete:
          - task2
          - task3
          - pause

      task2:
        action: std.echo output="Task 2"

      task3:
        action: std.echo output="Task 3"
"""


WORKBOOK_TWO_START_TASKS = """
---
version: '2.0'

name: wb

workflows:
  wf1:
    type: direct

    tasks:
      task1:
        action: std.echo output="Task 1"
        on-complete:
          - task3
          - pause

      task2:
        action: std.echo output="Task 2"
        on-complete:
          - pause

      task3:
        action: std.echo output="Task 3"
"""


WORKBOOK_DIFFERENT_TASK_STATES = """
---
version: '2.0'

name: wb

workflows:
  wf1:
    type: direct

    tasks:
      task1:
        action: std.echo output="Hi!"
        on-complete:
          - task3
          - pause

      task2:
        action: std.async_noop
        # This one won't be finished when execution is already PAUSED.
        on-complete:
          - task4

      task3:
        action: std.echo output="Task 3"

      task4:
        action: std.echo output="Task 4"
"""


class WorkflowResumeTest(base.EngineTestCase):
    def setUp(self):
        super(WorkflowResumeTest, self).setUp()

        self.wb_spec = spec_parser.get_workbook_spec_from_yaml(RESUME_WORKBOOK)
        self.wf_spec = self.wb_spec.get_workflows()['wf1']

    def test_resume_direct(self):
        wb_service.create_workbook_v2(RESUME_WORKBOOK)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wb.wf1', {})

        self.await_workflow_paused(wf_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.PAUSED, wf_ex.state)
        self.assertEqual(2, len(wf_ex.task_executions))

        self.engine.resume_workflow(wf_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(2, len(wf_ex.task_executions))

        self.await_workflow_success(wf_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.SUCCESS, wf_ex.state)
        self.assertEqual(2, len(wf_ex.task_executions))

    def test_resume_reverse(self):
        wb_service.create_workbook_v2(RESUME_WORKBOOK_REVERSE)

        # Start workflow.
        wf_ex = self.engine.start_workflow(
            'resume_reverse.wf',
            {},
            task_name='task2'
        )

        # Note: We need to reread execution to access related tasks.

        self.engine.pause_workflow(wf_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.PAUSED, wf_ex.state)
        self.assertEqual(1, len(wf_ex.task_executions))

        self.engine.resume_workflow(wf_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.RUNNING, wf_ex.state)

        self.await_workflow_success(wf_ex.id)
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.SUCCESS, wf_ex.state)
        self.assertEqual(2, len(wf_ex.task_executions))

    def test_resume_two_branches(self):
        wb_service.create_workbook_v2(WORKBOOK_TWO_BRANCHES)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wb.wf1', {})

        self.await_workflow_paused(wf_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.PAUSED, wf_ex.state)
        self.assertEqual(3, len(wf_ex.task_executions))

        wf_ex = self.engine.resume_workflow(wf_ex.id)

        self.await_workflow_success(wf_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.SUCCESS, wf_ex.state)

        # We can see 3 tasks in execution.
        self.assertEqual(3, len(wf_ex.task_executions))

    def test_resume_two_start_tasks(self):
        wb_service.create_workbook_v2(WORKBOOK_TWO_START_TASKS)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wb.wf1', {})

        self.await_workflow_paused(wf_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.PAUSED, wf_ex.state)

        task_execs = wf_ex.task_executions

        # The exact number of tasks depends on which of two tasks
        # 'task1' and 'task2' completed earlier.
        self.assertGreaterEqual(len(task_execs), 2)

        task1_ex = self._assert_single_item(task_execs, name='task1')
        task2_ex = self._assert_single_item(task_execs, name='task2')

        self.await_task_success(task1_ex.id)
        self.await_task_success(task2_ex.id)

        self.engine.resume_workflow(wf_ex.id)

        self.await_workflow_success(wf_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.SUCCESS, wf_ex.state)
        self.assertEqual(3, len(wf_ex.task_executions))

    def test_resume_different_task_states(self):
        wb_service.create_workbook_v2(WORKBOOK_DIFFERENT_TASK_STATES)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wb.wf1', {})

        self.await_workflow_paused(wf_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.PAUSED, wf_ex.state)

        task_execs = wf_ex.task_executions

        self.assertEqual(3, len(task_execs))

        task2_ex = self._assert_single_item(task_execs, name='task2')

        # Task2 is not finished yet.
        self.assertFalse(states.is_completed(task2_ex.state))

        wf_ex = self.engine.resume_workflow(wf_ex.id)

        self.assertEqual(states.RUNNING, wf_ex.state)

        # Wait for task3 to be processed.
        task3_ex = self._assert_single_item(task_execs, name='task3')

        self.await_task_success(task3_ex.id)
        self.await_task_processed(task3_ex.id)

        # Finish task2.
        task2_action_ex = db_api.get_action_executions(
            task_execution_id=task2_ex.id
        )[0]

        self.engine.on_action_complete(task2_action_ex.id, utils.Result())

        self.await_workflow_success(wf_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.SUCCESS, wf_ex.state, wf_ex.state_info)
        self.assertEqual(4, len(wf_ex.task_executions))

    def test_resume_fails(self):
        # Start and pause workflow.
        wb_service.create_workbook_v2(WORKBOOK_DIFFERENT_TASK_STATES)

        wf_ex = self.engine.start_workflow('wb.wf1', {})

        self.await_workflow_paused(wf_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.PAUSED, wf_ex.state)

        # Simulate failure and check if it is handled.
        err = exc.MistralError('foo')

        with mock.patch.object(
                db_api,
                'get_workflow_execution',
                side_effect=err):

            self.assertRaises(
                exc.MistralError,
                self.engine.resume_workflow,
                wf_ex.id
            )

    def test_resume_diff_env_vars(self):
        wb_service.create_workbook_v2(RESUME_WORKBOOK_DIFF_ENV_VAR)

        # Initial environment variables for the workflow execution.
        env = {
            'var1': 'fee fi fo fum',
            'var2': 'foobar'
        }

        # Start workflow.
        wf_ex = self.engine.start_workflow('wb.wf1', {}, env=env)

        self.await_workflow_paused(wf_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        task_1_ex = self._assert_single_item(
            wf_ex.task_executions,
            name='task1'
        )

        task_2_ex = self._assert_single_item(
            wf_ex.task_executions,
            name='task2'
        )

        self.assertEqual(states.PAUSED, wf_ex.state)
        self.assertEqual(2, len(wf_ex.task_executions))
        self.assertDictEqual(env, wf_ex.params['env'])
        self.assertDictEqual(env, wf_ex.context['__env'])
        self.assertEqual(states.SUCCESS, task_1_ex.state)
        self.assertEqual(states.IDLE, task_2_ex.state)

        # Update env in workflow execution with the following.
        updated_env = {
            'var1': 'Task 2',
            'var2': 'Task 3'
        }

        # Update the env variables and resume workflow.
        self.engine.resume_workflow(wf_ex.id, env=updated_env)

        self.await_workflow_success(wf_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertDictEqual(updated_env, wf_ex.params['env'])
        self.assertDictEqual(updated_env, wf_ex.context['__env'])
        self.assertEqual(3, len(wf_ex.task_executions))

        # Check result of task2.
        task_2_ex = self._assert_single_item(
            wf_ex.task_executions,
            name='task2'
        )

        self.assertEqual(states.SUCCESS, task_2_ex.state)

        # Re-read task execution, otherwise lazy loading of action executions
        # may not work.
        with db_api.transaction():
            task_2_ex = db_api.get_task_execution(task_2_ex.id)

            task_2_result = data_flow.get_task_execution_result(task_2_ex)

        self.assertEqual(updated_env['var1'], task_2_result)

        # Check result of task3.
        task_3_ex = self._assert_single_item(
            wf_ex.task_executions,
            name='task3'
        )

        self.assertEqual(states.SUCCESS, task_3_ex.state)

        # Re-read task execution, otherwise lazy loading of action executions
        # may not work.
        with db_api.transaction():
            task_3_ex = db_api.get_task_execution(task_3_ex.id)

            task_3_result = data_flow.get_task_execution_result(task_3_ex)

        self.assertEqual(updated_env['var2'], task_3_result)
