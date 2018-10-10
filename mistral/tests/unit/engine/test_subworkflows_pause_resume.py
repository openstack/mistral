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
from mistral.services import workbooks as wb_service
from mistral.tests.unit.engine import base
from mistral.workflow import states
from mistral_lib import actions as ml_actions


class SubworkflowPauseResumeTest(base.EngineTestCase):

    def test_pause_resume_cascade_down_to_subworkflow(self):
        workbook = """
        version: '2.0'
        name: wb
        workflows:
          wf1:
            tasks:
              task1:
                workflow: wf2
                on-success:
                  - task3
              task2:
                workflow: wf3
                on-success:
                  - task3
              task3:
                join: all
                action: std.noop
          wf2:
            tasks:
              task1:
                action: std.async_noop
                on-success:
                  - task2
              task2:
                action: std.noop
          wf3:
            tasks:
              task1:
                action: std.async_noop
                on-success:
                  - task2
              task2:
                action: std.noop
        """

        wb_service.create_workbook_v2(workbook)

        # Start workflow execution.
        wf_1_ex = self.engine.start_workflow('wb.wf1')

        self.await_workflow_state(wf_1_ex.id, states.RUNNING)

        with db_api.transaction():
            wf_execs = db_api.get_workflow_executions()

            # Get objects for the parent workflow execution.
            wf_1_ex = self._assert_single_item(wf_execs, name='wb.wf1')

            wf_1_task_execs = wf_1_ex.task_executions

            wf_1_task_1_ex = self._assert_single_item(
                wf_1_ex.task_executions,
                name='task1'
            )

            wf_1_task_1_action_exs = wf_1_task_1_ex.executions

            wf_1_task_2_ex = self._assert_single_item(
                wf_1_ex.task_executions,
                name='task2'
            )

            wf_1_task_2_action_exs = wf_1_task_2_ex.executions

            # Get objects for the subworkflow executions.
            wf_2_ex = self._assert_single_item(wf_execs, name='wb.wf2')

            wf_2_task_execs = wf_2_ex.task_executions

            wf_2_task_1_ex = self._assert_single_item(
                wf_2_ex.task_executions,
                name='task1'
            )

            wf_2_task_1_action_exs = db_api.get_action_executions(
                task_execution_id=wf_2_task_1_ex.id
            )

            wf_3_ex = self._assert_single_item(wf_execs, name='wb.wf3')

            wf_3_task_execs = wf_3_ex.task_executions

            wf_3_task_1_ex = self._assert_single_item(
                wf_3_ex.task_executions,
                name='task1'
            )

            wf_3_task_1_action_exs = db_api.get_action_executions(
                task_execution_id=wf_3_task_1_ex.id
            )

        self.assertEqual(states.RUNNING, wf_1_ex.state)
        self.assertEqual(2, len(wf_1_task_execs))
        self.assertEqual(states.RUNNING, wf_1_task_1_ex.state)
        self.assertEqual(states.RUNNING, wf_1_task_2_ex.state)
        self.assertEqual(1, len(wf_1_task_1_action_exs))
        self.assertEqual(states.RUNNING, wf_1_task_1_action_exs[0].state)
        self.assertEqual(wf_1_task_1_action_exs[0].id, wf_2_ex.id)
        self.assertEqual(1, len(wf_1_task_2_action_exs))
        self.assertEqual(states.RUNNING, wf_1_task_2_action_exs[0].state)
        self.assertEqual(wf_1_task_2_action_exs[0].id, wf_3_ex.id)
        self.assertEqual(states.RUNNING, wf_2_ex.state)
        self.assertEqual(1, len(wf_2_task_execs))
        self.assertEqual(states.RUNNING, wf_2_task_1_ex.state)
        self.assertEqual(1, len(wf_2_task_1_action_exs))
        self.assertEqual(states.RUNNING, wf_2_task_1_action_exs[0].state)
        self.assertEqual(states.RUNNING, wf_3_ex.state)
        self.assertEqual(1, len(wf_3_task_execs))
        self.assertEqual(states.RUNNING, wf_3_task_1_ex.state)
        self.assertEqual(1, len(wf_3_task_1_action_exs))
        self.assertEqual(states.RUNNING, wf_3_task_1_action_exs[0].state)

        # Pause the main workflow.
        self.engine.pause_workflow(wf_1_ex.id)

        self.await_workflow_paused(wf_1_ex.id)
        self.await_workflow_paused(wf_2_ex.id)
        self.await_workflow_paused(wf_3_ex.id)

        with db_api.transaction():
            wf_execs = db_api.get_workflow_executions()

            # Get objects for the parent workflow execution.
            wf_1_ex = self._assert_single_item(wf_execs, name='wb.wf1')

            wf_1_task_execs = wf_1_ex.task_executions

            wf_1_task_1_ex = self._assert_single_item(
                wf_1_ex.task_executions,
                name='task1'
            )

            wf_1_task_1_action_exs = wf_1_task_1_ex.executions

            wf_1_task_2_ex = self._assert_single_item(
                wf_1_ex.task_executions,
                name='task2'
            )

            wf_1_task_2_action_exs = wf_1_task_2_ex.executions

            # Get objects for the subworkflow executions.
            wf_2_ex = self._assert_single_item(wf_execs, name='wb.wf2')

            wf_2_task_execs = wf_2_ex.task_executions

            wf_2_task_1_ex = self._assert_single_item(
                wf_2_ex.task_executions,
                name='task1'
            )

            wf_2_task_1_action_exs = db_api.get_action_executions(
                task_execution_id=wf_2_task_1_ex.id
            )

            wf_3_ex = self._assert_single_item(wf_execs, name='wb.wf3')

            wf_3_task_execs = wf_3_ex.task_executions

            wf_3_task_1_ex = self._assert_single_item(
                wf_3_ex.task_executions,
                name='task1'
            )

            wf_3_task_1_action_exs = db_api.get_action_executions(
                task_execution_id=wf_3_task_1_ex.id
            )

        self.assertEqual(states.PAUSED, wf_2_ex.state)
        self.assertEqual(states.RUNNING, wf_2_task_1_ex.state)
        self.assertEqual(states.RUNNING, wf_2_task_1_action_exs[0].state)
        self.assertEqual(states.PAUSED, wf_3_ex.state)
        self.assertEqual(states.RUNNING, wf_3_task_1_ex.state)
        self.assertEqual(states.RUNNING, wf_3_task_1_action_exs[0].state)
        self.assertEqual(states.PAUSED, wf_1_task_1_action_exs[0].state)
        self.assertEqual(states.PAUSED, wf_1_task_1_ex.state)
        self.assertEqual(states.PAUSED, wf_1_task_2_action_exs[0].state)
        self.assertEqual(states.PAUSED, wf_1_task_2_ex.state)
        self.assertEqual(states.PAUSED, wf_1_ex.state)

        # Resume the main workflow.
        self.engine.resume_workflow(wf_1_ex.id)

        self.await_workflow_running(wf_1_ex.id)
        self.await_workflow_running(wf_2_ex.id)
        self.await_workflow_running(wf_3_ex.id)

        with db_api.transaction():
            wf_execs = db_api.get_workflow_executions()

            # Get objects for the parent workflow execution.
            wf_1_ex = self._assert_single_item(wf_execs, name='wb.wf1')

            wf_1_task_execs = wf_1_ex.task_executions

            wf_1_task_1_ex = self._assert_single_item(
                wf_1_ex.task_executions,
                name='task1'
            )

            wf_1_task_1_action_exs = wf_1_task_1_ex.executions

            wf_1_task_2_ex = self._assert_single_item(
                wf_1_ex.task_executions,
                name='task2'
            )

            wf_1_task_2_action_exs = wf_1_task_2_ex.executions

            # Get objects for the subworkflow executions.
            wf_2_ex = self._assert_single_item(wf_execs, name='wb.wf2')

            wf_2_task_execs = wf_2_ex.task_executions

            wf_2_task_1_ex = self._assert_single_item(
                wf_2_ex.task_executions,
                name='task1'
            )

            wf_2_task_1_action_exs = db_api.get_action_executions(
                task_execution_id=wf_2_task_1_ex.id
            )

            wf_3_ex = self._assert_single_item(wf_execs, name='wb.wf3')

            wf_3_task_execs = wf_3_ex.task_executions

            wf_3_task_1_ex = self._assert_single_item(
                wf_3_ex.task_executions,
                name='task1'
            )

            wf_3_task_1_action_exs = db_api.get_action_executions(
                task_execution_id=wf_3_task_1_ex.id
            )

        self.assertEqual(states.RUNNING, wf_2_ex.state)
        self.assertEqual(states.RUNNING, wf_2_task_1_ex.state)
        self.assertEqual(states.RUNNING, wf_2_task_1_action_exs[0].state)
        self.assertEqual(states.RUNNING, wf_3_ex.state)
        self.assertEqual(states.RUNNING, wf_3_task_1_ex.state)
        self.assertEqual(states.RUNNING, wf_3_task_1_action_exs[0].state)
        self.assertEqual(states.RUNNING, wf_1_task_1_action_exs[0].state)
        self.assertEqual(states.RUNNING, wf_1_task_1_ex.state)
        self.assertEqual(states.RUNNING, wf_1_task_2_action_exs[0].state)
        self.assertEqual(states.RUNNING, wf_1_task_2_ex.state)
        self.assertEqual(states.RUNNING, wf_1_ex.state)

        # Complete action executions of the subworkflows.
        self.engine.on_action_complete(
            wf_2_task_1_action_exs[0].id,
            ml_actions.Result(data={'result': 'foobar'})
        )

        self.engine.on_action_complete(
            wf_3_task_1_action_exs[0].id,
            ml_actions.Result(data={'result': 'foobar'})
        )

        self.await_workflow_success(wf_2_ex.id)
        self.await_workflow_success(wf_3_ex.id)
        self.await_workflow_success(wf_1_ex.id)

        with db_api.transaction():
            wf_execs = db_api.get_workflow_executions()

            # Get objects for the parent workflow execution.
            wf_1_ex = self._assert_single_item(wf_execs, name='wb.wf1')

            wf_1_task_execs = wf_1_ex.task_executions

            wf_1_task_1_ex = self._assert_single_item(
                wf_1_ex.task_executions,
                name='task1'
            )

            wf_1_task_1_action_exs = wf_1_task_1_ex.executions

            wf_1_task_2_ex = self._assert_single_item(
                wf_1_ex.task_executions,
                name='task2'
            )

            wf_1_task_2_action_exs = wf_1_task_2_ex.executions

            wf_1_task_3_ex = self._assert_single_item(
                wf_1_ex.task_executions,
                name='task3'
            )

            # Get objects for the subworkflow executions.
            wf_2_ex = self._assert_single_item(wf_execs, name='wb.wf2')

            wf_2_task_execs = wf_2_ex.task_executions

            wf_2_task_1_ex = self._assert_single_item(
                wf_2_ex.task_executions,
                name='task1'
            )

            wf_2_task_1_action_exs = db_api.get_action_executions(
                task_execution_id=wf_2_task_1_ex.id
            )

            wf_2_task_2_ex = self._assert_single_item(
                wf_2_ex.task_executions,
                name='task2'
            )

            wf_3_ex = self._assert_single_item(wf_execs, name='wb.wf3')

            wf_3_task_execs = wf_3_ex.task_executions

            wf_3_task_1_ex = self._assert_single_item(
                wf_3_ex.task_executions,
                name='task1'
            )

            wf_3_task_1_action_exs = db_api.get_action_executions(
                task_execution_id=wf_3_task_1_ex.id
            )

            wf_3_task_2_ex = self._assert_single_item(
                wf_3_ex.task_executions,
                name='task2'
            )

        self.assertEqual(states.SUCCESS, wf_1_ex.state)
        self.assertEqual(3, len(wf_1_task_execs))
        self.assertEqual(states.SUCCESS, wf_1_task_1_ex.state)
        self.assertEqual(states.SUCCESS, wf_1_task_2_ex.state)
        self.assertEqual(states.SUCCESS, wf_1_task_3_ex.state)
        self.assertEqual(states.SUCCESS, wf_1_task_1_action_exs[0].state)
        self.assertEqual(states.SUCCESS, wf_1_task_2_action_exs[0].state)
        self.assertEqual(states.SUCCESS, wf_2_ex.state)
        self.assertEqual(2, len(wf_2_task_execs))
        self.assertEqual(states.SUCCESS, wf_2_task_1_ex.state)
        self.assertEqual(states.SUCCESS, wf_2_task_2_ex.state)
        self.assertEqual(states.SUCCESS, wf_3_ex.state)
        self.assertEqual(2, len(wf_3_task_execs))
        self.assertEqual(states.SUCCESS, wf_3_task_1_ex.state)
        self.assertEqual(states.SUCCESS, wf_3_task_2_ex.state)

    def test_pause_resume_cascade_up_from_subworkflow(self):
        workbook = """
        version: '2.0'
        name: wb
        workflows:
          wf1:
            tasks:
              task1:
                workflow: wf2
                on-success:
                  - task3
              task2:
                workflow: wf3
                on-success:
                  - task3
              task3:
                join: all
                action: std.noop
          wf2:
            tasks:
              task1:
                action: std.async_noop
                on-success:
                  - task2
              task2:
                action: std.noop
          wf3:
            tasks:
              task1:
                action: std.async_noop
                on-success:
                  - task2
              task2:
                action: std.noop
        """

        wb_service.create_workbook_v2(workbook)

        # Start workflow execution.
        wf_1_ex = self.engine.start_workflow('wb.wf1')

        self.await_workflow_state(wf_1_ex.id, states.RUNNING)

        with db_api.transaction():
            wf_execs = db_api.get_workflow_executions()

            # Get objects for the parent workflow execution.
            wf_1_ex = self._assert_single_item(wf_execs, name='wb.wf1')

            wf_1_task_execs = wf_1_ex.task_executions

            wf_1_task_1_ex = self._assert_single_item(
                wf_1_ex.task_executions,
                name='task1'
            )

            wf_1_task_1_action_exs = wf_1_task_1_ex.executions

            wf_1_task_2_ex = self._assert_single_item(
                wf_1_ex.task_executions,
                name='task2'
            )

            wf_1_task_2_action_exs = wf_1_task_2_ex.executions

            # Get objects for the subworkflow executions.
            wf_2_ex = self._assert_single_item(wf_execs, name='wb.wf2')

            wf_2_task_execs = wf_2_ex.task_executions

            wf_2_task_1_ex = self._assert_single_item(
                wf_2_ex.task_executions,
                name='task1'
            )

            wf_2_task_1_action_exs = db_api.get_action_executions(
                task_execution_id=wf_2_task_1_ex.id
            )

            wf_3_ex = self._assert_single_item(wf_execs, name='wb.wf3')

            wf_3_task_execs = wf_3_ex.task_executions

            wf_3_task_1_ex = self._assert_single_item(
                wf_3_ex.task_executions,
                name='task1'
            )

            wf_3_task_1_action_exs = db_api.get_action_executions(
                task_execution_id=wf_3_task_1_ex.id
            )

        self.assertEqual(states.RUNNING, wf_1_ex.state)
        self.assertEqual(2, len(wf_1_task_execs))
        self.assertEqual(states.RUNNING, wf_1_task_1_ex.state)
        self.assertEqual(states.RUNNING, wf_1_task_2_ex.state)
        self.assertEqual(1, len(wf_1_task_1_action_exs))
        self.assertEqual(states.RUNNING, wf_1_task_1_action_exs[0].state)
        self.assertEqual(wf_1_task_1_action_exs[0].id, wf_2_ex.id)
        self.assertEqual(1, len(wf_1_task_2_action_exs))
        self.assertEqual(states.RUNNING, wf_1_task_2_action_exs[0].state)
        self.assertEqual(wf_1_task_2_action_exs[0].id, wf_3_ex.id)
        self.assertEqual(states.RUNNING, wf_2_ex.state)
        self.assertEqual(1, len(wf_2_task_execs))
        self.assertEqual(states.RUNNING, wf_2_task_1_ex.state)
        self.assertEqual(1, len(wf_2_task_1_action_exs))
        self.assertEqual(states.RUNNING, wf_2_task_1_action_exs[0].state)
        self.assertEqual(states.RUNNING, wf_3_ex.state)
        self.assertEqual(1, len(wf_3_task_execs))
        self.assertEqual(states.RUNNING, wf_3_task_1_ex.state)
        self.assertEqual(1, len(wf_3_task_1_action_exs))
        self.assertEqual(states.RUNNING, wf_3_task_1_action_exs[0].state)

        # Pause the subworkflow.
        self.engine.pause_workflow(wf_2_ex.id)

        self.await_workflow_paused(wf_2_ex.id)

        with db_api.transaction():
            wf_execs = db_api.get_workflow_executions()

            # Get objects for the parent workflow execution.
            wf_1_ex = self._assert_single_item(wf_execs, name='wb.wf1')

            wf_1_task_execs = wf_1_ex.task_executions

            wf_1_task_1_ex = self._assert_single_item(
                wf_1_ex.task_executions,
                name='task1'
            )

            wf_1_task_1_action_exs = wf_1_task_1_ex.executions

            wf_1_task_2_ex = self._assert_single_item(
                wf_1_ex.task_executions,
                name='task2'
            )

            wf_1_task_2_action_exs = wf_1_task_2_ex.executions

            # Get objects for the subworkflow executions.
            wf_2_ex = self._assert_single_item(wf_execs, name='wb.wf2')

            wf_2_task_execs = wf_2_ex.task_executions

            wf_2_task_1_ex = self._assert_single_item(
                wf_2_ex.task_executions,
                name='task1'
            )

            wf_2_task_1_action_exs = db_api.get_action_executions(
                task_execution_id=wf_2_task_1_ex.id
            )

            wf_3_ex = self._assert_single_item(wf_execs, name='wb.wf3')

            wf_3_task_execs = wf_3_ex.task_executions

            wf_3_task_1_ex = self._assert_single_item(
                wf_3_ex.task_executions,
                name='task1'
            )

            wf_3_task_1_action_exs = db_api.get_action_executions(
                task_execution_id=wf_3_task_1_ex.id
            )

        self.assertEqual(states.PAUSED, wf_2_ex.state)
        self.assertEqual(states.RUNNING, wf_2_task_1_ex.state)
        self.assertEqual(states.RUNNING, wf_2_task_1_action_exs[0].state)
        self.assertEqual(states.PAUSED, wf_3_ex.state)
        self.assertEqual(states.RUNNING, wf_3_task_1_ex.state)
        self.assertEqual(states.RUNNING, wf_3_task_1_action_exs[0].state)
        self.assertEqual(states.PAUSED, wf_1_task_1_action_exs[0].state)
        self.assertEqual(states.PAUSED, wf_1_task_1_ex.state)
        self.assertEqual(states.PAUSED, wf_1_task_2_action_exs[0].state)
        self.assertEqual(states.PAUSED, wf_1_task_2_ex.state)
        self.assertEqual(states.PAUSED, wf_1_ex.state)

        # Resume the 1st subworkflow.
        self.engine.resume_workflow(wf_2_ex.id)

        self.await_workflow_running(wf_2_ex.id)

        with db_api.transaction():
            wf_execs = db_api.get_workflow_executions()

            # Get objects for the parent workflow execution.
            wf_1_ex = self._assert_single_item(wf_execs, name='wb.wf1')

            wf_1_task_execs = wf_1_ex.task_executions

            wf_1_task_1_ex = self._assert_single_item(
                wf_1_ex.task_executions,
                name='task1'
            )

            wf_1_task_1_action_exs = wf_1_task_1_ex.executions

            wf_1_task_2_ex = self._assert_single_item(
                wf_1_ex.task_executions,
                name='task2'
            )

            wf_1_task_2_action_exs = wf_1_task_2_ex.executions

            # Get objects for the subworkflow executions.
            wf_2_ex = self._assert_single_item(wf_execs, name='wb.wf2')

            wf_2_task_execs = wf_2_ex.task_executions

            wf_2_task_1_ex = self._assert_single_item(
                wf_2_ex.task_executions,
                name='task1'
            )

            wf_2_task_1_action_exs = db_api.get_action_executions(
                task_execution_id=wf_2_task_1_ex.id
            )

            wf_3_ex = self._assert_single_item(wf_execs, name='wb.wf3')

            wf_3_task_execs = wf_3_ex.task_executions

            wf_3_task_1_ex = self._assert_single_item(
                wf_3_ex.task_executions,
                name='task1'
            )

            wf_3_task_1_action_exs = db_api.get_action_executions(
                task_execution_id=wf_3_task_1_ex.id
            )

        self.assertEqual(states.RUNNING, wf_2_ex.state)
        self.assertEqual(states.RUNNING, wf_2_task_1_ex.state)
        self.assertEqual(states.RUNNING, wf_2_task_1_action_exs[0].state)
        self.assertEqual(states.PAUSED, wf_3_ex.state)
        self.assertEqual(states.RUNNING, wf_3_task_1_ex.state)
        self.assertEqual(states.RUNNING, wf_3_task_1_action_exs[0].state)
        self.assertEqual(states.RUNNING, wf_1_task_1_action_exs[0].state)
        self.assertEqual(states.RUNNING, wf_1_task_1_ex.state)
        self.assertEqual(states.PAUSED, wf_1_task_2_action_exs[0].state)
        self.assertEqual(states.PAUSED, wf_1_task_2_ex.state)
        self.assertEqual(states.PAUSED, wf_1_ex.state)

        # Complete action execution of 1st subworkflow.
        self.engine.on_action_complete(
            wf_2_task_1_action_exs[0].id,
            ml_actions.Result(data={'result': 'foobar'})
        )

        self.await_workflow_success(wf_2_ex.id)
        self.await_task_success(wf_1_task_1_ex.id)

        with db_api.transaction():
            wf_execs = db_api.get_workflow_executions()

            # Get objects for the parent workflow execution.
            wf_1_ex = self._assert_single_item(wf_execs, name='wb.wf1')

            wf_1_task_execs = wf_1_ex.task_executions

            wf_1_task_1_ex = self._assert_single_item(
                wf_1_ex.task_executions,
                name='task1'
            )

            wf_1_task_1_action_exs = wf_1_task_1_ex.executions

            wf_1_task_2_ex = self._assert_single_item(
                wf_1_ex.task_executions,
                name='task2'
            )

            wf_1_task_2_action_exs = wf_1_task_2_ex.executions

            # Get objects for the subworkflow executions.
            wf_2_ex = self._assert_single_item(wf_execs, name='wb.wf2')

            wf_2_task_execs = wf_2_ex.task_executions

            wf_2_task_1_ex = self._assert_single_item(
                wf_2_ex.task_executions,
                name='task1'
            )

            wf_2_task_1_action_exs = db_api.get_action_executions(
                task_execution_id=wf_2_task_1_ex.id
            )

            wf_3_ex = self._assert_single_item(wf_execs, name='wb.wf3')

            wf_3_task_execs = wf_3_ex.task_executions

            wf_3_task_1_ex = self._assert_single_item(
                wf_3_ex.task_executions,
                name='task1'
            )

            wf_3_task_1_action_exs = db_api.get_action_executions(
                task_execution_id=wf_3_task_1_ex.id
            )

        self.assertEqual(states.SUCCESS, wf_2_ex.state)
        self.assertEqual(states.SUCCESS, wf_2_task_1_ex.state)
        self.assertEqual(states.SUCCESS, wf_2_task_1_action_exs[0].state)
        self.assertEqual(states.PAUSED, wf_3_ex.state)
        self.assertEqual(states.RUNNING, wf_3_task_1_ex.state)
        self.assertEqual(states.RUNNING, wf_3_task_1_action_exs[0].state)
        self.assertEqual(states.SUCCESS, wf_1_task_1_action_exs[0].state)
        self.assertEqual(states.SUCCESS, wf_1_task_1_ex.state)
        self.assertEqual(states.PAUSED, wf_1_task_2_action_exs[0].state)
        self.assertEqual(states.PAUSED, wf_1_task_2_ex.state)
        self.assertEqual(states.PAUSED, wf_1_ex.state)

        # Resume the 2nd subworkflow.
        self.engine.resume_workflow(wf_3_ex.id)

        self.await_workflow_running(wf_3_ex.id)

        with db_api.transaction():
            wf_execs = db_api.get_workflow_executions()

            # Get objects for the parent workflow execution.
            wf_1_ex = self._assert_single_item(wf_execs, name='wb.wf1')

            wf_1_task_execs = wf_1_ex.task_executions

            wf_1_task_1_ex = self._assert_single_item(
                wf_1_ex.task_executions,
                name='task1'
            )

            wf_1_task_1_action_exs = wf_1_task_1_ex.executions

            wf_1_task_2_ex = self._assert_single_item(
                wf_1_ex.task_executions,
                name='task2'
            )

            wf_1_task_2_action_exs = wf_1_task_2_ex.executions

            # Get objects for the subworkflow executions.
            wf_2_ex = self._assert_single_item(wf_execs, name='wb.wf2')

            wf_2_task_execs = wf_2_ex.task_executions

            wf_2_task_1_ex = self._assert_single_item(
                wf_2_ex.task_executions,
                name='task1'
            )

            wf_2_task_1_action_exs = db_api.get_action_executions(
                task_execution_id=wf_2_task_1_ex.id
            )

            wf_3_ex = self._assert_single_item(wf_execs, name='wb.wf3')

            wf_3_task_execs = wf_3_ex.task_executions

            wf_3_task_1_ex = self._assert_single_item(
                wf_3_ex.task_executions,
                name='task1'
            )

            wf_3_task_1_action_exs = db_api.get_action_executions(
                task_execution_id=wf_3_task_1_ex.id
            )

        self.assertEqual(states.SUCCESS, wf_2_ex.state)
        self.assertEqual(states.SUCCESS, wf_2_task_1_ex.state)
        self.assertEqual(states.SUCCESS, wf_2_task_1_action_exs[0].state)
        self.assertEqual(states.RUNNING, wf_3_ex.state)
        self.assertEqual(states.RUNNING, wf_3_task_1_ex.state)
        self.assertEqual(states.RUNNING, wf_3_task_1_action_exs[0].state)
        self.assertEqual(states.SUCCESS, wf_1_task_1_action_exs[0].state)
        self.assertEqual(states.SUCCESS, wf_1_task_1_ex.state)
        self.assertEqual(states.RUNNING, wf_1_task_2_action_exs[0].state)
        self.assertEqual(states.RUNNING, wf_1_task_2_ex.state)
        self.assertEqual(states.RUNNING, wf_1_ex.state)

        # Complete action execution of 2nd subworkflow.
        self.engine.on_action_complete(
            wf_3_task_1_action_exs[0].id,
            ml_actions.Result(data={'result': 'foobar'})
        )

        self.await_workflow_success(wf_3_ex.id)
        self.await_workflow_success(wf_1_ex.id)

        with db_api.transaction():
            wf_execs = db_api.get_workflow_executions()

            # Get objects for the parent workflow execution.
            wf_1_ex = self._assert_single_item(wf_execs, name='wb.wf1')

            wf_1_task_execs = wf_1_ex.task_executions

            wf_1_task_1_ex = self._assert_single_item(
                wf_1_ex.task_executions,
                name='task1'
            )

            wf_1_task_1_action_exs = wf_1_task_1_ex.executions

            wf_1_task_2_ex = self._assert_single_item(
                wf_1_ex.task_executions,
                name='task2'
            )

            wf_1_task_2_action_exs = wf_1_task_2_ex.executions

            wf_1_task_3_ex = self._assert_single_item(
                wf_1_ex.task_executions,
                name='task3'
            )

            # Get objects for the subworkflow executions.
            wf_2_ex = self._assert_single_item(wf_execs, name='wb.wf2')

            wf_2_task_execs = wf_2_ex.task_executions

            wf_2_task_1_ex = self._assert_single_item(
                wf_2_ex.task_executions,
                name='task1'
            )

            wf_2_task_1_action_exs = db_api.get_action_executions(
                task_execution_id=wf_2_task_1_ex.id
            )

            wf_2_task_2_ex = self._assert_single_item(
                wf_2_ex.task_executions,
                name='task2'
            )

            wf_3_ex = self._assert_single_item(wf_execs, name='wb.wf3')

            wf_3_task_execs = wf_3_ex.task_executions

            wf_3_task_1_ex = self._assert_single_item(
                wf_3_ex.task_executions,
                name='task1'
            )

            wf_3_task_1_action_exs = db_api.get_action_executions(
                task_execution_id=wf_3_task_1_ex.id
            )

            wf_3_task_2_ex = self._assert_single_item(
                wf_3_ex.task_executions,
                name='task2'
            )

        self.assertEqual(states.SUCCESS, wf_1_ex.state)
        self.assertEqual(3, len(wf_1_task_execs))
        self.assertEqual(states.SUCCESS, wf_1_task_1_ex.state)
        self.assertEqual(states.SUCCESS, wf_1_task_2_ex.state)
        self.assertEqual(states.SUCCESS, wf_1_task_3_ex.state)
        self.assertEqual(states.SUCCESS, wf_1_task_1_action_exs[0].state)
        self.assertEqual(states.SUCCESS, wf_1_task_2_action_exs[0].state)
        self.assertEqual(states.SUCCESS, wf_2_ex.state)
        self.assertEqual(2, len(wf_2_task_execs))
        self.assertEqual(states.SUCCESS, wf_2_task_1_ex.state)
        self.assertEqual(states.SUCCESS, wf_2_task_2_ex.state)
        self.assertEqual(states.SUCCESS, wf_3_ex.state)
        self.assertEqual(2, len(wf_3_task_execs))
        self.assertEqual(states.SUCCESS, wf_3_task_1_ex.state)
        self.assertEqual(states.SUCCESS, wf_3_task_2_ex.state)

    def test_pause_resume_cascade_down_to_with_items_subworkflows(self):
        workbook = """
        version: '2.0'
        name: wb
        workflows:
          wf1:
            tasks:
              task1:
                with-items: i in <% range(3) %>
                workflow: wf2
                on-success:
                  - task3
              task2:
                workflow: wf3
                on-success:
                  - task3
              task3:
                join: all
                action: std.noop
          wf2:
            tasks:
              task1:
                action: std.async_noop
                on-success:
                  - task2
              task2:
                action: std.noop
          wf3:
            tasks:
              task1:
                action: std.async_noop
                on-success:
                  - task2
              task2:
                action: std.noop
        """

        wb_service.create_workbook_v2(workbook)

        # Start workflow execution.
        wf_1_ex = self.engine.start_workflow('wb.wf1')

        self.await_workflow_state(wf_1_ex.id, states.RUNNING)

        with db_api.transaction():
            wf_execs = db_api.get_workflow_executions()

            # Get objects for the parent workflow execution.
            wf_1_ex = self._assert_single_item(wf_execs, name='wb.wf1')

            wf_1_task_execs = wf_1_ex.task_executions

            wf_1_task_1_ex = self._assert_single_item(
                wf_1_ex.task_executions,
                name='task1'
            )

            wf_1_task_1_action_exs = sorted(
                wf_1_task_1_ex.executions,
                key=lambda x: x['runtime_context']['index']
            )

            wf_1_task_2_ex = self._assert_single_item(
                wf_1_ex.task_executions,
                name='task2'
            )

            wf_1_task_2_action_exs = wf_1_task_2_ex.executions

            # Get objects for the with-items subworkflow executions.
            wf_2_ex_1 = db_api.get_workflow_execution(
                wf_1_task_1_action_exs[0].id
            )

            wf_2_ex_1_task_execs = wf_2_ex_1.task_executions

            wf_2_ex_1_task_1_ex = self._assert_single_item(
                wf_2_ex_1.task_executions,
                name='task1'
            )

            wf_2_ex_1_task_1_action_exs = db_api.get_action_executions(
                task_execution_id=wf_2_ex_1_task_1_ex.id
            )

            wf_2_ex_2 = db_api.get_workflow_execution(
                wf_1_task_1_action_exs[1].id
            )

            wf_2_ex_2_task_execs = wf_2_ex_2.task_executions

            wf_2_ex_2_task_1_ex = self._assert_single_item(
                wf_2_ex_2.task_executions,
                name='task1'
            )

            wf_2_ex_2_task_1_action_exs = db_api.get_action_executions(
                task_execution_id=wf_2_ex_2_task_1_ex.id
            )

            wf_2_ex_3 = db_api.get_workflow_execution(
                wf_1_task_1_action_exs[2].id
            )

            wf_2_ex_3_task_execs = wf_2_ex_3.task_executions

            wf_2_ex_3_task_1_ex = self._assert_single_item(
                wf_2_ex_3.task_executions,
                name='task1'
            )

            wf_2_ex_3_task_1_action_exs = db_api.get_action_executions(
                task_execution_id=wf_2_ex_3_task_1_ex.id
            )

            # Get objects for the wf3 subworkflow execution.
            wf_3_ex = self._assert_single_item(wf_execs, name='wb.wf3')

            wf_3_task_execs = wf_3_ex.task_executions

            wf_3_task_1_ex = self._assert_single_item(
                wf_3_ex.task_executions,
                name='task1'
            )

            wf_3_task_1_action_exs = db_api.get_action_executions(
                task_execution_id=wf_3_task_1_ex.id
            )

        # Check state of parent workflow execution.
        self.assertEqual(states.RUNNING, wf_1_ex.state)
        self.assertEqual(2, len(wf_1_task_execs))
        self.assertEqual(states.RUNNING, wf_1_task_1_ex.state)
        self.assertEqual(states.RUNNING, wf_1_task_2_ex.state)
        self.assertEqual(3, len(wf_1_task_1_action_exs))

        # Check state of wf2 (1) subworkflow execution.
        self.assertEqual(states.RUNNING, wf_1_task_1_action_exs[0].state)
        self.assertEqual(wf_1_task_1_action_exs[0].id, wf_2_ex_1.id)
        self.assertEqual(states.RUNNING, wf_2_ex_1.state)
        self.assertEqual(1, len(wf_2_ex_1_task_execs))
        self.assertEqual(states.RUNNING, wf_2_ex_1_task_1_ex.state)
        self.assertEqual(1, len(wf_2_ex_1_task_1_action_exs))
        self.assertEqual(states.RUNNING, wf_2_ex_1_task_1_action_exs[0].state)

        # Check state of wf2 (2) subworkflow execution.
        self.assertEqual(states.RUNNING, wf_1_task_1_action_exs[1].state)
        self.assertEqual(wf_1_task_1_action_exs[1].id, wf_2_ex_2.id)
        self.assertEqual(states.RUNNING, wf_2_ex_2.state)
        self.assertEqual(1, len(wf_2_ex_2_task_execs))
        self.assertEqual(states.RUNNING, wf_2_ex_2_task_1_ex.state)
        self.assertEqual(1, len(wf_2_ex_2_task_1_action_exs))
        self.assertEqual(states.RUNNING, wf_2_ex_2_task_1_action_exs[0].state)

        # Check state of wf2 (3) subworkflow execution.
        self.assertEqual(states.RUNNING, wf_1_task_1_action_exs[2].state)
        self.assertEqual(wf_1_task_1_action_exs[2].id, wf_2_ex_3.id)
        self.assertEqual(states.RUNNING, wf_2_ex_3.state)
        self.assertEqual(1, len(wf_2_ex_3_task_execs))
        self.assertEqual(states.RUNNING, wf_2_ex_3_task_1_ex.state)
        self.assertEqual(1, len(wf_2_ex_3_task_1_action_exs))
        self.assertEqual(states.RUNNING, wf_2_ex_3_task_1_action_exs[0].state)

        # Check state of wf3 subworkflow execution.
        self.assertEqual(1, len(wf_1_task_2_action_exs))
        self.assertEqual(states.RUNNING, wf_1_task_2_action_exs[0].state)
        self.assertEqual(wf_1_task_2_action_exs[0].id, wf_3_ex.id)
        self.assertEqual(states.RUNNING, wf_3_ex.state)
        self.assertEqual(1, len(wf_3_task_execs))
        self.assertEqual(states.RUNNING, wf_3_task_1_ex.state)
        self.assertEqual(1, len(wf_3_task_1_action_exs))
        self.assertEqual(states.RUNNING, wf_3_task_1_action_exs[0].state)

        # Pause the main workflow.
        self.engine.pause_workflow(wf_1_ex.id)
        self.await_workflow_paused(wf_2_ex_1.id)
        self.await_workflow_paused(wf_2_ex_2.id)
        self.await_workflow_paused(wf_2_ex_3.id)
        self.await_workflow_paused(wf_3_ex.id)
        self.await_task_paused(wf_1_task_1_ex.id)
        self.await_task_paused(wf_1_task_2_ex.id)
        self.await_workflow_paused(wf_1_ex.id)

        with db_api.transaction():
            wf_execs = db_api.get_workflow_executions()

            # Get objects for the parent workflow execution.
            wf_1_ex = self._assert_single_item(wf_execs, name='wb.wf1')

            wf_1_task_1_ex = self._assert_single_item(
                wf_1_ex.task_executions,
                name='task1'
            )

            wf_1_task_1_action_exs = sorted(
                wf_1_task_1_ex.executions,
                key=lambda x: x['runtime_context']['index']
            )

            wf_1_task_2_ex = self._assert_single_item(
                wf_1_ex.task_executions,
                name='task2'
            )

            wf_1_task_2_action_exs = wf_1_task_2_ex.executions

            # Get objects for the with-items subworkflow executions.
            wf_2_ex_1 = db_api.get_workflow_execution(
                wf_1_task_1_action_exs[0].id
            )

            wf_2_ex_1_task_1_ex = self._assert_single_item(
                wf_2_ex_1.task_executions,
                name='task1'
            )

            wf_2_ex_1_task_1_action_exs = db_api.get_action_executions(
                task_execution_id=wf_2_ex_1_task_1_ex.id
            )

            wf_2_ex_2 = db_api.get_workflow_execution(
                wf_1_task_1_action_exs[1].id
            )

            wf_2_ex_2_task_1_ex = self._assert_single_item(
                wf_2_ex_2.task_executions,
                name='task1'
            )

            wf_2_ex_2_task_1_action_exs = db_api.get_action_executions(
                task_execution_id=wf_2_ex_2_task_1_ex.id
            )

            wf_2_ex_3 = db_api.get_workflow_execution(
                wf_1_task_1_action_exs[2].id
            )

            wf_2_ex_3_task_1_ex = self._assert_single_item(
                wf_2_ex_3.task_executions,
                name='task1'
            )

            wf_2_ex_3_task_1_action_exs = db_api.get_action_executions(
                task_execution_id=wf_2_ex_3_task_1_ex.id
            )

            # Get objects for the wf3 subworkflow execution.
            wf_3_ex = self._assert_single_item(wf_execs, name='wb.wf3')

            wf_3_task_1_ex = self._assert_single_item(
                wf_3_ex.task_executions,
                name='task1'
            )

            wf_3_task_1_action_exs = db_api.get_action_executions(
                task_execution_id=wf_3_task_1_ex.id
            )

        # Check state of parent workflow execution.
        self.assertEqual(states.PAUSED, wf_1_ex.state)
        self.assertEqual(states.PAUSED, wf_1_task_1_ex.state)
        self.assertEqual(states.PAUSED, wf_1_task_2_ex.state)

        # Check state of wf2 (1) subworkflow execution.
        self.assertEqual(states.PAUSED, wf_1_task_1_action_exs[0].state)
        self.assertEqual(states.PAUSED, wf_2_ex_1.state)
        self.assertEqual(states.RUNNING, wf_2_ex_1_task_1_ex.state)
        self.assertEqual(states.RUNNING, wf_2_ex_1_task_1_action_exs[0].state)

        # Check state of wf2 (2) subworkflow execution.
        self.assertEqual(states.PAUSED, wf_1_task_1_action_exs[1].state)
        self.assertEqual(states.PAUSED, wf_2_ex_2.state)
        self.assertEqual(states.RUNNING, wf_2_ex_2_task_1_ex.state)
        self.assertEqual(states.RUNNING, wf_2_ex_2_task_1_action_exs[0].state)

        # Check state of wf2 (3) subworkflow execution.
        self.assertEqual(states.PAUSED, wf_1_task_1_action_exs[2].state)
        self.assertEqual(states.PAUSED, wf_2_ex_3.state)
        self.assertEqual(states.RUNNING, wf_2_ex_3_task_1_ex.state)
        self.assertEqual(states.RUNNING, wf_2_ex_3_task_1_action_exs[0].state)

        # Check state of wf3 subworkflow execution.
        self.assertEqual(states.PAUSED, wf_1_task_2_action_exs[0].state)
        self.assertEqual(states.PAUSED, wf_3_ex.state)
        self.assertEqual(states.RUNNING, wf_3_task_1_ex.state)
        self.assertEqual(states.RUNNING, wf_3_task_1_action_exs[0].state)

        # Resume the main workflow.
        self.engine.resume_workflow(wf_1_ex.id)
        self.await_workflow_running(wf_2_ex_1.id)
        self.await_workflow_running(wf_2_ex_2.id)
        self.await_workflow_running(wf_2_ex_3.id)
        self.await_workflow_running(wf_3_ex.id)
        self.await_task_running(wf_1_task_1_ex.id)
        self.await_task_running(wf_1_task_2_ex.id)
        self.await_workflow_running(wf_1_ex.id)

        with db_api.transaction():
            wf_execs = db_api.get_workflow_executions()

            # Get objects for the parent workflow execution.
            wf_1_ex = self._assert_single_item(wf_execs, name='wb.wf1')

            wf_1_task_1_ex = self._assert_single_item(
                wf_1_ex.task_executions,
                name='task1'
            )

            wf_1_task_1_action_exs = sorted(
                wf_1_task_1_ex.executions,
                key=lambda x: x['runtime_context']['index']
            )

            wf_1_task_2_ex = self._assert_single_item(
                wf_1_ex.task_executions,
                name='task2'
            )

            wf_1_task_2_action_exs = wf_1_task_2_ex.executions

            # Get objects for the with-items subworkflow executions.
            wf_2_ex_1 = db_api.get_workflow_execution(
                wf_1_task_1_action_exs[0].id
            )

            wf_2_ex_1_task_1_ex = self._assert_single_item(
                wf_2_ex_1.task_executions,
                name='task1'
            )

            wf_2_ex_1_task_1_action_exs = db_api.get_action_executions(
                task_execution_id=wf_2_ex_1_task_1_ex.id
            )

            wf_2_ex_2 = db_api.get_workflow_execution(
                wf_1_task_1_action_exs[1].id
            )

            wf_2_ex_2_task_1_ex = self._assert_single_item(
                wf_2_ex_2.task_executions,
                name='task1'
            )

            wf_2_ex_2_task_1_action_exs = db_api.get_action_executions(
                task_execution_id=wf_2_ex_2_task_1_ex.id
            )

            wf_2_ex_3 = db_api.get_workflow_execution(
                wf_1_task_1_action_exs[2].id
            )

            wf_2_ex_3_task_1_ex = self._assert_single_item(
                wf_2_ex_3.task_executions,
                name='task1'
            )

            wf_2_ex_3_task_1_action_exs = db_api.get_action_executions(
                task_execution_id=wf_2_ex_3_task_1_ex.id
            )

            # Get objects for the wf3 subworkflow execution.
            wf_3_ex = self._assert_single_item(wf_execs, name='wb.wf3')

            wf_3_task_1_ex = self._assert_single_item(
                wf_3_ex.task_executions,
                name='task1'
            )

            wf_3_task_1_action_exs = db_api.get_action_executions(
                task_execution_id=wf_3_task_1_ex.id
            )

        # Check state of parent workflow execution.
        self.assertEqual(states.RUNNING, wf_1_ex.state)
        self.assertEqual(states.RUNNING, wf_1_task_1_ex.state)
        self.assertEqual(states.RUNNING, wf_1_task_2_ex.state)

        # Check state of wf2 (1) subworkflow execution.
        self.assertEqual(states.RUNNING, wf_1_task_1_action_exs[0].state)
        self.assertEqual(states.RUNNING, wf_2_ex_1.state)
        self.assertEqual(states.RUNNING, wf_2_ex_1_task_1_ex.state)
        self.assertEqual(states.RUNNING, wf_2_ex_1_task_1_action_exs[0].state)

        # Check state of wf2 (2) subworkflow execution.
        self.assertEqual(states.RUNNING, wf_1_task_1_action_exs[1].state)
        self.assertEqual(states.RUNNING, wf_2_ex_2.state)
        self.assertEqual(states.RUNNING, wf_2_ex_2_task_1_ex.state)
        self.assertEqual(states.RUNNING, wf_2_ex_2_task_1_action_exs[0].state)

        # Check state of wf2 (3) subworkflow execution.
        self.assertEqual(states.RUNNING, wf_1_task_1_action_exs[2].state)
        self.assertEqual(states.RUNNING, wf_2_ex_3.state)
        self.assertEqual(states.RUNNING, wf_2_ex_3_task_1_ex.state)
        self.assertEqual(states.RUNNING, wf_2_ex_3_task_1_action_exs[0].state)

        # Check state of wf3 subworkflow execution.
        self.assertEqual(states.RUNNING, wf_1_task_2_action_exs[0].state)
        self.assertEqual(states.RUNNING, wf_3_ex.state)
        self.assertEqual(states.RUNNING, wf_3_task_1_ex.state)
        self.assertEqual(states.RUNNING, wf_3_task_1_action_exs[0].state)

        # Complete action execution of subworkflows.
        self.engine.on_action_complete(
            wf_2_ex_1_task_1_action_exs[0].id,
            ml_actions.Result(data={'result': 'foobar'})
        )

        self.engine.on_action_complete(
            wf_2_ex_2_task_1_action_exs[0].id,
            ml_actions.Result(data={'result': 'foobar'})
        )

        self.engine.on_action_complete(
            wf_2_ex_3_task_1_action_exs[0].id,
            ml_actions.Result(data={'result': 'foobar'})
        )

        self.engine.on_action_complete(
            wf_3_task_1_action_exs[0].id,
            ml_actions.Result(data={'result': 'foobar'})
        )

        self.await_workflow_success(wf_2_ex_1.id)
        self.await_workflow_success(wf_2_ex_2.id)
        self.await_workflow_success(wf_2_ex_3.id)
        self.await_workflow_success(wf_3_ex.id)
        self.await_task_success(wf_1_task_1_ex.id)
        self.await_task_success(wf_1_task_2_ex.id)
        self.await_workflow_success(wf_1_ex.id)

        with db_api.transaction():
            wf_execs = db_api.get_workflow_executions()

            # Get objects for the parent workflow execution.
            wf_1_ex = self._assert_single_item(wf_execs, name='wb.wf1')

            wf_1_task_1_ex = self._assert_single_item(
                wf_1_ex.task_executions,
                name='task1'
            )

            wf_1_task_1_action_exs = sorted(
                wf_1_task_1_ex.executions,
                key=lambda x: x['runtime_context']['index']
            )

            wf_1_task_2_ex = self._assert_single_item(
                wf_1_ex.task_executions,
                name='task2'
            )

            wf_1_task_2_action_exs = wf_1_task_2_ex.executions

            # Get objects for the with-items subworkflow executions.
            wf_2_ex_1 = db_api.get_workflow_execution(
                wf_1_task_1_action_exs[0].id
            )

            wf_2_ex_1_task_1_ex = self._assert_single_item(
                wf_2_ex_1.task_executions,
                name='task1'
            )

            wf_2_ex_1_task_1_action_exs = db_api.get_action_executions(
                task_execution_id=wf_2_ex_1_task_1_ex.id
            )

            wf_2_ex_2 = db_api.get_workflow_execution(
                wf_1_task_1_action_exs[1].id
            )

            wf_2_ex_2_task_1_ex = self._assert_single_item(
                wf_2_ex_2.task_executions,
                name='task1'
            )

            wf_2_ex_2_task_1_action_exs = db_api.get_action_executions(
                task_execution_id=wf_2_ex_2_task_1_ex.id
            )

            wf_2_ex_3 = db_api.get_workflow_execution(
                wf_1_task_1_action_exs[2].id
            )

            wf_2_ex_3_task_1_ex = self._assert_single_item(
                wf_2_ex_3.task_executions,
                name='task1'
            )

            wf_2_ex_3_task_1_action_exs = db_api.get_action_executions(
                task_execution_id=wf_2_ex_3_task_1_ex.id
            )

            # Get objects for the wf3 subworkflow execution.
            wf_3_ex = self._assert_single_item(wf_execs, name='wb.wf3')

            wf_3_task_1_ex = self._assert_single_item(
                wf_3_ex.task_executions,
                name='task1'
            )

            wf_3_task_1_action_exs = db_api.get_action_executions(
                task_execution_id=wf_3_task_1_ex.id
            )

        # Check state of parent workflow execution.
        self.assertEqual(states.SUCCESS, wf_1_ex.state)
        self.assertEqual(states.SUCCESS, wf_1_task_1_ex.state)
        self.assertEqual(states.SUCCESS, wf_1_task_2_ex.state)

        # Check state of wf2 (1) subworkflow execution.
        self.assertEqual(states.SUCCESS, wf_1_task_1_action_exs[0].state)
        self.assertEqual(states.SUCCESS, wf_2_ex_1.state)
        self.assertEqual(states.SUCCESS, wf_2_ex_1_task_1_ex.state)
        self.assertEqual(states.SUCCESS, wf_2_ex_1_task_1_action_exs[0].state)

        # Check state of wf2 (2) subworkflow execution.
        self.assertEqual(states.SUCCESS, wf_1_task_1_action_exs[1].state)
        self.assertEqual(states.SUCCESS, wf_2_ex_2.state)
        self.assertEqual(states.SUCCESS, wf_2_ex_2_task_1_ex.state)
        self.assertEqual(states.SUCCESS, wf_2_ex_2_task_1_action_exs[0].state)

        # Check state of wf2 (3) subworkflow execution.
        self.assertEqual(states.SUCCESS, wf_1_task_1_action_exs[2].state)
        self.assertEqual(states.SUCCESS, wf_2_ex_3.state)
        self.assertEqual(states.SUCCESS, wf_2_ex_3_task_1_ex.state)
        self.assertEqual(states.SUCCESS, wf_2_ex_3_task_1_action_exs[0].state)

        # Check state of wf3 subworkflow execution.
        self.assertEqual(states.SUCCESS, wf_1_task_2_action_exs[0].state)
        self.assertEqual(states.SUCCESS, wf_3_ex.state)
        self.assertEqual(states.SUCCESS, wf_3_task_1_ex.state)
        self.assertEqual(states.SUCCESS, wf_3_task_1_action_exs[0].state)

    def test_pause_resume_cascade_up_from_with_items_subworkflow(self):
        workbook = """
        version: '2.0'
        name: wb
        workflows:
          wf1:
            tasks:
              task1:
                with-items: i in <% range(3) %>
                workflow: wf2
                on-success:
                  - task3
              task2:
                workflow: wf3
                on-success:
                  - task3
              task3:
                join: all
                action: std.noop
          wf2:
            tasks:
              task1:
                action: std.async_noop
                on-success:
                  - task2
              task2:
                action: std.noop
          wf3:
            tasks:
              task1:
                action: std.async_noop
                on-success:
                  - task2
              task2:
                action: std.noop
        """

        wb_service.create_workbook_v2(workbook)

        # Start workflow execution.
        wf_1_ex = self.engine.start_workflow('wb.wf1')

        self.await_workflow_state(wf_1_ex.id, states.RUNNING)

        with db_api.transaction():
            wf_execs = db_api.get_workflow_executions()

            # Get objects for the parent workflow execution.
            wf_1_ex = self._assert_single_item(wf_execs, name='wb.wf1')

            wf_1_task_execs = wf_1_ex.task_executions

            wf_1_task_1_ex = self._assert_single_item(
                wf_1_ex.task_executions,
                name='task1'
            )

            wf_1_task_1_action_exs = sorted(
                wf_1_task_1_ex.executions,
                key=lambda x: x['runtime_context']['index']
            )

            wf_1_task_2_ex = self._assert_single_item(
                wf_1_ex.task_executions,
                name='task2'
            )

            wf_1_task_2_action_exs = wf_1_task_2_ex.executions

            # Get objects for the with-items subworkflow executions.
            wf_2_ex_1 = db_api.get_workflow_execution(
                wf_1_task_1_action_exs[0].id
            )

            wf_2_ex_1_task_execs = wf_2_ex_1.task_executions

            wf_2_ex_1_task_1_ex = self._assert_single_item(
                wf_2_ex_1.task_executions,
                name='task1'
            )

            wf_2_ex_1_task_1_action_exs = db_api.get_action_executions(
                task_execution_id=wf_2_ex_1_task_1_ex.id
            )

            wf_2_ex_2 = db_api.get_workflow_execution(
                wf_1_task_1_action_exs[1].id
            )

            wf_2_ex_2_task_execs = wf_2_ex_2.task_executions

            wf_2_ex_2_task_1_ex = self._assert_single_item(
                wf_2_ex_2.task_executions,
                name='task1'
            )

            wf_2_ex_2_task_1_action_exs = db_api.get_action_executions(
                task_execution_id=wf_2_ex_2_task_1_ex.id
            )

            wf_2_ex_3 = db_api.get_workflow_execution(
                wf_1_task_1_action_exs[2].id
            )

            wf_2_ex_3_task_execs = wf_2_ex_3.task_executions

            wf_2_ex_3_task_1_ex = self._assert_single_item(
                wf_2_ex_3.task_executions,
                name='task1'
            )

            wf_2_ex_3_task_1_action_exs = db_api.get_action_executions(
                task_execution_id=wf_2_ex_3_task_1_ex.id
            )

            # Get objects for the wf3 subworkflow execution.
            wf_3_ex = self._assert_single_item(wf_execs, name='wb.wf3')

            wf_3_task_execs = wf_3_ex.task_executions

            wf_3_task_1_ex = self._assert_single_item(
                wf_3_ex.task_executions,
                name='task1'
            )

            wf_3_task_1_action_exs = db_api.get_action_executions(
                task_execution_id=wf_3_task_1_ex.id
            )

        # Check state of parent workflow execution.
        self.assertEqual(states.RUNNING, wf_1_ex.state)
        self.assertEqual(2, len(wf_1_task_execs))
        self.assertEqual(states.RUNNING, wf_1_task_1_ex.state)
        self.assertEqual(states.RUNNING, wf_1_task_2_ex.state)
        self.assertEqual(3, len(wf_1_task_1_action_exs))

        # Check state of wf2 (1) subworkflow execution.
        self.assertEqual(states.RUNNING, wf_1_task_1_action_exs[0].state)
        self.assertEqual(wf_1_task_1_action_exs[0].id, wf_2_ex_1.id)
        self.assertEqual(states.RUNNING, wf_2_ex_1.state)
        self.assertEqual(1, len(wf_2_ex_1_task_execs))
        self.assertEqual(states.RUNNING, wf_2_ex_1_task_1_ex.state)
        self.assertEqual(1, len(wf_2_ex_1_task_1_action_exs))
        self.assertEqual(states.RUNNING, wf_2_ex_1_task_1_action_exs[0].state)

        # Check state of wf2 (2) subworkflow execution.
        self.assertEqual(states.RUNNING, wf_1_task_1_action_exs[1].state)
        self.assertEqual(wf_1_task_1_action_exs[1].id, wf_2_ex_2.id)
        self.assertEqual(states.RUNNING, wf_2_ex_2.state)
        self.assertEqual(1, len(wf_2_ex_2_task_execs))
        self.assertEqual(states.RUNNING, wf_2_ex_2_task_1_ex.state)
        self.assertEqual(1, len(wf_2_ex_2_task_1_action_exs))
        self.assertEqual(states.RUNNING, wf_2_ex_2_task_1_action_exs[0].state)

        # Check state of wf2 (3) subworkflow execution.
        self.assertEqual(states.RUNNING, wf_1_task_1_action_exs[2].state)
        self.assertEqual(wf_1_task_1_action_exs[2].id, wf_2_ex_3.id)
        self.assertEqual(states.RUNNING, wf_2_ex_3.state)
        self.assertEqual(1, len(wf_2_ex_3_task_execs))
        self.assertEqual(states.RUNNING, wf_2_ex_3_task_1_ex.state)
        self.assertEqual(1, len(wf_2_ex_3_task_1_action_exs))
        self.assertEqual(states.RUNNING, wf_2_ex_3_task_1_action_exs[0].state)

        # Check state of wf3 subworkflow execution.
        self.assertEqual(1, len(wf_1_task_2_action_exs))
        self.assertEqual(states.RUNNING, wf_1_task_2_action_exs[0].state)
        self.assertEqual(wf_1_task_2_action_exs[0].id, wf_3_ex.id)
        self.assertEqual(states.RUNNING, wf_3_ex.state)
        self.assertEqual(1, len(wf_3_task_execs))
        self.assertEqual(states.RUNNING, wf_3_task_1_ex.state)
        self.assertEqual(1, len(wf_3_task_1_action_exs))
        self.assertEqual(states.RUNNING, wf_3_task_1_action_exs[0].state)

        # Pause one of the subworkflows in the with-items task.
        self.engine.pause_workflow(wf_2_ex_1.id)

        self.await_workflow_paused(wf_2_ex_1.id)
        self.await_workflow_paused(wf_2_ex_2.id)
        self.await_workflow_paused(wf_2_ex_3.id)
        self.await_workflow_paused(wf_3_ex.id)
        self.await_task_paused(wf_1_task_1_ex.id)
        self.await_task_paused(wf_1_task_2_ex.id)
        self.await_workflow_paused(wf_1_ex.id)

        with db_api.transaction():
            wf_execs = db_api.get_workflow_executions()

            # Get objects for the parent workflow execution.
            wf_1_ex = self._assert_single_item(wf_execs, name='wb.wf1')

            wf_1_task_1_ex = self._assert_single_item(
                wf_1_ex.task_executions,
                name='task1'
            )

            wf_1_task_1_action_exs = sorted(
                wf_1_task_1_ex.executions,
                key=lambda x: x['runtime_context']['index']
            )

            wf_1_task_2_ex = self._assert_single_item(
                wf_1_ex.task_executions,
                name='task2'
            )

            wf_1_task_2_action_exs = wf_1_task_2_ex.executions

            # Get objects for the with-items subworkflow executions.
            wf_2_ex_1 = db_api.get_workflow_execution(
                wf_1_task_1_action_exs[0].id
            )

            wf_2_ex_1_task_1_ex = self._assert_single_item(
                wf_2_ex_1.task_executions,
                name='task1'
            )

            wf_2_ex_1_task_1_action_exs = db_api.get_action_executions(
                task_execution_id=wf_2_ex_1_task_1_ex.id
            )

            wf_2_ex_2 = db_api.get_workflow_execution(
                wf_1_task_1_action_exs[1].id
            )

            wf_2_ex_2_task_1_ex = self._assert_single_item(
                wf_2_ex_2.task_executions,
                name='task1'
            )

            wf_2_ex_2_task_1_action_exs = db_api.get_action_executions(
                task_execution_id=wf_2_ex_2_task_1_ex.id
            )

            wf_2_ex_3 = db_api.get_workflow_execution(
                wf_1_task_1_action_exs[2].id
            )

            wf_2_ex_3_task_1_ex = self._assert_single_item(
                wf_2_ex_3.task_executions,
                name='task1'
            )

            wf_2_ex_3_task_1_action_exs = db_api.get_action_executions(
                task_execution_id=wf_2_ex_3_task_1_ex.id
            )

            # Get objects for the wf3 subworkflow execution.
            wf_3_ex = self._assert_single_item(wf_execs, name='wb.wf3')

            wf_3_task_1_ex = self._assert_single_item(
                wf_3_ex.task_executions,
                name='task1'
            )

            wf_3_task_1_action_exs = db_api.get_action_executions(
                task_execution_id=wf_3_task_1_ex.id
            )

        # Check state of parent workflow execution.
        self.assertEqual(states.PAUSED, wf_1_ex.state)
        self.assertEqual(states.PAUSED, wf_1_task_1_ex.state)
        self.assertEqual(states.PAUSED, wf_1_task_2_ex.state)

        # Check state of wf2 (1) subworkflow execution.
        self.assertEqual(states.PAUSED, wf_1_task_1_action_exs[0].state)
        self.assertEqual(states.PAUSED, wf_2_ex_1.state)
        self.assertEqual(states.RUNNING, wf_2_ex_1_task_1_ex.state)
        self.assertEqual(states.RUNNING, wf_2_ex_1_task_1_action_exs[0].state)

        # Check state of wf2 (2) subworkflow execution.
        self.assertEqual(states.PAUSED, wf_1_task_1_action_exs[1].state)
        self.assertEqual(states.PAUSED, wf_2_ex_2.state)
        self.assertEqual(states.RUNNING, wf_2_ex_2_task_1_ex.state)
        self.assertEqual(states.RUNNING, wf_2_ex_2_task_1_action_exs[0].state)

        # Check state of wf2 (3) subworkflow execution.
        self.assertEqual(states.PAUSED, wf_1_task_1_action_exs[2].state)
        self.assertEqual(states.PAUSED, wf_2_ex_3.state)
        self.assertEqual(states.RUNNING, wf_2_ex_3_task_1_ex.state)
        self.assertEqual(states.RUNNING, wf_2_ex_3_task_1_action_exs[0].state)

        # Check state of wf3 subworkflow execution.
        self.assertEqual(states.PAUSED, wf_1_task_2_action_exs[0].state)
        self.assertEqual(states.PAUSED, wf_3_ex.state)
        self.assertEqual(states.RUNNING, wf_3_task_1_ex.state)
        self.assertEqual(states.RUNNING, wf_3_task_1_action_exs[0].state)

        # NOTE(rakhmerov): Since cascade pausing is not atomic we need
        # to make sure that all internal operations related to pausing
        # one of workflow executions 'wb.wf2' are completed. So we have
        # to look if any "_on_action_update" calls are scheduled.

        def _predicate():
            return all(
                [
                    '_on_action_update' not in c.target_method_name
                    for c in db_api.get_delayed_calls()
                ]
            )

        self._await(_predicate)

        # Resume one of the subworkflows in the with-items task.
        self.engine.resume_workflow(wf_2_ex_1.id)

        self.await_workflow_running(wf_2_ex_1.id)
        self.await_workflow_paused(wf_2_ex_2.id)
        self.await_workflow_paused(wf_2_ex_3.id)
        self.await_workflow_paused(wf_3_ex.id)
        self.await_task_paused(wf_1_task_1_ex.id)
        self.await_task_paused(wf_1_task_2_ex.id)
        self.await_workflow_paused(wf_1_ex.id)

        # Complete action execution of the subworkflow that is resumed.
        self.engine.on_action_complete(
            wf_2_ex_1_task_1_action_exs[0].id,
            ml_actions.Result(data={'result': 'foobar'})
        )

        self.await_workflow_success(wf_2_ex_1.id)
        self.await_workflow_paused(wf_2_ex_2.id)
        self.await_workflow_paused(wf_2_ex_3.id)
        self.await_workflow_paused(wf_3_ex.id)
        self.await_task_paused(wf_1_task_1_ex.id)
        self.await_task_paused(wf_1_task_2_ex.id)
        self.await_workflow_paused(wf_1_ex.id)

        with db_api.transaction():
            wf_execs = db_api.get_workflow_executions()

            # Get objects for the parent workflow execution.
            wf_1_ex = self._assert_single_item(wf_execs, name='wb.wf1')

            wf_1_task_1_ex = self._assert_single_item(
                wf_1_ex.task_executions,
                name='task1'
            )

            wf_1_task_1_action_exs = sorted(
                wf_1_task_1_ex.executions,
                key=lambda x: x['runtime_context']['index']
            )

            wf_1_task_2_ex = self._assert_single_item(
                wf_1_ex.task_executions,
                name='task2'
            )

            wf_1_task_2_action_exs = wf_1_task_2_ex.executions

            # Get objects for the with-items subworkflow executions.
            wf_2_ex_1 = db_api.get_workflow_execution(
                wf_1_task_1_action_exs[0].id
            )

            wf_2_ex_1_task_1_ex = self._assert_single_item(
                wf_2_ex_1.task_executions,
                name='task1'
            )

            wf_2_ex_1_task_1_action_exs = db_api.get_action_executions(
                task_execution_id=wf_2_ex_1_task_1_ex.id
            )

            wf_2_ex_2 = db_api.get_workflow_execution(
                wf_1_task_1_action_exs[1].id
            )

            wf_2_ex_2_task_1_ex = self._assert_single_item(
                wf_2_ex_2.task_executions,
                name='task1'
            )

            wf_2_ex_2_task_1_action_exs = db_api.get_action_executions(
                task_execution_id=wf_2_ex_2_task_1_ex.id
            )

            wf_2_ex_3 = db_api.get_workflow_execution(
                wf_1_task_1_action_exs[2].id
            )

            wf_2_ex_3_task_execs = wf_2_ex_3.task_executions

            wf_2_ex_3_task_1_ex = self._assert_single_item(
                wf_2_ex_3.task_executions,
                name='task1'
            )

            wf_2_ex_3_task_1_action_exs = db_api.get_action_executions(
                task_execution_id=wf_2_ex_3_task_1_ex.id
            )

            # Get objects for the wf3 subworkflow execution.
            wf_3_ex = self._assert_single_item(wf_execs, name='wb.wf3')

            wf_3_task_execs = wf_3_ex.task_executions

            wf_3_task_1_ex = self._assert_single_item(
                wf_3_ex.task_executions,
                name='task1'
            )

            wf_3_task_1_action_exs = db_api.get_action_executions(
                task_execution_id=wf_3_task_1_ex.id
            )

        # Check state of parent workflow execution.
        self.assertEqual(states.PAUSED, wf_1_ex.state)
        self.assertEqual(states.PAUSED, wf_1_task_1_ex.state)
        self.assertEqual(states.PAUSED, wf_1_task_2_ex.state)

        # Check state of wf2 (1) subworkflow execution.
        self.assertEqual(states.SUCCESS, wf_1_task_1_action_exs[0].state)
        self.assertEqual(states.SUCCESS, wf_2_ex_1.state)
        self.assertEqual(states.SUCCESS, wf_2_ex_1_task_1_ex.state)
        self.assertEqual(states.SUCCESS, wf_2_ex_1_task_1_action_exs[0].state)

        # Check state of wf2 (2) subworkflow execution.
        self.assertEqual(states.PAUSED, wf_1_task_1_action_exs[1].state)
        self.assertEqual(states.PAUSED, wf_2_ex_2.state)
        self.assertEqual(states.RUNNING, wf_2_ex_2_task_1_ex.state)
        self.assertEqual(states.RUNNING, wf_2_ex_2_task_1_action_exs[0].state)

        # Check state of wf2 (3) subworkflow execution.
        self.assertEqual(states.PAUSED, wf_1_task_1_action_exs[2].state)
        self.assertEqual(states.PAUSED, wf_2_ex_3.state)
        self.assertEqual(states.RUNNING, wf_2_ex_3_task_1_ex.state)
        self.assertEqual(states.RUNNING, wf_2_ex_3_task_1_action_exs[0].state)

        # Check state of wf3 subworkflow execution.
        self.assertEqual(states.PAUSED, wf_1_task_2_action_exs[0].state)
        self.assertEqual(states.PAUSED, wf_3_ex.state)
        self.assertEqual(states.RUNNING, wf_3_task_1_ex.state)
        self.assertEqual(states.RUNNING, wf_3_task_1_action_exs[0].state)

        # Resume one of the remaining subworkflows.
        self.engine.resume_workflow(wf_2_ex_2.id)
        self.engine.resume_workflow(wf_2_ex_3.id)
        self.engine.resume_workflow(wf_3_ex.id)
        self.await_workflow_running(wf_2_ex_2.id)
        self.await_workflow_running(wf_2_ex_3.id)
        self.await_workflow_running(wf_3_ex.id)
        self.await_task_running(wf_1_task_1_ex.id)
        self.await_task_running(wf_1_task_2_ex.id)
        self.await_workflow_running(wf_1_ex.id)

        # Complete action executions of the remaining subworkflows.
        self.engine.on_action_complete(
            wf_2_ex_2_task_1_action_exs[0].id,
            ml_actions.Result(data={'result': 'foobar'})
        )

        self.engine.on_action_complete(
            wf_2_ex_3_task_1_action_exs[0].id,
            ml_actions.Result(data={'result': 'foobar'})
        )

        self.engine.on_action_complete(
            wf_3_task_1_action_exs[0].id,
            ml_actions.Result(data={'result': 'foobar'})
        )

        self.await_workflow_success(wf_2_ex_1.id)
        self.await_workflow_success(wf_2_ex_2.id)
        self.await_workflow_success(wf_2_ex_3.id)
        self.await_workflow_success(wf_3_ex.id)
        self.await_task_success(wf_1_task_1_ex.id)
        self.await_task_success(wf_1_task_2_ex.id)
        self.await_workflow_success(wf_1_ex.id)

        with db_api.transaction():
            wf_execs = db_api.get_workflow_executions()

            # Get objects for the parent workflow execution.
            wf_1_ex = self._assert_single_item(wf_execs, name='wb.wf1')

            wf_1_task_execs = wf_1_ex.task_executions

            wf_1_task_1_ex = self._assert_single_item(
                wf_1_ex.task_executions,
                name='task1'
            )

            wf_1_task_1_action_exs = sorted(
                wf_1_task_1_ex.executions,
                key=lambda x: x['runtime_context']['index']
            )

            wf_1_task_2_ex = self._assert_single_item(
                wf_1_ex.task_executions,
                name='task2'
            )

            wf_1_task_2_action_exs = wf_1_task_2_ex.executions

            # Get objects for the with-items subworkflow executions.
            wf_2_ex_1 = db_api.get_workflow_execution(
                wf_1_task_1_action_exs[0].id
            )

            wf_2_ex_1_task_execs = wf_2_ex_1.task_executions

            wf_2_ex_1_task_1_ex = self._assert_single_item(
                wf_2_ex_1.task_executions,
                name='task1'
            )

            wf_2_ex_1_task_1_action_exs = db_api.get_action_executions(
                task_execution_id=wf_2_ex_1_task_1_ex.id
            )

            wf_2_ex_2 = db_api.get_workflow_execution(
                wf_1_task_1_action_exs[1].id
            )

            wf_2_ex_2_task_execs = wf_2_ex_2.task_executions

            wf_2_ex_2_task_1_ex = self._assert_single_item(
                wf_2_ex_2.task_executions,
                name='task1'
            )

            wf_2_ex_2_task_1_action_exs = db_api.get_action_executions(
                task_execution_id=wf_2_ex_2_task_1_ex.id
            )

            wf_2_ex_3 = db_api.get_workflow_execution(
                wf_1_task_1_action_exs[2].id
            )

            wf_2_ex_3_task_execs = wf_2_ex_3.task_executions

            wf_2_ex_3_task_1_ex = self._assert_single_item(
                wf_2_ex_3.task_executions,
                name='task1'
            )

            wf_2_ex_3_task_1_action_exs = db_api.get_action_executions(
                task_execution_id=wf_2_ex_3_task_1_ex.id
            )

            # Get objects for the wf3 subworkflow execution.
            wf_3_ex = self._assert_single_item(wf_execs, name='wb.wf3')

            wf_3_task_execs = wf_3_ex.task_executions

            wf_3_task_1_ex = self._assert_single_item(
                wf_3_ex.task_executions,
                name='task1'
            )

            wf_3_task_1_action_exs = db_api.get_action_executions(
                task_execution_id=wf_3_task_1_ex.id
            )

        # Check state of parent workflow execution.
        self.assertEqual(states.SUCCESS, wf_1_ex.state)
        self.assertEqual(states.SUCCESS, wf_1_task_1_ex.state)
        self.assertEqual(states.SUCCESS, wf_1_task_2_ex.state)

        # Check state of wf2 (1) subworkflow execution.
        self.assertEqual(states.SUCCESS, wf_1_task_1_action_exs[0].state)
        self.assertEqual(states.SUCCESS, wf_2_ex_1.state)
        self.assertEqual(states.SUCCESS, wf_2_ex_1_task_1_ex.state)
        self.assertEqual(states.SUCCESS, wf_2_ex_1_task_1_action_exs[0].state)

        # Check state of wf2 (2) subworkflow execution.
        self.assertEqual(states.SUCCESS, wf_1_task_1_action_exs[1].state)
        self.assertEqual(states.SUCCESS, wf_2_ex_2.state)
        self.assertEqual(states.SUCCESS, wf_2_ex_2_task_1_ex.state)
        self.assertEqual(states.SUCCESS, wf_2_ex_2_task_1_action_exs[0].state)

        # Check state of wf2 (3) subworkflow execution.
        self.assertEqual(states.SUCCESS, wf_1_task_1_action_exs[2].state)
        self.assertEqual(states.SUCCESS, wf_2_ex_3.state)
        self.assertEqual(states.SUCCESS, wf_2_ex_3_task_1_ex.state)
        self.assertEqual(states.SUCCESS, wf_2_ex_3_task_1_action_exs[0].state)

        # Check state of wf3 subworkflow execution.
        self.assertEqual(states.SUCCESS, wf_1_task_2_action_exs[0].state)
        self.assertEqual(states.SUCCESS, wf_3_ex.state)
        self.assertEqual(states.SUCCESS, wf_3_task_1_ex.state)
        self.assertEqual(states.SUCCESS, wf_3_task_1_action_exs[0].state)

    def test_pause_resume_cascade_up_from_subworkflow_pause_before(self):
        workbook = """
        version: '2.0'
        name: wb
        workflows:
            wf1:
                tasks:
                    task1:
                        workflow: wf2
                        on-success:
                            - task3
                    task2:
                        workflow: wf3
                        on-success:
                            - task3
                    task3:
                        join: all
                        action: std.noop
            wf2:
                tasks:
                    task1:
                        action: std.noop
                        on-success:
                            - task2
                    task2:
                        pause-before: true
                        action: std.async_noop
            wf3:
                tasks:
                    task1:
                        action: std.async_noop
                        on-success:
                            - task2
                    task2:
                        action: std.noop
        """

        wb_service.create_workbook_v2(workbook)

        # Start workflow execution.
        wf_1_ex = self.engine.start_workflow('wb.wf1')

        self.await_workflow_state(wf_1_ex.id, states.PAUSED)

        with db_api.transaction():
            wf_execs = db_api.get_workflow_executions()

            # Get objects for the parent workflow execution.
            wf_1_ex = self._assert_single_item(wf_execs, name='wb.wf1')

            wf_1_task_execs = wf_1_ex.task_executions

            wf_1_task_1_ex = self._assert_single_item(
                wf_1_ex.task_executions,
                name='task1'
            )

            wf_1_task_1_action_exs = wf_1_task_1_ex.executions

            wf_1_task_2_ex = self._assert_single_item(
                wf_1_ex.task_executions,
                name='task2'
            )

            wf_1_task_2_action_exs = wf_1_task_2_ex.executions

            # Get objects for the subworkflow executions.
            wf_2_ex = self._assert_single_item(wf_execs, name='wb.wf2')

            wf_2_task_execs = wf_2_ex.task_executions

            wf_2_task_1_ex = self._assert_single_item(
                wf_2_ex.task_executions,
                name='task1'
            )

            wf_2_task_1_action_exs = db_api.get_action_executions(
                task_execution_id=wf_2_task_1_ex.id
            )

            wf_2_task_2_ex = self._assert_single_item(
                wf_2_ex.task_executions,
                name='task2'
            )

            wf_2_task_2_action_exs = db_api.get_action_executions(
                task_execution_id=wf_2_task_2_ex.id
            )

            wf_3_ex = self._assert_single_item(wf_execs, name='wb.wf3')

            wf_3_task_execs = wf_3_ex.task_executions

            wf_3_task_1_ex = self._assert_single_item(
                wf_3_ex.task_executions,
                name='task1'
            )

            wf_3_task_1_action_exs = db_api.get_action_executions(
                task_execution_id=wf_3_task_1_ex.id
            )

        self.assertEqual(states.PAUSED, wf_2_ex.state)
        self.assertEqual(states.SUCCESS, wf_2_task_1_ex.state)
        self.assertEqual(states.SUCCESS, wf_2_task_1_action_exs[0].state)
        self.assertEqual(states.IDLE, wf_2_task_2_ex.state)
        self.assertEqual(0, len(wf_2_task_2_action_exs))
        self.assertEqual(states.PAUSED, wf_3_ex.state)
        self.assertEqual(states.RUNNING, wf_3_task_1_ex.state)
        self.assertEqual(states.RUNNING, wf_3_task_1_action_exs[0].state)
        self.assertEqual(states.PAUSED, wf_1_task_1_action_exs[0].state)
        self.assertEqual(states.PAUSED, wf_1_task_1_ex.state)
        self.assertEqual(states.PAUSED, wf_1_task_2_action_exs[0].state)
        self.assertEqual(states.PAUSED, wf_1_task_2_ex.state)
        self.assertEqual(states.PAUSED, wf_1_ex.state)

        # Resume the main workflow.
        self.engine.resume_workflow(wf_1_ex.id)

        self.await_workflow_running(wf_1_ex.id)
        self.await_workflow_running(wf_2_ex.id)
        self.await_workflow_running(wf_3_ex.id)

        with db_api.transaction():
            wf_execs = db_api.get_workflow_executions()

            # Get objects for the parent workflow execution.
            wf_1_ex = self._assert_single_item(wf_execs, name='wb.wf1')

            wf_1_task_execs = wf_1_ex.task_executions

            wf_1_task_1_ex = self._assert_single_item(
                wf_1_ex.task_executions,
                name='task1'
            )

            wf_1_task_1_action_exs = wf_1_task_1_ex.executions

            wf_1_task_2_ex = self._assert_single_item(
                wf_1_ex.task_executions,
                name='task2'
            )

            wf_1_task_2_action_exs = wf_1_task_2_ex.executions

            # Get objects for the subworkflow executions.
            wf_2_ex = self._assert_single_item(wf_execs, name='wb.wf2')

            wf_2_task_execs = wf_2_ex.task_executions

            wf_2_task_1_ex = self._assert_single_item(
                wf_2_ex.task_executions,
                name='task1'
            )

            wf_2_task_1_action_exs = db_api.get_action_executions(
                task_execution_id=wf_2_task_1_ex.id
            )

            wf_2_task_2_ex = self._assert_single_item(
                wf_2_ex.task_executions,
                name='task2'
            )

            wf_2_task_2_action_exs = db_api.get_action_executions(
                task_execution_id=wf_2_task_2_ex.id
            )

            wf_3_ex = self._assert_single_item(wf_execs, name='wb.wf3')

            wf_3_task_execs = wf_3_ex.task_executions

            wf_3_task_1_ex = self._assert_single_item(
                wf_3_ex.task_executions,
                name='task1'
            )

            wf_3_task_1_action_exs = db_api.get_action_executions(
                task_execution_id=wf_3_task_1_ex.id
            )

        self.assertEqual(states.RUNNING, wf_2_ex.state)
        self.assertEqual(states.SUCCESS, wf_2_task_1_ex.state)
        self.assertEqual(states.SUCCESS, wf_2_task_1_action_exs[0].state)
        self.assertEqual(states.RUNNING, wf_2_task_2_ex.state)
        self.assertEqual(states.RUNNING, wf_2_task_2_action_exs[0].state)
        self.assertEqual(states.RUNNING, wf_3_ex.state)
        self.assertEqual(states.RUNNING, wf_3_task_1_ex.state)
        self.assertEqual(states.RUNNING, wf_3_task_1_action_exs[0].state)
        self.assertEqual(states.RUNNING, wf_1_task_1_action_exs[0].state)
        self.assertEqual(states.RUNNING, wf_1_task_1_ex.state)
        self.assertEqual(states.RUNNING, wf_1_task_2_action_exs[0].state)
        self.assertEqual(states.RUNNING, wf_1_task_2_ex.state)
        self.assertEqual(states.RUNNING, wf_1_ex.state)

        # Complete action executions of the subworkflows.
        self.engine.on_action_complete(
            wf_2_task_2_action_exs[0].id,
            ml_actions.Result(data={'result': 'foobar'})
        )

        self.engine.on_action_complete(
            wf_3_task_1_action_exs[0].id,
            ml_actions.Result(data={'result': 'foobar'})
        )

        self.await_workflow_success(wf_2_ex.id)
        self.await_workflow_success(wf_3_ex.id)
        self.await_workflow_success(wf_1_ex.id)

        with db_api.transaction():
            wf_execs = db_api.get_workflow_executions()

            # Get objects for the parent workflow execution.
            wf_1_ex = self._assert_single_item(wf_execs, name='wb.wf1')

            wf_1_task_execs = wf_1_ex.task_executions

            wf_1_task_1_ex = self._assert_single_item(
                wf_1_ex.task_executions,
                name='task1'
            )

            wf_1_task_1_action_exs = wf_1_task_1_ex.executions

            wf_1_task_2_ex = self._assert_single_item(
                wf_1_ex.task_executions,
                name='task2'
            )

            wf_1_task_2_action_exs = wf_1_task_2_ex.executions

            wf_1_task_3_ex = self._assert_single_item(
                wf_1_ex.task_executions,
                name='task3'
            )

            # Get objects for the subworkflow executions.
            wf_2_ex = self._assert_single_item(wf_execs, name='wb.wf2')

            wf_2_task_execs = wf_2_ex.task_executions

            wf_2_task_1_ex = self._assert_single_item(
                wf_2_ex.task_executions,
                name='task1'
            )

            wf_2_task_1_action_exs = db_api.get_action_executions(
                task_execution_id=wf_2_task_1_ex.id
            )

            wf_2_task_2_ex = self._assert_single_item(
                wf_2_ex.task_executions,
                name='task2'
            )

            wf_2_task_2_action_exs = db_api.get_action_executions(
                task_execution_id=wf_2_task_2_ex.id
            )

            wf_3_ex = self._assert_single_item(wf_execs, name='wb.wf3')

            wf_3_task_execs = wf_3_ex.task_executions

            wf_3_task_1_ex = self._assert_single_item(
                wf_3_ex.task_executions,
                name='task1'
            )

            wf_3_task_1_action_exs = db_api.get_action_executions(
                task_execution_id=wf_3_task_1_ex.id
            )

            wf_3_task_2_ex = self._assert_single_item(
                wf_3_ex.task_executions,
                name='task2'
            )

            wf_3_task_2_action_exs = db_api.get_action_executions(
                task_execution_id=wf_3_task_2_ex.id
            )

        self.assertEqual(states.SUCCESS, wf_1_ex.state)
        self.assertEqual(3, len(wf_1_task_execs))
        self.assertEqual(states.SUCCESS, wf_1_task_1_ex.state)
        self.assertEqual(states.SUCCESS, wf_1_task_2_ex.state)
        self.assertEqual(states.SUCCESS, wf_1_task_3_ex.state)
        self.assertEqual(states.SUCCESS, wf_1_task_1_action_exs[0].state)
        self.assertEqual(states.SUCCESS, wf_1_task_2_action_exs[0].state)
        self.assertEqual(states.SUCCESS, wf_2_ex.state)
        self.assertEqual(2, len(wf_2_task_execs))
        self.assertEqual(states.SUCCESS, wf_2_task_1_ex.state)
        self.assertEqual(states.SUCCESS, wf_2_task_2_ex.state)
        self.assertEqual(states.SUCCESS, wf_2_task_1_action_exs[0].state)
        self.assertEqual(states.SUCCESS, wf_2_task_2_action_exs[0].state)
        self.assertEqual(states.SUCCESS, wf_3_ex.state)
        self.assertEqual(2, len(wf_3_task_execs))
        self.assertEqual(states.SUCCESS, wf_3_task_1_ex.state)
        self.assertEqual(states.SUCCESS, wf_3_task_2_ex.state)
        self.assertEqual(states.SUCCESS, wf_3_task_1_action_exs[0].state)
        self.assertEqual(states.SUCCESS, wf_3_task_2_action_exs[0].state)
