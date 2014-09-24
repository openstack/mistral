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
from mistral.engine import states
from mistral.engine1 import policies
from mistral.openstack.common import log as logging
from mistral.services import scheduler
from mistral.services import workbooks as wb_service
from mistral.tests.unit.engine1 import base
from mistral.workbook import parser as spec_parser

LOG = logging.getLogger(__name__)
# Use the set_default method to set value otherwise in certain test cases
# the change in value is not permanent.
cfg.CONF.set_default('auth_enable', False, group='pecan')

WORKBOOK = """
---
version: '2.0'

name: wb

workflows:
  wf1:
    type: direct

    tasks:
      task1:
        action: std.echo output="Hi!"
        policies:
          wait-before: 2
          wait-after: 5
          timeout: 7
          retry:
            count: 5
            delay: 10
            break-on: $.my_val = 10
"""


WB_WITH_DEFAULTS = """
---
version: '2.0'

name: wb

workflows:
  wf1:
    type: direct

    task-defaults:
      policies:
        wait-before: 2
        retry:
          count: 2
          delay: 1

    tasks:
      task1:
        action: std.echo output="Hi!"
        policies:
          wait-before: 3
          wait-after: 5
          timeout: 7

"""


WAIT_BEFORE_WB = """
---
version: '2.0'

name: wb

workflows:
  wf1:
    type: direct

    tasks:
      task1:
        action: std.echo output="Hi!"
        policies:
          wait-before: 1
"""


WAIT_AFTER_WB = """
---
version: '2.0'

name: wb

workflows:
  wf1:
    type: direct

    tasks:
      task1:
        action: std.echo output="Hi!"
        policies:
          wait-after: 2
"""


RETRY_WB = """
---
version: '2.0'

name: wb

workflows:
  wf1:
    type: direct

    tasks:
      task1:
        action: std.http url="http://some_non-existing_host"
        policies:
          retry:
            count: 2
            delay: 2
            break-on: $.my_val = 10
"""


TIMEOUT_WB = """
---
version: '2.0'

name: wb

workflows:
  wf1:
    type: direct

    tasks:
      task1:
        action: std.mistral_http
        policies:
          timeout: 2
        input:
          # We need to fix this
          action_context:
            workbook_name: wb
            execution_id: 123
            task_id: 3121
          url: http://google.com
          method: GET
        on-error:
          - task2

      task2:
        action: std.echo output="Hi!"
        policies:
          timeout: 2
"""


TIMEOUT_WB2 = """
---
version: '2.0'
name: wb
workflows:
  wf1:
    type: direct

    tasks:
      task1:
        action: std.echo output="Hi!"
        policies:
          wait-after: 2
          timeout: 1
"""


