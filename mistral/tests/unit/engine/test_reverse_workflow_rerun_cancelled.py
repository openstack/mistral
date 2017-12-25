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

from oslo_config import cfg

from mistral.actions import std_actions
from mistral.db.v2 import api as db_api
from mistral.services import workbooks as wb_service
from mistral.tests.unit.engine import base
from mistral.workflow import states
from mistral_lib import actions as ml_actions


# Use the set_default method to set value otherwise in certain test cases
# the change in value is not permanent.
cfg.CONF.set_default('auth_enable', False, group='pecan')


class ReverseWorkflowRerunCancelledTest(base.EngineTestCase):

    @mock.patch.object(
        std_actions.EchoAction,
        'run',
        mock.MagicMock(
            side_effect=[
                'Task 2',               # Mock task2 success.
                'Task 3'                # Mock task3 success.
            ]
        )
    )
    def test_rerun_cancelled_task(self):
        wb_def = """
            version: '2.0'
            name: wb1
            workflows:
              wf1:
                type: reverse
                tasks:
                  t1:
                    action: std.async_noop
                  t2:
                    action: std.echo output="Task 2"
                    requires:
                      - t1
                  t3:
                    action: std.echo output="Task 3"
                    requires:
                      - t2
        """

        wb_service.create_workbook_v2(wb_def)

        wf1_ex = self.engine.start_workflow('wb1.wf1', task_name='t3')

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

        self.assertEqual(1, len(wf1_t1_action_exs))
        self.assertEqual(states.RUNNING, wf1_t1_action_exs[0].state)

        # Cancel action execution for task.
        self.engine.on_action_complete(
            wf1_t1_action_exs[0].id,
            ml_actions.Result(cancel=True)
        )

        self.await_workflow_cancelled(wf1_ex.id)

        with db_api.transaction():
            wf1_ex = db_api.get_workflow_execution(wf1_ex.id)

            wf1_t1_ex = self._assert_single_item(
                wf1_ex.task_executions,
                name='t1'
            )

        self.await_task_cancelled(wf1_t1_ex.id)

        with db_api.transaction():
            wf1_ex = db_api.get_workflow_execution(wf1_ex.id)

            wf1_t1_ex = self._assert_single_item(
                wf1_ex.task_executions,
                name='t1'
            )

        self.assertEqual(states.CANCELLED, wf1_ex.state)
        self.assertEqual("Cancelled tasks: t1", wf1_ex.state_info)
        self.assertEqual(1, len(wf1_ex.task_executions))
        self.assertEqual(states.CANCELLED, wf1_t1_ex.state)
        self.assertIsNone(wf1_t1_ex.state_info)

        # Resume workflow and re-run cancelled task.
        self.engine.rerun_workflow(wf1_t1_ex.id)

        with db_api.transaction():
            wf1_ex = db_api.get_workflow_execution(wf1_ex.id)

            wf1_task_execs = wf1_ex.task_executions

        self.assertEqual(states.RUNNING, wf1_ex.state)
        self.assertIsNone(wf1_ex.state_info)

        # Mark async action execution complete.
        wf1_t1_ex = self._assert_single_item(wf1_task_execs, name='t1')

        wf1_t1_action_exs = db_api.get_action_executions(
            task_execution_id=wf1_t1_ex.id
        )

        self.assertEqual(states.RUNNING, wf1_t1_ex.state)
        self.assertEqual(2, len(wf1_t1_action_exs))
        # Check there is exactly 1 action in Running and 1 in Cancelled state.
        # Order doesn't matter.
        self._assert_single_item(wf1_t1_action_exs, state=states.CANCELLED)
        running_execution = self._assert_single_item(
            wf1_t1_action_exs,
            state=states.RUNNING
        )

        self.engine.on_action_complete(
            running_execution.id,
            ml_actions.Result(data={'foo': 'bar'})
        )

        # Wait for the workflow to succeed.
        self.await_workflow_success(wf1_ex.id)

        with db_api.transaction():
            wf1_ex = db_api.get_workflow_execution(wf1_ex.id)

            wf1_task_execs = wf1_ex.task_executions

        self.assertEqual(states.SUCCESS, wf1_ex.state)
        self.assertIsNone(wf1_ex.state_info)
        self.assertEqual(3, len(wf1_task_execs))

        wf1_t1_ex = self._assert_single_item(wf1_task_execs, name='t1')
        wf1_t2_ex = self._assert_single_item(wf1_task_execs, name='t2')
        wf1_t3_ex = self._assert_single_item(wf1_task_execs, name='t3')

        # Check action executions of task 1.
        self.assertEqual(states.SUCCESS, wf1_t1_ex.state)
        self.assertIsNone(wf1_t2_ex.state_info)

        wf1_t1_action_exs = db_api.get_action_executions(
            task_execution_id=wf1_t1_ex.id
        )

        self.assertEqual(2, len(wf1_t1_action_exs))
        # Check there is exactly 1 action in Success and 1 in Cancelled state.
        # Order doesn't matter.
        self._assert_single_item(wf1_t1_action_exs, state=states.SUCCESS)
        self._assert_single_item(wf1_t1_action_exs, state=states.CANCELLED)

        # Check action executions of task 2.
        self.assertEqual(states.SUCCESS, wf1_t2_ex.state)

        wf1_t2_action_exs = db_api.get_action_executions(
            task_execution_id=wf1_t2_ex.id
        )

        self.assertEqual(1, len(wf1_t2_action_exs))
        self.assertEqual(states.SUCCESS, wf1_t2_action_exs[0].state)

        # Check action executions of task 3.
        self.assertEqual(states.SUCCESS, wf1_t3_ex.state)

        wf1_t3_action_exs = db_api.get_action_executions(
            task_execution_id=wf1_t3_ex.id
        )

        self.assertEqual(1, len(wf1_t3_action_exs))
        self.assertEqual(states.SUCCESS, wf1_t3_action_exs[0].state)
