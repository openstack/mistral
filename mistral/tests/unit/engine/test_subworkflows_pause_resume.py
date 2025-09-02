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
    def test_cascade_down(self):
        # The purpose of this test is to check whether pausing a main wf will
        # also pause subworkflows
        wb_text = """
        version: '2.0'

        name: wb

        workflows:
          wf1:
            tasks:
              task1:
                workflow: wf2
                on-success: task3

              task2:
                workflow: wf3
                on-success: task3

              task3:
                join: all

          wf2:
            tasks:
              task1:
                action: std.noop
                on-success: task2

              task2:
                action: std.async_noop

          wf3:
            tasks:
              task1:
                action: std.async_noop
                on-success: task2

              task2:
                action: std.noop
        """

        wb_service.create_workbook_v2(wb_text)

        # Start wf1
        wf1_ex = self.engine.start_workflow('wb.wf1')
        self.await_workflow_state(wf1_ex.id, states.RUNNING)

        with db_api.transaction():
            # Grab latest info
            wf_execs = db_api.get_workflow_executions()
            wf1_ex = self._assert_single_item(wf_execs, name='wb.wf1')
            # Grab tasks
            wf1_task1 = self._assert_single_item(
                wf1_ex.task_executions,
                name='task1'
            )
            wf1_task2 = self._assert_single_item(
                wf1_ex.task_executions,
                name='task2'
            )

        # Wait for tasks to be running
        # We know that it will be running for a long time, because the wf
        # use async_noop and should be running until we decide to send an
        # action complete event
        self.await_task_running(wf1_task1.id)
        self.await_task_running(wf1_task2.id)

        with db_api.transaction():
            # Grab latest info
            wf_execs = db_api.get_workflow_executions()

            # Get subworkflows
            wf2_ex = self._assert_single_item(wf_execs, name='wb.wf2')
            wf3_ex = self._assert_single_item(wf_execs, name='wb.wf3')

            # Grab wf2 first task (we cant yet be sure the second is executed)
            # The first task is noop
            wf2_task1 = self._assert_single_item(
                wf2_ex.task_executions,
                name='task1'
            )

            # wf3 task1 is async_noop
            wf3_task1 = self._assert_single_item(
                wf3_ex.task_executions,
                name='task1'
            )

        # Make sure wf2 and wf3 are running
        self.await_workflow_state(wf2_ex.id, states.RUNNING)
        self.await_workflow_state(wf3_ex.id, states.RUNNING)

        # Make sure wf3 task1 is running
        self.await_task_running(wf3_task1.id)

        # Wait for the wf2_task1 (noop) to be finished
        self.await_task_success(wf2_task1.id)

        with db_api.transaction():
            # Grab latest info
            wf_execs = db_api.get_workflow_executions()

            # Get subworkflows
            wf2_ex = self._assert_single_item(wf_execs, name='wb.wf2')

            # We should be able now to grab the second task of wf2
            wf2_task2 = self._assert_single_item(
                wf2_ex.task_executions,
                name='task2'
            )

            # Grab action so we can complete it after
            wf3_task1_action = db_api.get_action_executions(
                task_execution_id=wf3_task1.id
            )

        # Make sure wf2 task2 is running
        self.await_task_running(wf2_task2.id)

        with db_api.transaction():
            # Grab action so we can complete it after
            wf2_task2_action = db_api.get_action_executions(
                task_execution_id=wf2_task2.id
            )

        # Pause the main workflow
        self.engine.pause_workflow(wf1_ex.id)

        # We should have all wf paused now (aka cascade down)
        self.await_workflow_paused(wf1_ex.id)
        self.await_workflow_paused(wf2_ex.id)
        self.await_workflow_paused(wf3_ex.id)

        # Async and success tasks stay the same
        # Task that were creating subwf inherit the wf state (paused here)
        self.await_task_paused(wf1_task1.id)
        self.await_task_paused(wf1_task2.id)
        self.await_task_success(wf2_task1.id)
        self.await_task_running(wf2_task2.id)
        self.await_task_running(wf3_task1.id)

        # Resume the main workflow.
        # This will resume all workflows
        self.engine.resume_workflow(wf1_ex.id)
        self.await_workflow_running(wf1_ex.id)
        self.await_workflow_running(wf2_ex.id)
        self.await_workflow_running(wf3_ex.id)

        # Complete action executions of the subworkflows.
        self.engine.on_action_complete(
            wf2_task2_action[0].id,
            ml_actions.Result(data={'result': 'foobar'})
        )

        self.engine.on_action_complete(
            wf3_task1_action[0].id,
            ml_actions.Result(data={'result': 'foobar'})
        )

        self.await_workflow_success(wf2_ex.id)
        self.await_workflow_success(wf3_ex.id)
        self.await_workflow_success(wf1_ex.id)

    def test_cascade_up(self):
        # The purpose of this test is to check whether pausing a subwf will
        # also pause the main wf
        wb_text = """
        version: '2.0'

        name: wb

        workflows:
          wf1:
            tasks:
              task1:
                workflow: wf2
                on-success: task3

              task2:
                workflow: wf3
                on-success: task3

              task3:
                join: all

          wf2:
            tasks:
              task1:
                action: std.noop
                on-success: task2

              task2:
                action: std.async_noop

          wf3:
            tasks:
              task1:
                action: std.async_noop
                on-success: task2

              task2:
                action: std.noop
        """

        wb_service.create_workbook_v2(wb_text)

        # Start wf1
        wf1_ex = self.engine.start_workflow('wb.wf1')
        self.await_workflow_state(wf1_ex.id, states.RUNNING)

        with db_api.transaction():
            # Grab latest info
            wf_execs = db_api.get_workflow_executions()
            wf1_ex = self._assert_single_item(wf_execs, name='wb.wf1')
            # Grab tasks
            wf1_task1 = self._assert_single_item(
                wf1_ex.task_executions,
                name='task1'
            )
            wf1_task2 = self._assert_single_item(
                wf1_ex.task_executions,
                name='task2'
            )

        # Wait for tasks to be running
        # We know that it will be running for a long time, because the wf
        # use async_noop and should be running until we decide to send an
        # action complete event
        self.await_task_running(wf1_task1.id)
        self.await_task_running(wf1_task2.id)

        with db_api.transaction():
            # Grab latest info
            wf_execs = db_api.get_workflow_executions()

            # Get subworkflows
            wf2_ex = self._assert_single_item(wf_execs, name='wb.wf2')
            wf3_ex = self._assert_single_item(wf_execs, name='wb.wf3')

            # Grab wf2 first task (we cant yet be sure the second is executed)
            # The first task is noop
            wf2_task1 = self._assert_single_item(
                wf2_ex.task_executions,
                name='task1'
            )

            # wf3 task1 is async_noop
            wf3_task1 = self._assert_single_item(
                wf3_ex.task_executions,
                name='task1'
            )

        # Make sure wf2 and wf3 are running
        self.await_workflow_state(wf2_ex.id, states.RUNNING)
        self.await_workflow_state(wf3_ex.id, states.RUNNING)

        # Make sure wf3 task1 is running
        self.await_task_running(wf3_task1.id)

        # Wait for the wf2_task1 (noop) to be finished
        self.await_task_success(wf2_task1.id)

        with db_api.transaction():
            # Grab latest info
            wf_execs = db_api.get_workflow_executions()

            # Get subworkflows
            wf2_ex = self._assert_single_item(wf_execs, name='wb.wf2')

            # We should be able now to grab the second task of wf2
            wf2_task2 = self._assert_single_item(
                wf2_ex.task_executions,
                name='task2'
            )

            # Grab action so we can complete it after
            wf3_task1_action = db_api.get_action_executions(
                task_execution_id=wf3_task1.id
            )

        # Make sure wf2 task2 is running
        self.await_task_running(wf2_task2.id)

        with db_api.transaction():
            # Grab action so we can complete it after
            wf2_task2_action = db_api.get_action_executions(
                task_execution_id=wf2_task2.id
            )

        # Pause the wf2 workflow
        self.engine.pause_workflow(wf2_ex.id)

        # We should have all wf paused now (aka cascade up)
        self.await_workflow_paused(wf1_ex.id)
        self.await_workflow_paused(wf2_ex.id)
        self.await_workflow_paused(wf3_ex.id)

        # Async and success tasks stay the same
        # Task that were creating subwf inherit the wf state (paused here)
        self.await_task_paused(wf1_task1.id)
        self.await_task_paused(wf1_task2.id)
        self.await_task_success(wf2_task1.id)
        self.await_task_running(wf2_task2.id)
        self.await_task_running(wf3_task1.id)

        # Resume and complete wf2
        self.engine.resume_workflow(wf2_ex.id)
        self.await_workflow_running(wf2_ex.id)
        self.engine.on_action_complete(
            wf2_task2_action[0].id,
            ml_actions.Result(data={'result': 'foobar'})
        )

        # This is not resuming wf1 and wf3
        self.await_workflow_paused(wf1_ex.id)
        self.await_workflow_paused(wf3_ex.id)

        # Resume and complete wf3
        self.engine.resume_workflow(wf3_ex.id)
        self.await_workflow_running(wf3_ex.id)
        self.engine.on_action_complete(
            wf3_task1_action[0].id,
            ml_actions.Result(data={'result': 'foobar'})
        )

        # Resuming both subwf is resuming wf1
        self.await_workflow_running(wf1_ex.id)

        self.await_workflow_success(wf2_ex.id)
        self.await_workflow_success(wf3_ex.id)
        self.await_workflow_success(wf1_ex.id)

    def test_with_items_cascade(self):
        # Purpose of this tests is to test that a wf creating subwfs
        # from items (with-items) can be paused and pause will cascade down
        # to all subwf
        wb_text = """
        version: '2.0'

        name: wb

        workflows:
          wf1:
            tasks:
              task1:
                with-items: i in <% range(2) %>
                workflow: wf2

          wf2:
            tasks:
              task1:
                action: std.async_noop
        """

        wb_service.create_workbook_v2(wb_text)

        # Start workflow execution.
        wf1_ex = self.engine.start_workflow('wb.wf1')

        self.await_workflow_state(wf1_ex.id, states.RUNNING)

        with db_api.transaction():
            # Grab latest info
            wf_execs = db_api.get_workflow_executions()
            wf1_ex = self._assert_single_item(wf_execs, name='wb.wf1')

            wf1_task1 = wf1_ex.task_executions
            wf1_task1 = self._assert_single_item(
                wf1_ex.task_executions,
                name='task1'
            )

        # Wait for the first task to be running
        # It will run until we send a action_complete (later in this test)
        self.await_task_running(wf1_task1.id)

        with db_api.transaction():
            # Grab latest info
            wf_execs = db_api.get_workflow_executions()
            wf1_ex = self._assert_single_item(wf_execs, name='wb.wf1')

            wf1_task1 = wf1_ex.task_executions
            wf1_task1 = self._assert_single_item(
                wf1_ex.task_executions,
                name='task1'
            )
            wf1_task1_actions = sorted(
                wf1_task1.executions,
                key=lambda x: x['runtime_context']['index']
            )

            # Get the two with-items subworkflow executions.
            wf2_ex1 = db_api.get_workflow_execution(
                wf1_task1_actions[0].id
            )
            wf2_ex2 = db_api.get_workflow_execution(
                wf1_task1_actions[1].id
            )

        # NOTE(amorin) we need to await the wf to make sure it's actually
        # running and avoid race condition with IDLE state
        # See lp-2051040
        self.await_workflow_state(wf2_ex1.id, states.RUNNING)
        self.await_workflow_state(wf2_ex2.id, states.RUNNING)

        with db_api.transaction():
            # Grab latest info
            wf2_ex1 = db_api.get_workflow_execution(wf2_ex1.id)
            wf2_ex2 = db_api.get_workflow_execution(wf2_ex2.id)

            wf2_ex1_task1 = self._assert_single_item(
                wf2_ex1.task_executions,
                name='task1'
            )
            wf2_ex2_task1 = self._assert_single_item(
                wf2_ex2.task_executions,
                name='task1'
            )

        # And wait for the tasks to be RUNNING
        self.await_task_running(wf2_ex1_task1.id)
        self.await_task_running(wf2_ex2_task1.id)

        with db_api.transaction():
            # Grab actions so we can complete it after
            wf2_ex1_task1_actions = db_api.get_action_executions(
                task_execution_id=wf2_ex1_task1.id
            )
            wf2_ex2_task1_actions = db_api.get_action_executions(
                task_execution_id=wf2_ex2_task1.id
            )

        # Pause the main workflow.
        self.engine.pause_workflow(wf1_ex.id)

        # This should pause wf1 and its task
        self.await_workflow_paused(wf1_ex.id)
        self.await_task_paused(wf1_task1.id)

        # And this should cascade down to all subwf
        self.await_workflow_paused(wf2_ex1.id)
        self.await_workflow_paused(wf2_ex2.id)

        # But tasks stay running (async noop)
        self.await_task_running(wf2_ex1_task1.id)
        self.await_task_running(wf2_ex2_task1.id)

        # Resume the main workflow.
        self.engine.resume_workflow(wf1_ex.id)

        # This should resume wf1
        self.await_workflow_running(wf1_ex.id)
        self.await_task_running(wf1_task1.id)

        # But also wf2 subwfs
        self.await_workflow_running(wf2_ex1.id)
        self.await_workflow_running(wf2_ex2.id)
        self.await_task_running(wf2_ex1_task1.id)
        self.await_task_running(wf2_ex2_task1.id)

        # Complete action execution of subworkflows.
        self.engine.on_action_complete(
            wf2_ex1_task1_actions[0].id,
            ml_actions.Result(data={'result': 'foobar'})
        )

        self.engine.on_action_complete(
            wf2_ex2_task1_actions[0].id,
            ml_actions.Result(data={'result': 'foobar'})
        )

        self.await_workflow_success(wf2_ex1.id)
        self.await_workflow_success(wf2_ex2.id)
        self.await_workflow_success(wf1_ex.id)

    def test_pause_before_cascade(self):
        # Purpose of this test is to verify if a pause-before in a subwf will
        # pause the main wf
        wb_text = """
        version: '2.0'

        name: wb

        workflows:
          wf1:
            tasks:
              task1:
                workflow: wf2

          wf2:
            tasks:
              task1:
                pause-before: true
                action: std.async_noop
        """

        wb_service.create_workbook_v2(wb_text)

        # Start workflow execution.
        wf1_ex = self.engine.start_workflow('wb.wf1')

        self.await_workflow_state(wf1_ex.id, states.PAUSED)

        with db_api.transaction():
            wf_execs = db_api.get_workflow_executions()
            wf1_ex = self._assert_single_item(wf_execs, name='wb.wf1')
            wf2_ex = self._assert_single_item(wf_execs, name='wb.wf2')

            wf2_task1 = self._assert_single_item(
                wf2_ex.task_executions,
                name='task1'
            )

        # Make sure the task and wf are paused
        self.await_workflow_state(wf2_ex.id, states.PAUSED)
        # NOTE(amorin) not sure why the state is IDLE here, that was coded
        # like this in the past, even if my logic would suggest to have
        # PAUSED instead.
        # Maybe because the task actually never started
        # seen in logs: [RUNNING -> IDLE, msg=Set by 'pause-before' policy]
        self.await_task_state(wf2_task1.id, states.IDLE)

        # Resume wf2
        self.engine.resume_workflow(wf2_ex.id)

        # Make sure it's back running
        self.await_workflow_running(wf1_ex.id)
        self.await_workflow_running(wf2_ex.id)
        self.await_task_running(wf2_task1.id)

        with db_api.transaction():
            # Grab action so we can complete it below
            wf2_task1_actions = db_api.get_action_executions(
                task_execution_id=wf2_task1.id
            )

        # Complete action execution of subworkflows.
        self.engine.on_action_complete(
            wf2_task1_actions[0].id,
            ml_actions.Result(data={'result': 'foobar'})
        )

        self.await_workflow_success(wf2_ex.id)
        self.await_workflow_success(wf1_ex.id)
