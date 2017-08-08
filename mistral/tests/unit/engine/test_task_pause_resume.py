# Copyright 2015 - StackStorm, Inc.
# Copyright 2016 - Brocade Communications Systems, Inc.
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

from mistral.db.v2 import api as db_api
from mistral.services import workflows as wf_service
from mistral.tests.unit.engine import base
from mistral.workflow import states
from mistral_lib import actions as ml_actions


class TaskPauseResumeTest(base.EngineTestCase):

    def test_pause_resume_action_ex(self):
        workflow = """
        version: '2.0'

        wf:
          tasks:
            task1:
              action: std.async_noop
              on-success:
                - task2
            task2:
              action: std.noop
        """

        wf_service.create_workflows(workflow)

        wf_ex = self.engine.start_workflow('wf')

        self.await_workflow_state(wf_ex.id, states.RUNNING)

        with db_api.transaction():
            wf_execs = db_api.get_workflow_executions()

            wf_ex = self._assert_single_item(wf_execs, name='wf')

            task_execs = wf_ex.task_executions

            task_1_ex = self._assert_single_item(
                wf_ex.task_executions,
                name='task1'
            )

        task_1_action_exs = db_api.get_action_executions(
            task_execution_id=task_1_ex.id
        )

        self.assertEqual(states.RUNNING, wf_ex.state)
        self.assertEqual(1, len(task_execs))
        self.assertEqual(states.RUNNING, task_1_ex.state)
        self.assertEqual(1, len(task_1_action_exs))
        self.assertEqual(states.RUNNING, task_1_action_exs[0].state)

        # Pause the action execution of task 1.
        self.engine.on_action_update(task_1_action_exs[0].id, states.PAUSED)

        self.await_task_paused(task_1_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_execs = wf_ex.task_executions

            task_1_ex = self._assert_single_item(
                wf_ex.task_executions,
                name='task1'
            )

        task_1_action_exs = db_api.get_action_executions(
            task_execution_id=task_1_ex.id
        )

        self.assertEqual(states.PAUSED, wf_ex.state)
        self.assertEqual(1, len(task_execs))
        self.assertEqual(states.PAUSED, task_1_ex.state)
        self.assertEqual(1, len(task_1_action_exs))
        self.assertEqual(states.PAUSED, task_1_action_exs[0].state)

        # Resume the action execution of task 1.
        self.engine.on_action_update(task_1_action_exs[0].id, states.RUNNING)

        self.await_task_running(task_1_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_1_ex = self._assert_single_item(
                wf_ex.task_executions,
                name='task1'
            )

        task_1_action_exs = db_api.get_action_executions(
            task_execution_id=task_1_ex.id
        )

        self.assertEqual(states.RUNNING, wf_ex.state)
        self.assertEqual(1, len(task_execs))
        self.assertEqual(states.RUNNING, task_1_ex.state)
        self.assertEqual(1, len(task_1_action_exs))
        self.assertEqual(states.RUNNING, task_1_action_exs[0].state)

        # Complete action execution of task 1.
        self.engine.on_action_complete(
            task_1_action_exs[0].id,
            ml_actions.Result(data={'result': 'foobar'})
        )

        # Wait for the workflow execution to complete.
        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_execs = wf_ex.task_executions

        task_1_ex = self._assert_single_item(task_execs, name='task1')

        task_1_action_exs = db_api.get_action_executions(
            task_execution_id=task_1_ex.id
        )

        task_2_ex = self._assert_single_item(task_execs, name='task2')

        self.assertEqual(states.SUCCESS, wf_ex.state)
        self.assertEqual(2, len(task_execs))
        self.assertEqual(states.SUCCESS, task_1_ex.state)
        self.assertEqual(1, len(task_1_action_exs))
        self.assertEqual(states.SUCCESS, task_1_action_exs[0].state)
        self.assertEqual(states.SUCCESS, task_2_ex.state)

    def test_pause_resume_action_ex_with_items_task(self):
        workflow = """
        version: '2.0'

        wf:
          tasks:
            task1:
              with-items: i in <% range(3) %>
              action: std.async_noop
              on-success:
                - task2
            task2:
              action: std.noop
        """

        wf_service.create_workflows(workflow)

        wf_ex = self.engine.start_workflow('wf')

        self.await_workflow_state(wf_ex.id, states.RUNNING)

        with db_api.transaction():
            wf_execs = db_api.get_workflow_executions()

            wf_ex = self._assert_single_item(wf_execs, name='wf')

            task_execs = wf_ex.task_executions

            task_1_ex = self._assert_single_item(
                wf_ex.task_executions,
                name='task1'
            )

        task_1_action_exs = sorted(
            db_api.get_action_executions(task_execution_id=task_1_ex.id),
            key=lambda x: x['runtime_context']['index']
        )

        self.assertEqual(states.RUNNING, wf_ex.state)
        self.assertEqual(1, len(task_execs))
        self.assertEqual(states.RUNNING, task_1_ex.state)
        self.assertEqual(3, len(task_1_action_exs))
        self.assertEqual(states.RUNNING, task_1_action_exs[0].state)
        self.assertEqual(states.RUNNING, task_1_action_exs[1].state)
        self.assertEqual(states.RUNNING, task_1_action_exs[2].state)

        # Pause the 1st action execution of task 1.
        self.engine.on_action_update(task_1_action_exs[0].id, states.PAUSED)

        self.await_task_paused(task_1_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_execs = wf_ex.task_executions

            task_1_ex = self._assert_single_item(
                wf_ex.task_executions,
                name='task1'
            )

        task_1_action_exs = sorted(
            db_api.get_action_executions(task_execution_id=task_1_ex.id),
            key=lambda x: x['runtime_context']['index']
        )

        self.assertEqual(states.PAUSED, wf_ex.state)
        self.assertEqual(1, len(task_execs))
        self.assertEqual(states.PAUSED, task_1_ex.state)
        self.assertEqual(3, len(task_1_action_exs))
        self.assertEqual(states.PAUSED, task_1_action_exs[0].state)
        self.assertEqual(states.RUNNING, task_1_action_exs[1].state)
        self.assertEqual(states.RUNNING, task_1_action_exs[2].state)

        # Complete 2nd and 3rd action executions of task 1.
        self.engine.on_action_complete(
            task_1_action_exs[1].id,
            ml_actions.Result(data={'result': 'two'})
        )

        self.engine.on_action_complete(
            task_1_action_exs[2].id,
            ml_actions.Result(data={'result': 'three'})
        )

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_execs = wf_ex.task_executions

            task_1_ex = self._assert_single_item(
                wf_ex.task_executions,
                name='task1'
            )

        task_1_action_exs = sorted(
            db_api.get_action_executions(task_execution_id=task_1_ex.id),
            key=lambda x: x['runtime_context']['index']
        )

        self.assertEqual(states.PAUSED, wf_ex.state)
        self.assertEqual(1, len(task_execs))
        self.assertEqual(states.PAUSED, task_1_ex.state)
        self.assertEqual(3, len(task_1_action_exs))
        self.assertEqual(states.PAUSED, task_1_action_exs[0].state)
        self.assertEqual(states.SUCCESS, task_1_action_exs[1].state)
        self.assertEqual(states.SUCCESS, task_1_action_exs[2].state)

        # Resume the 1st action execution of task 1.
        self.engine.on_action_update(task_1_action_exs[0].id, states.RUNNING)

        self.await_task_running(task_1_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_1_ex = self._assert_single_item(
                wf_ex.task_executions,
                name='task1'
            )

        task_1_action_exs = sorted(
            db_api.get_action_executions(task_execution_id=task_1_ex.id),
            key=lambda x: x['runtime_context']['index']
        )

        self.assertEqual(states.RUNNING, wf_ex.state)
        self.assertEqual(1, len(task_execs))
        self.assertEqual(states.RUNNING, task_1_ex.state)
        self.assertEqual(3, len(task_1_action_exs))
        self.assertEqual(states.RUNNING, task_1_action_exs[0].state)
        self.assertEqual(states.SUCCESS, task_1_action_exs[1].state)
        self.assertEqual(states.SUCCESS, task_1_action_exs[2].state)

        # Complete the 1st action execution of task 1.
        self.engine.on_action_complete(
            task_1_action_exs[0].id,
            ml_actions.Result(data={'result': 'foobar'})
        )

        # Wait for the workflow execution to complete.
        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_execs = wf_ex.task_executions

        task_1_ex = self._assert_single_item(task_execs, name='task1')

        task_1_action_exs = sorted(
            db_api.get_action_executions(task_execution_id=task_1_ex.id),
            key=lambda x: x['runtime_context']['index']
        )

        task_2_ex = self._assert_single_item(task_execs, name='task2')

        self.assertEqual(states.SUCCESS, wf_ex.state)
        self.assertEqual(2, len(task_execs))
        self.assertEqual(states.SUCCESS, task_1_ex.state)
        self.assertEqual(3, len(task_1_action_exs))
        self.assertEqual(states.SUCCESS, task_1_action_exs[0].state)
        self.assertEqual(states.SUCCESS, task_1_action_exs[1].state)
        self.assertEqual(states.SUCCESS, task_1_action_exs[2].state)
        self.assertEqual(states.SUCCESS, task_2_ex.state)
