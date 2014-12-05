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

from oslo.config import cfg

from mistral.db.v2 import api as db_api
from mistral.openstack.common import log as logging
from mistral.services import scheduler
from mistral.services import workbooks as wb_service
from mistral.tests.unit.engine1 import base
from mistral.workbook import parser as spec_parser
from mistral.workflow import states
from mistral.workflow import utils

LOG = logging.getLogger(__name__)
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
        exec_db = self.engine.start_workflow('wb.wf1', {})

        self._await(lambda: self.is_execution_paused(exec_db.id))

        exec_db = db_api.get_execution(exec_db.id)

        self.assertEqual(states.PAUSED, exec_db.state)
        self.assertEqual(1, len(exec_db.tasks))

        self.engine.resume_workflow(exec_db.id)
        exec_db = db_api.get_execution(exec_db.id)

        self.assertEqual(states.RUNNING, exec_db.state)

        self._await(lambda: self.is_execution_success(exec_db.id))
        exec_db = db_api.get_execution(exec_db.id)

        self.assertEqual(states.SUCCESS, exec_db.state)
        self.assertEqual(2, len(exec_db.tasks))

    def test_resume_reverse(self):
        wb_service.create_workbook_v2(RESUME_WORKBOOK_REVERSE)

        # Start workflow.
        exec_db = self.engine.start_workflow(
            'resume_reverse.wf',
            {}, task_name='task2'
        )

        # Note: We need to reread execution to access related tasks.

        self.engine.pause_workflow(exec_db.id)
        exec_db = db_api.get_execution(exec_db.id)

        self.assertEqual(states.PAUSED, exec_db.state)
        self.assertEqual(1, len(exec_db.tasks))

        self.engine.resume_workflow(exec_db.id)
        exec_db = db_api.get_execution(exec_db.id)

        self.assertEqual(states.RUNNING, exec_db.state)

        self._await(lambda: self.is_execution_success(exec_db.id))
        exec_db = db_api.get_execution(exec_db.id)

        self.assertEqual(states.SUCCESS, exec_db.state)
        self.assertEqual(2, len(exec_db.tasks))

    def test_resume_two_branches(self):
        wb_service.create_workbook_v2(WORKBOOK_TWO_BRANCHES)

        # Start workflow.
        exec_db = self.engine.start_workflow('wb.wf1', {})

        self._await(lambda: self.is_execution_paused(exec_db.id))

        exec_db = db_api.get_execution(exec_db.id)

        self.assertEqual(states.PAUSED, exec_db.state)
        self.assertEqual(1, len(exec_db.tasks))

        self.engine.resume_workflow(exec_db.id)
        exec_db = db_api.get_execution(exec_db.id)

        self.assertEqual(states.RUNNING, exec_db.state)

        self._await(lambda: self.is_execution_success(exec_db.id))
        exec_db = db_api.get_execution(exec_db.id)

        self.assertEqual(states.SUCCESS, exec_db.state)

        # We can see 3 tasks in execution.
        self.assertEqual(3, len(exec_db.tasks))

    def test_resume_two_start_tasks(self):
        wb_service.create_workbook_v2(WORKBOOK_TWO_START_TASKS)

        # Start workflow.
        exec_db = self.engine.start_workflow('wb.wf1', {})

        self._await(lambda: self.is_execution_paused(exec_db.id))

        exec_db = db_api.get_execution(exec_db.id)

        self.assertEqual(states.PAUSED, exec_db.state)
        self.assertEqual(2, len(exec_db.tasks))

        self.engine.resume_workflow(exec_db.id)
        exec_db = db_api.get_execution(exec_db.id)

        self.assertEqual(states.RUNNING, exec_db.state)

        self._await(lambda: self.is_execution_success(exec_db.id))
        exec_db = db_api.get_execution(exec_db.id)

        self.assertEqual(states.SUCCESS, exec_db.state)
        self.assertEqual(3, len(exec_db.tasks))

    def test_resume_different_task_states(self):
        wb_service.create_workbook_v2(WORKBOOK_DIFFERENT_TASK_STATES)

        # Start workflow.
        exec_db = self.engine.start_workflow('wb.wf1', {})

        self._await(lambda: self.is_execution_paused(exec_db.id))

        exec_db = db_api.get_execution(exec_db.id)

        self.assertEqual(states.PAUSED, exec_db.state)
        self.assertEqual(2, len(exec_db.tasks))

        task2 = self._assert_single_item(exec_db.tasks, name="task2")

        # Task2 is not finished yet.
        self.assertFalse(states.is_completed(task2.state))

        self.engine.resume_workflow(exec_db.id)
        exec_db = db_api.get_execution(exec_db.id)

        self.assertEqual(states.RUNNING, exec_db.state)

        # Finish task2.
        self.engine.on_task_result(task2.id, utils.TaskResult())

        self._await(lambda: self.is_execution_success(exec_db.id))
        exec_db = db_api.get_execution(exec_db.id)

        self.assertEqual(states.SUCCESS, exec_db.state)
        self.assertEqual(4, len(exec_db.tasks))
