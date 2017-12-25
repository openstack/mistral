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

import mock
import testtools

from mistral.actions import std_actions
from mistral.db.v2 import api as db_api
from mistral.services import workbooks as wb_service
from mistral.services import workflows as wf_service
from mistral.tests.unit.engine import base
from mistral.workflow import states
from mistral_lib import actions as ml_actions


class TaskCancelTest(base.EngineTestCase):

    def test_cancel_action_execution(self):
        workflow = """
        version: '2.0'

        wf:
          tasks:
            task1:
              action: std.async_noop
              on-success:
                - task2
              on-error:
                - task3
              on-complete:
                - task4

            task2:
              action: std.noop
            task3:
              action: std.noop
            task4:
              action: std.noop
        """

        wf_service.create_workflows(workflow)

        wf_ex = self.engine.start_workflow('wf')

        self.await_workflow_state(wf_ex.id, states.RUNNING)

        with db_api.transaction():
            wf_execs = db_api.get_workflow_executions()

            wf_ex = self._assert_single_item(wf_execs, name='wf')

            task_1_ex = self._assert_single_item(
                wf_ex.task_executions,
                name='task1'
            )

        task_1_action_exs = db_api.get_action_executions(
            task_execution_id=task_1_ex.id
        )

        self.assertEqual(1, len(task_1_action_exs))
        self.assertEqual(states.RUNNING, task_1_action_exs[0].state)

        self.engine.on_action_complete(
            task_1_action_exs[0].id,
            ml_actions.Result(cancel=True)
        )

        self.await_workflow_cancelled(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_1_ex = self._assert_single_item(
                wf_ex.task_executions,
                name='task1'
            )

        self.await_task_cancelled(task_1_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_execs = wf_ex.task_executions

        task_1_ex = self._assert_single_item(task_execs, name='task1')

        task_1_action_exs = db_api.get_action_executions(
            task_execution_id=task_1_ex.id
        )

        self.assertEqual(states.CANCELLED, wf_ex.state)
        self.assertEqual("Cancelled tasks: task1", wf_ex.state_info)
        self.assertEqual(1, len(task_execs))
        self.assertEqual(states.CANCELLED, task_1_ex.state)
        self.assertIsNone(task_1_ex.state_info)
        self.assertEqual(1, len(task_1_action_exs))
        self.assertEqual(states.CANCELLED, task_1_action_exs[0].state)
        self.assertIsNone(task_1_action_exs[0].state_info)

    def test_cancel_child_workflow_action_execution(self):
        workbook = """
        version: '2.0'

        name: wb

        workflows:
            wf:
              tasks:
                taskx:
                  workflow: subwf

            subwf:
              tasks:
                task1:
                  action: std.async_noop
                  on-success:
                    - task2
                  on-error:
                    - task3
                  on-complete:
                    - task4

                task2:
                  action: std.noop
                task3:
                  action: std.noop
                task4:
                  action: std.noop
        """

        wb_service.create_workbook_v2(workbook)

        wf_ex = self.engine.start_workflow('wb.wf')

        self.await_workflow_state(wf_ex.id, states.RUNNING)

        with db_api.transaction():
            wf_execs = db_api.get_workflow_executions()

            wf_ex = self._assert_single_item(wf_execs, name='wb.wf')
            task_ex = self._assert_single_item(
                wf_ex.task_executions,
                name='taskx'
            )
            subwf_ex = self._assert_single_item(wf_execs, name='wb.subwf')

            task_1_ex = self._assert_single_item(
                subwf_ex.task_executions,
                name='task1'
            )

        task_1_action_exs = db_api.get_action_executions(
            task_execution_id=task_1_ex.id
        )

        self.assertEqual(1, len(task_1_action_exs))
        self.assertEqual(states.RUNNING, task_1_action_exs[0].state)

        self.engine.on_action_complete(
            task_1_action_exs[0].id,
            ml_actions.Result(cancel=True)
        )

        self.await_workflow_cancelled(subwf_ex.id)
        self.await_task_cancelled(task_ex.id)
        self.await_workflow_cancelled(wf_ex.id)

        with db_api.transaction():
            wf_execs = db_api.get_workflow_executions()

            wf_ex = self._assert_single_item(wf_execs, name='wb.wf')
            task_ex = self._assert_single_item(
                wf_ex.task_executions,
                name='taskx'
            )

            subwf_ex = self._assert_single_item(wf_execs, name='wb.subwf')

            subwf_task_execs = subwf_ex.task_executions

        self.assertEqual(states.CANCELLED, subwf_ex.state)
        self.assertEqual("Cancelled tasks: task1", subwf_ex.state_info)
        self.assertEqual(1, len(subwf_task_execs))
        self.assertEqual(states.CANCELLED, task_ex.state)
        self.assertEqual("Cancelled tasks: task1", task_ex.state_info)
        self.assertEqual(states.CANCELLED, wf_ex.state)
        self.assertEqual("Cancelled tasks: taskx", wf_ex.state_info)

    def test_cancel_action_execution_with_task_retry(self):
        workflow = """
        version: '2.0'

        wf:
          tasks:
            task1:
              action: std.async_noop
              retry:
                count: 3
                delay: 0
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

            task_1_ex = self._assert_single_item(
                wf_ex.task_executions,
                name='task1'
            )

        task_1_action_exs = db_api.get_action_executions(
            task_execution_id=task_1_ex.id
        )

        self.assertEqual(1, len(task_1_action_exs))
        self.assertEqual(states.RUNNING, task_1_action_exs[0].state)

        self.engine.on_action_complete(
            task_1_action_exs[0].id,
            ml_actions.Result(cancel=True)
        )

        self.await_workflow_cancelled(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_1_ex = self._assert_single_item(
                wf_ex.task_executions,
                name='task1'
            )

        self.await_task_cancelled(task_1_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_execs = wf_ex.task_executions

        task_1_ex = self._assert_single_item(task_execs, name='task1')

        task_1_action_exs = db_api.get_action_executions(
            task_execution_id=task_1_ex.id
        )

        self.assertEqual(states.CANCELLED, wf_ex.state)
        self.assertEqual("Cancelled tasks: task1", wf_ex.state_info)
        self.assertEqual(1, len(task_execs))
        self.assertEqual(states.CANCELLED, task_1_ex.state)
        self.assertIsNone(task_1_ex.state_info)
        self.assertEqual(1, len(task_1_action_exs))
        self.assertEqual(states.CANCELLED, task_1_action_exs[0].state)
        self.assertIsNone(task_1_action_exs[0].state_info)

    @testtools.skip('Restore concurrency support.')
    @mock.patch.object(
        std_actions.EchoAction,
        'run',
        mock.MagicMock(
            side_effect=[
                'Task 2'                # Mock task2 success.
            ]
        )
    )
    def test_cancel_with_items_concurrency(self):
        wb_def = """
            version: '2.0'

            name: wb1

            workflows:
              wf1:
                tasks:
                  t1:
                    with-items: i in <% list(range(0, 4)) %>
                    action: std.async_noop
                    concurrency: 2
                    on-success:
                      - t2
                  t2:
                    action: std.echo output="Task 2"
        """

        wb_service.create_workbook_v2(wb_def)

        wf1_ex = self.engine.start_workflow('wb1.wf1')

        self.await_workflow_state(wf1_ex.id, states.RUNNING)

        with db_api.transaction():
            wf1_execs = db_api.get_workflow_executions()

            wf1_ex = self._assert_single_item(wf1_execs, name='wb1.wf1')
            wf1_t1_ex = self._assert_single_item(
                wf1_ex.task_executions,
                name='t1'
            )

        wf1_t1_action_exs = db_api.get_action_executions(
            task_execution_id=wf1_t1_ex.id
        )

        self.assertEqual(2, len(wf1_t1_action_exs))
        self.assertEqual(states.RUNNING, wf1_t1_action_exs[0].state)
        self.assertEqual(states.RUNNING, wf1_t1_action_exs[1].state)

        # Cancel action execution for task.
        for wf1_t1_action_ex in wf1_t1_action_exs:
            self.engine.on_action_complete(
                wf1_t1_action_ex.id,
                ml_actions.Result(cancel=True)
            )

        self.await_task_cancelled(wf1_t1_ex.id)
        self.await_workflow_cancelled(wf1_ex.id)

        wf1_t1_action_exs = db_api.get_action_executions(
            task_execution_id=wf1_t1_ex.id
        )

        self.assertEqual(2, len(wf1_t1_action_exs))
        self.assertEqual(states.CANCELLED, wf1_t1_action_exs[0].state)
        self.assertEqual(states.CANCELLED, wf1_t1_action_exs[1].state)