class PoliciesTest(base.EngineTestCase):
    def setUp(self):
        super(PoliciesTest, self).setUp()

        self.wb_spec = spec_parser.get_workbook_spec_from_yaml(WORKBOOK)
        self.wf_spec = self.wb_spec.get_workflows()['wf1']
        self.task_spec = self.wf_spec.get_tasks()['task1']

        thread_group = scheduler.setup()
        self.addCleanup(thread_group.stop)

    def test_build_policies(self):
        arr = policies.build_policies(
            self.task_spec.get_policies(),
            self.wf_spec
        )

        self.assertEqual(4, len(arr))
        p = self._assert_single_item(arr, delay=2)

        self.assertIsInstance(p, policies.WaitBeforePolicy)

        p = self._assert_single_item(arr, delay=5)

        self.assertIsInstance(p, policies.WaitAfterPolicy)

        p = self._assert_single_item(arr, delay=10)

        self.assertIsInstance(p, policies.RetryPolicy)
        self.assertEqual(5, p.count)
        self.assertEqual('$.my_val = 10', p.break_on)

        p = self._assert_single_item(arr, delay=7)

        self.assertIsInstance(p, policies.TimeoutPolicy)

    def test_build_policies_with_workflow_defaults(self):
        wb_spec = spec_parser.get_workbook_spec_from_yaml(WB_WITH_DEFAULTS)
        wf_spec = wb_spec.get_workflows()['wf1']
        task_spec = wf_spec.get_tasks()['task1']

        arr = policies.build_policies(task_spec.get_policies(), wf_spec)

        self.assertEqual(4, len(arr))

        p = self._assert_single_item(arr, delay=3)

        self.assertIsInstance(p, policies.WaitBeforePolicy)

        p = self._assert_single_item(arr, delay=5)

        self.assertIsInstance(p, policies.WaitAfterPolicy)

        p = self._assert_single_item(arr, delay=1)

        self.assertIsInstance(p, policies.RetryPolicy)
        self.assertEqual(2, p.count)

        p = self._assert_single_item(arr, delay=7)

        self.assertIsInstance(p, policies.TimeoutPolicy)

    def test_wait_before_policy(self):
        wb_service.create_workbook_v2({'definition': WAIT_BEFORE_WB})

        # Start workflow.
        exec_db = self.engine.start_workflow('wb.wf1', {})

        # Note: We need to reread execution to access related tasks.
        exec_db = db_api.get_execution(exec_db.id)
        task_db = exec_db.tasks[0]

        self.assertEqual(states.DELAYED, task_db.state)
        self.assertDictEqual(
            {'wait_before_policy': {'skip': True}},
            task_db.runtime_context
        )

        self._await(
            lambda: self.is_execution_success(exec_db.id),
        )

        exec_db = db_api.get_execution(exec_db.id)

        self.assertIsNotNone(exec_db)
        self.assertEqual(states.SUCCESS, exec_db.state)

    def test_wait_after_policy(self):
        wb_service.create_workbook_v2({'definition': WAIT_AFTER_WB})

        # Start workflow.
        exec_db = self.engine.start_workflow('wb.wf1', {})

        # Note: We need to reread execution to access related tasks.
        exec_db = db_api.get_execution(exec_db.id)
        task_db = exec_db.tasks[0]

        self.assertEqual(states.RUNNING, task_db.state)
        self.assertIsNone(task_db.runtime_context)

        self._await(
            lambda: self.is_task_delayed(task_db.id),
            delay=0.5
        )
        self._await(
            lambda: self.is_task_success(task_db.id),
        )

        exec_db = db_api.get_execution(exec_db.id)

        self.assertIsNotNone(exec_db)
        self.assertEqual(states.SUCCESS, exec_db.state)

    def test_retry_policy(self):
        wb_service.create_workbook_v2({'definition': RETRY_WB})

        # Start workflow.
        exec_db = self.engine.start_workflow('wb.wf1', {})

        # Note: We need to reread execution to access related tasks.
        exec_db = db_api.get_execution(exec_db.id)
        task_db = exec_db.tasks[0]

        self.assertEqual(states.RUNNING, task_db.state)
        self.assertIsNone(task_db.runtime_context)

        self._await(
            lambda: self.is_task_delayed(task_db.id),
            delay=0.5
        )
        self._await(
            lambda: self.is_task_error(task_db.id),
        )
        self._await(
            lambda: self.is_execution_error(exec_db.id),
        )

        exec_db = db_api.get_execution(exec_db.id)
        task_db = exec_db.tasks[0]

        self.assertEqual(
            1,
            task_db.runtime_context["retry_task_policy"]["retry_no"]
        )
        self.assertIsNotNone(exec_db)
        self.assertEqual(states.ERROR, exec_db.state)

    def test_timeout_policy(self):
        wb_service.create_workbook_v2({'definition': TIMEOUT_WB})

        # Start workflow.
        exec_db = self.engine.start_workflow('wb.wf1', {})

        # Note: We need to reread execution to access related tasks.
        exec_db = db_api.get_execution(exec_db.id)
        task_db = exec_db.tasks[0]

        self.assertEqual(states.RUNNING, task_db.state)

        self._await(
            lambda: self.is_task_error(task_db.id),
        )

        exec_db = db_api.get_execution(exec_db.id)
        task_db = exec_db.tasks[0]

        self.assertEqual(states.ERROR, task_db.state)
        self.assertIsNotNone(exec_db)

        self._await(
            lambda: self.is_execution_success(exec_db.id),
        )

        exec_db = db_api.get_execution(exec_db.id)
        self.assertEqual(states.SUCCESS, exec_db.state)

    def test_timeout_policy_success_after_timeout(self):
        wb_service.create_workbook_v2({'definition': TIMEOUT_WB2})

        # Start workflow.
        exec_db = self.engine.start_workflow('wb.wf1', {})

        # Note: We need to reread execution to access related tasks.
        exec_db = db_api.get_execution(exec_db.id)
        task_db = exec_db.tasks[0]

        self.assertEqual(states.RUNNING, task_db.state)

        self._await(
            lambda: self.is_execution_error(exec_db.id),
        )

        # Wait until timeout exceeds.
        self._sleep(2)

        exec_db = db_api.get_execution(exec_db.id)
        tasks_db = exec_db.tasks

        # Make sure that engine did not create extra tasks.
        self.assertEqual(1, len(tasks_db))
        self.assertEqual(states.ERROR, tasks_db[0].state)
