# Copyright 2014 - Mirantis, Inc.
# Copyright 2015 - StackStorm, Inc.
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
from mistral import exceptions as exc
from mistral.services import workflows as wf_service
from mistral.tests.unit.engine import base
from mistral.workflow import states


# Use the set_default method to set value otherwise in certain test cases
# the change in value is not permanent.
cfg.CONF.set_default('auth_enable', False, group='pecan')


class ExecutionStateInfoTest(base.EngineTestCase):
    def test_state_info(self):
        workflow = """---
        version: '2.0'
        test_wf:
          type: direct
          tasks:
            task1:
              action: std.fail

            task2:
              action: std.noop
        """
        wf_service.create_workflows(workflow)

        # Start workflow.
        wf_ex = self.engine.start_workflow('test_wf')

        self.await_workflow_error(wf_ex.id)

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertIn("error in tasks: task1", wf_ex.state_info)

    def test_state_info_two_failed_branches(self):
        workflow = """---
        version: '2.0'
        test_wf:
          type: direct
          tasks:
            task1:
              action: std.fail

            task2:
              action: std.fail
        """
        wf_service.create_workflows(workflow)

        # Start workflow.
        wf_ex = self.engine.start_workflow('test_wf')

        self.await_workflow_error(wf_ex.id)

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertIn("error in tasks: task1, task2", wf_ex.state_info)

    def test_state_info_with_policies(self):
        workflow = """---
        version: '2.0'
        test_wf:
          type: direct
          tasks:
            task1:
              action: std.fail
              wait-after: 1

            task2:
              action: std.noop
              wait-after: 3
        """
        wf_service.create_workflows(workflow)

        # Start workflow.
        wf_ex = self.engine.start_workflow('test_wf')

        self.await_workflow_error(wf_ex.id)

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertIn("error in tasks: task1", wf_ex.state_info)

    @mock.patch.object(
        std_actions.EchoAction,
        'run',
        mock.MagicMock(
            side_effect=[
                exc.ActionException(),  # Mock task1 exception for initial run.
                'Task 1.1',             # Mock task1 success for initial run.
                exc.ActionException(),  # Mock task1 exception for initial run.
                'Task 1.0',             # Mock task1 success for rerun.
                'Task 1.2'              # Mock task1 success for rerun.
            ]
        )
    )
    def test_state_info_with_items(self):
        workflow = """---
        version: '2.0'
        wf:
          type: direct
          tasks:
            t1:
              with-items: i in <% list(range(0, 3)) %>
              action: std.echo output="Task 1.<% $.i %>"
        """

        wf_service.create_workflows(workflow)

        wf_ex = self.engine.start_workflow('wf')

        self.await_workflow_error(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_execs = wf_ex.task_executions

        self.assertEqual(states.ERROR, wf_ex.state)

        task_1_ex = self._assert_single_item(task_execs, name='t1')

        self.assertEqual(states.ERROR, task_1_ex.state)

        task_1_action_exs = db_api.get_action_executions(
            task_execution_id=task_1_ex.id
        )

        self.assertEqual(3, len(task_1_action_exs))

        error_actions = [
            action_ex for action_ex in task_1_action_exs if
            action_ex.state == states.ERROR
        ]
        self.assertEqual(2, len(error_actions))

        success_actions = [
            action_ex for action_ex in task_1_action_exs if
            action_ex.state == states.SUCCESS
        ]
        self.assertEqual(1, len(success_actions))

        for action_ex in error_actions:
            self.assertIn(action_ex.id, wf_ex.state_info)

        for action_ex in success_actions:
            self.assertNotIn(action_ex.id, wf_ex.state_info)

    def test_state_info_with_json(self):
        workflow = """---
        version: "2.0"
        wf_state_info:
          type: direct
          tasks:
            main_task:
              action: std.test_dict
              input:
                size: 1
                key_prefix: "abc"
                val: "pqr"
              on-success:
                - fail msg="<% task().result %>"
        """
        wf_service.create_workflows(workflow)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wf_state_info')

        self.await_workflow_error(wf_ex.id)

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertIn('{"abc0": "pqr"}', wf_ex.state_info)
