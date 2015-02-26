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
from oslo.config import cfg

from mistral.db.v2 import api as db_api
from mistral.engine1 import default_engine as de
from mistral import exceptions as exc
from mistral.services import scheduler
from mistral.services import workbooks as wb_service
from mistral.tests.unit.engine1 import base
from mistral.workbook import parser as spec_parser
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
          - pause
          - task2

      task2:
        action: std.echo output="Task 2"
"""


RESUME_WORKBOOK_REVERSE = """
---
version: 2.0

name: resume_reverse

workflows:
  wf:
    type: reverse

    tasks:
      task1:
        action: std.echo output="Hi!"
        policies:
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
          - pause
          - task2
          - task3

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
        action: std.echo output="Hi!"
        on-complete:
          - pause
          - task3

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
          - pause
          - task3

      task2:
        action: std.mistral_http url="http://google.com"
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

        thread_group = scheduler.setup()
        self.addCleanup(thread_group.stop)

    def test_resume_direct(self):
        wb_service.create_workbook_v2(RESUME_WORKBOOK)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wb.wf1', {})

        self._await(lambda: self.is_execution_paused(wf_ex.id))

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.PAUSED, wf_ex.state)
        self.assertEqual(1, len(wf_ex.task_executions))

        self.engine.resume_workflow(wf_ex.id)
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.RUNNING, wf_ex.state)

        self._await(lambda: self.is_execution_success(wf_ex.id))
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.SUCCESS, wf_ex.state)
        self.assertEqual(2, len(wf_ex.task_executions))

    def test_resume_reverse(self):
        wb_service.create_workbook_v2(RESUME_WORKBOOK_REVERSE)

        # Start workflow.
        wf_ex = self.engine.start_workflow(
            'resume_reverse.wf',
            {}, task_name='task2'
        )

        # Note: We need to reread execution to access related tasks.

        self.engine.pause_workflow(wf_ex.id)
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.PAUSED, wf_ex.state)
        self.assertEqual(1, len(wf_ex.task_executions))

        self.engine.resume_workflow(wf_ex.id)
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.RUNNING, wf_ex.state)

        self._await(lambda: self.is_execution_success(wf_ex.id))
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.SUCCESS, wf_ex.state)
        self.assertEqual(2, len(wf_ex.task_executions))

    def test_resume_two_branches(self):
        wb_service.create_workbook_v2(WORKBOOK_TWO_BRANCHES)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wb.wf1', {})

        self._await(lambda: self.is_execution_paused(wf_ex.id))

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.PAUSED, wf_ex.state)
        self.assertEqual(1, len(wf_ex.task_executions))

        self.engine.resume_workflow(wf_ex.id)
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.RUNNING, wf_ex.state)

        self._await(lambda: self.is_execution_success(wf_ex.id))
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.SUCCESS, wf_ex.state)

        # We can see 3 tasks in execution.
        self.assertEqual(3, len(wf_ex.task_executions))

    def test_resume_two_start_tasks(self):
        wb_service.create_workbook_v2(WORKBOOK_TWO_START_TASKS)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wb.wf1', {})

        self._await(lambda: self.is_execution_paused(wf_ex.id))

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.PAUSED, wf_ex.state)
        self.assertEqual(2, len(wf_ex.task_executions))

        self.engine.resume_workflow(wf_ex.id)
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.RUNNING, wf_ex.state)

        self._await(lambda: self.is_execution_success(wf_ex.id))
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.SUCCESS, wf_ex.state)
        self.assertEqual(3, len(wf_ex.task_executions))

    def test_resume_different_task_states(self):
        wb_service.create_workbook_v2(WORKBOOK_DIFFERENT_TASK_STATES)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wb.wf1', {})

        self._await(lambda: self.is_execution_paused(wf_ex.id))

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.PAUSED, wf_ex.state)
        self.assertEqual(2, len(wf_ex.task_executions))

        task2 = self._assert_single_item(wf_ex.task_executions, name='task2')

        # Task2 is not finished yet.
        self.assertFalse(states.is_completed(task2.state))

        self.engine.resume_workflow(wf_ex.id)
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.RUNNING, wf_ex.state)

        # Finish task2.
        self.engine.on_task_result(task2.id, utils.TaskResult())

        self._await(lambda: self.is_execution_success(wf_ex.id))
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.SUCCESS, wf_ex.state)
        self.assertEqual(4, len(wf_ex.task_executions))

    @mock.patch.object(de.DefaultEngine, '_fail_workflow')
    def test_resume_fails(self, mock_fw):
        # Start and pause workflow.
        wb_service.create_workbook_v2(WORKBOOK_DIFFERENT_TASK_STATES)
        wf_ex = self.engine.start_workflow('wb.wf1', {})

        self._await(lambda: self.is_execution_paused(wf_ex.id))

        wf_ex = db_api.get_workflow_execution(wf_ex.id)
        self.assertEqual(states.PAUSED, wf_ex.state)

        # Simulate failure and check if it is handled.
        err = exc.MistralException('foo')
        with mock.patch.object(
                de.DefaultEngine,
                '_run_remote_commands',
                side_effect=err):

            self.assertRaises(
                exc.MistralException,
                self.engine.resume_workflow,
                wf_ex.id
            )
            mock_fw.assert_called_once_with(wf_ex.id, err)
