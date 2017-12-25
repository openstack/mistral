# Copyright 2017 - Brocade Communications Systems, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License");
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
from oslo_log import log as logging

from mistral.actions import std_actions
from mistral.db.v2 import api as db_api
from mistral.executors import base as exe
from mistral.executors import remote_executor as r_exe
from mistral.services import workbooks as wb_svc
from mistral.tests.unit.executors import base
from mistral.workflow import states


LOG = logging.getLogger(__name__)


# Use the set_default method to set value otherwise in certain test cases
# the change in value is not permanent.
cfg.CONF.set_default('auth_enable', False, group='pecan')


@mock.patch.object(
    r_exe.RemoteExecutor,
    'run_action',
    mock.MagicMock(return_value=None)
)
class LocalExecutorTestCase(base.ExecutorTestCase):

    @classmethod
    def setUpClass(cls):
        super(LocalExecutorTestCase, cls).setUpClass()
        cfg.CONF.set_default('type', 'local', group='executor')

    @classmethod
    def tearDownClass(cls):
        exe.cleanup()
        cfg.CONF.set_default('type', 'remote', group='executor')
        super(LocalExecutorTestCase, cls).tearDownClass()

    @mock.patch.object(
        std_actions.EchoAction,
        'run',
        mock.MagicMock(
            side_effect=[
                'Task 1',               # Mock task1 success.
                'Task 2',               # Mock task2 success.
                'Task 3'                # Mock task3 success.
            ]
        )
    )
    def test_run(self):
        wb_def = """
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

        wb_svc.create_workbook_v2(wb_def)

        wf_ex = self.engine.start_workflow('wb1.wf1')

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

        self.assertEqual(states.SUCCESS, task_1_ex.state)
        self.assertEqual(states.SUCCESS, task_2_ex.state)
        self.assertEqual(states.SUCCESS, task_3_ex.state)

        # Make sure the remote executor is not called.
        self.assertFalse(r_exe.RemoteExecutor.run_action.called)

    @mock.patch.object(
        std_actions.EchoAction,
        'run',
        mock.MagicMock(
            side_effect=[
                'Task 1.0',             # Mock task1 success.
                'Task 1.1',             # Mock task1 success.
                'Task 1.2',             # Mock task1 success.
                'Task 2'                # Mock task2 success.
            ]
        )
    )
    def test_run_with_items(self):
        wb_def = """
        version: '2.0'

        name: wb1

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

        wb_svc.create_workbook_v2(wb_def)

        wf_ex = self.engine.start_workflow('wb1.wf1')

        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
            task_execs = wf_ex.task_executions

        self.assertEqual(states.SUCCESS, wf_ex.state)
        self.assertEqual(2, len(wf_ex.task_executions))

        task_1_ex = self._assert_single_item(task_execs, name='t1')
        task_2_ex = self._assert_single_item(task_execs, name='t2')

        self.assertEqual(states.SUCCESS, task_1_ex.state)
        self.assertEqual(states.SUCCESS, task_2_ex.state)

        with db_api.transaction():
            task_1_action_exs = db_api.get_action_executions(
                task_execution_id=task_1_ex.id
            )

        self.assertEqual(3, len(task_1_action_exs))

        # Make sure the remote executor is not called.
        self.assertFalse(r_exe.RemoteExecutor.run_action.called)
