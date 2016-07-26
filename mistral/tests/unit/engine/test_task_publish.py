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
from mistral.services import workbooks as wb_service
from mistral.tests.unit.engine import base
from mistral.workflow import states

# Use the set_default method to set value otherwise in certain test cases
# the change in value is not permanent.
cfg.CONF.set_default('auth_enable', False, group='pecan')


SIMPLE_WORKBOOK = """
---
version: '2.0'
name: wb1
workflows:
  wf1:
    type: direct
    tasks:
      t1:
        action: std.echo output="Task 1"
        publish:
          v1: <% $.t1.get($foobar) %>
        on-success:
          - t2
      t2:
        action: std.echo output="Task 2"
        on-success:
          - t3
      t3:
        action: std.echo output="Task 3"
"""


class TaskPublishTest(base.EngineTestCase):

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
    def test_publish_failure(self):
        wb_service.create_workbook_v2(SIMPLE_WORKBOOK)

        # Run workflow and fail task.
        wf_ex = self.engine.start_workflow('wb1.wf1', {})

        self.await_workflow_error(wf_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.ERROR, wf_ex.state)
        self.assertEqual(1, len(wf_ex.task_executions))

        task_1_ex = self._assert_single_item(wf_ex.task_executions, name='t1')

        # Task 1 should have failed.
        self.assertEqual(states.ERROR, task_1_ex.state)
        self.assertIn('Can not evaluate YAQL expression', task_1_ex.state_info)

        # Action execution of task 1 should have succeeded.
        task_1_action_exs = db_api.get_action_executions(
            task_execution_id=task_1_ex.id)

        self.assertEqual(1, len(task_1_action_exs))
        self.assertEqual(states.SUCCESS, task_1_action_exs[0].state)
