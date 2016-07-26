# Copyright (c) 2016 Intel Corporation
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import mock

from mistral.db.v2 import api as db_api
from mistral.engine import default_executor
from mistral.engine.rpc_backend import rpc
from mistral.services import workflows as wf_service
from mistral.tests.unit.engine import base
from mistral.workflow import data_flow
from mistral.workflow import states


def _run_at_target(action_ex_id, action_class_str, attributes,
                   action_params, target=None, async=True, safe_rerun=False):
    # We'll just call executor directly for testing purposes.
    executor = default_executor.DefaultExecutor(rpc.get_engine_client())

    executor.run_action(
        action_ex_id,
        action_class_str,
        attributes,
        action_params,
        safe_rerun,
        redelivered=True
    )


MOCK_RUN_AT_TARGET = mock.MagicMock(side_effect=_run_at_target)


class TestSafeRerun(base.EngineTestCase):

    @mock.patch.object(rpc.ExecutorClient, 'run_action', MOCK_RUN_AT_TARGET)
    def test_safe_rerun_true(self):
        wf_text = """---
        version: '2.0'

        wf:
          tasks:
            task1:
              action: std.noop
              safe-rerun: true
              on-success:
                - task2
              on-error:
                - task3

            task2:
              action: std.noop
              safe-rerun: true

            task3:
              action: std.noop
              safe-rerun: true
        """
        # Note: because every task have redelivered flag set to true in mock
        # function (_run_at_target), task2 and task3 have to set safe-rerun
        # to true.

        wf_service.create_workflows(wf_text)
        wf_ex = self.engine.start_workflow('wf', {})

        self.await_workflow_success(wf_ex.id)

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        tasks = wf_ex.task_executions

        self.assertEqual(len(tasks), 2)

        task1 = self._assert_single_item(tasks, name='task1')
        task2 = self._assert_single_item(tasks, name='task2')

        self.assertEqual(task1.state, states.SUCCESS)
        self.assertEqual(task2.state, states.SUCCESS)

    @mock.patch.object(rpc.ExecutorClient, 'run_action', MOCK_RUN_AT_TARGET)
    def test_safe_rerun_false(self):
        wf_text = """---
        version: '2.0'

        wf:
          tasks:
            task1:
              action: std.noop
              safe-rerun: false
              on-success:
                - task2
              on-error:
                - task3

            task2:
              action: std.noop
              safe-rerun: true

            task3:
              action: std.noop
              safe-rerun: true
        """
        # Note: because every task have redelivered flag set to true in mock
        # function (_run_at_target), task2 and task3 have to set safe-rerun
        # to true.

        wf_service.create_workflows(wf_text)
        wf_ex = self.engine.start_workflow('wf', {})

        self.await_workflow_success(wf_ex.id)

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        tasks = wf_ex.task_executions

        self.assertEqual(len(tasks), 2)

        task1 = self._assert_single_item(tasks, name='task1')
        task3 = self._assert_single_item(tasks, name='task3')

        self.assertEqual(task1.state, states.ERROR)
        self.assertEqual(task3.state, states.SUCCESS)

    @mock.patch.object(rpc.ExecutorClient, 'run_action', MOCK_RUN_AT_TARGET)
    def test_safe_rerun_with_items(self):
        wf_text = """---
        version: '2.0'

        wf:
          tasks:
            task1:
              with-items: i in [1, 2, 3]
              action: std.echo output=<% $.i %>
              safe-rerun: true
              publish:
                result: <% task(task1).result %>

        """

        wf_service.create_workflows(wf_text)
        wf_ex = self.engine.start_workflow('wf', {})

        self.await_workflow_success(wf_ex.id)

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        tasks = wf_ex.task_executions

        self.assertEqual(len(tasks), 1)

        task1 = self._assert_single_item(tasks, name='task1')

        self.assertEqual(task1.state, states.SUCCESS)

        result = data_flow.get_task_execution_result(task1)

        self.assertIn(1, result)
        self.assertIn(2, result)
        self.assertIn(3, result)
