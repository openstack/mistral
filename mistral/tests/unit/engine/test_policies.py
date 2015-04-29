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
from mistral.engine import policies
from mistral import exceptions as exc
from mistral.openstack.common import log as logging
from mistral.services import workbooks as wb_service
from mistral.services import workflows as wf_service
from mistral.tests.unit.engine import base
from mistral.workbook import parser as spec_parser
from mistral.workflow import states

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
        wait-before: 2
        wait-after: 5
        timeout: 7
        retry:
          count: 5
          delay: 10
          break-on: <% $.my_val = 10 %>
"""


WB_WITH_DEFAULTS = """
---
version: '2.0'

name: wb

workflows:
  wf1:
    type: direct

    task-defaults:
      wait-before: 2
      retry:
        count: 2
        delay: 1

    tasks:
      task1:
        action: std.echo output="Hi!"
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
        wait-before: 1
"""


WAIT_BEFORE_FROM_VAR = """
---
version: '2.0'

name: wb

workflows:
  wf1:
    type: direct

    input:
      - wait_before

    tasks:
      task1:
        action: std.echo output="Hi!"
        wait-before: <% $.wait_before %>
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
        retry:
          count: 3
          delay: 1
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
        action: std.async_noop
        timeout: 2
        on-error:
          - task2

      task2:
        action: std.echo output="Hi!"
        timeout: 3
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
        wait-after: 4
        timeout: 3
"""


PAUSE_BEFORE_WB = """
---
version: '2.0'
name: wb
workflows:
  wf1:
    type: direct

    tasks:
      task1:
        action: std.echo output="Hi!"
        pause-before: True
        on-success:
          - task2
      task2:
        action: std.echo output="Bye!"
"""


CONCURRENCY_WB = """
---
version: '2.0'
name: wb
workflows:
  wf1:
    type: direct

    tasks:
      task1:
        action: std.echo output="Hi!"
        concurrency: 4
"""


class PoliciesTest(base.EngineTestCase):
    def setUp(self):
        super(PoliciesTest, self).setUp()

        self.wb_spec = spec_parser.get_workbook_spec_from_yaml(WORKBOOK)
        self.wf_spec = self.wb_spec.get_workflows()['wf1']
        self.task_spec = self.wf_spec.get_tasks()['task1']

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
        self.assertEqual('<% $.my_val = 10 %>', p.break_on)

        p = self._assert_single_item(arr, delay=7)

        self.assertIsInstance(p, policies.TimeoutPolicy)

    def test_task_policy_class(self):
        policy = policies.base.TaskPolicy()

        policy._schema = {
            "properties": {
                "delay": {"type": "integer"}
            }
        }
        task_db = type('Task', (object,), {'in_context': {'int_var': 5}})
        policy.delay = "<% $.int_var %>"

        # Validation is ok.
        policy.before_task_start(task_db, None)

        policy.delay = "some_string"

        # Validation is failing now.
        exception = self.assertRaises(
            exc.InvalidModelException,
            policy.before_task_start, task_db, None
        )

        self.assertIn("Invalid data type in TaskPolicy", str(exception))

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
        wb_service.create_workbook_v2(WAIT_BEFORE_WB)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wb.wf1', {})

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)
        task_ex = wf_ex.task_executions[0]

        self.assertEqual(states.DELAYED, task_ex.state)
        self.assertDictEqual(
            {'wait_before_policy': {'skip': True}},
            task_ex.runtime_context
        )

        self._await(lambda: self.is_execution_success(wf_ex.id))

    def test_wait_before_policy_from_var(self):
        wb_service.create_workbook_v2(WAIT_BEFORE_FROM_VAR)

        # Start workflow.
        exec_db = self.engine.start_workflow('wb.wf1', {'wait_before': 1})

        # Note: We need to reread execution to access related tasks.
        exec_db = db_api.get_execution(exec_db.id)
        task_db = exec_db.task_executions[0]

        self.assertEqual(states.DELAYED, task_db.state)

        self._await(lambda: self.is_execution_success(exec_db.id))

    def test_wait_after_policy(self):
        wb_service.create_workbook_v2(WAIT_AFTER_WB)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wb.wf1', {})

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)
        task_ex = wf_ex.task_executions[0]

        self.assertEqual(states.RUNNING, task_ex.state)
        self.assertDictEqual({}, task_ex.runtime_context)

        self._await(
            lambda: self.is_task_delayed(task_ex.id),
            delay=0.5
        )
        self._await(lambda: self.is_task_success(task_ex.id))

    def test_retry_policy(self):
        wb_service.create_workbook_v2(RETRY_WB)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wb.wf1', {})

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)
        task_ex = wf_ex.task_executions[0]

        self.assertEqual(states.RUNNING, task_ex.state)
        self.assertDictEqual({}, task_ex.runtime_context)

        self._await(
            lambda: self.is_task_delayed(task_ex.id),
            delay=0.5
        )
        self._await(lambda: self.is_task_error(task_ex.id))

        self._await(lambda: self.is_execution_error(wf_ex.id))

        wf_ex = db_api.get_workflow_execution(wf_ex.id)
        task_ex = wf_ex.task_executions[0]

        self.assertEqual(
            2,
            task_ex.runtime_context["retry_task_policy"]["retry_no"]
        )

    def test_retry_policy_break_on(self):
        retry_wb = """---
        version: '2.0'

        name: wb

        workflows:
          wf1:
            input:
              - var: 4
            tasks:
              task1:
                action: std.fail
                retry:
                  count: 3
                  delay: 1
                  break-on: <% $.var >= 3 %>
        """
        wb_service.create_workbook_v2(retry_wb)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wb.wf1', {})

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)
        task_ex = wf_ex.task_executions[0]

        self._await(lambda: self.is_task_error(task_ex.id))

        self._await(lambda: self.is_execution_error(wf_ex.id))

        wf_ex = db_api.get_workflow_execution(wf_ex.id)
        task_ex = wf_ex.task_executions[0]

        self.assertEqual(
            {},
            task_ex.runtime_context["retry_task_policy"]
        )

    def test_retry_policy_break_on_not_happened(self):
        retry_wb = """---
        version: '2.0'

        name: wb

        workflows:
          wf1:
            input:
              - var: 2
            tasks:
              task1:
                action: std.fail
                retry:
                  count: 3
                  delay: 1
                  break-on: <% $.var >= 3 %>
        """
        wb_service.create_workbook_v2(retry_wb)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wb.wf1', {})

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)
        task_ex = wf_ex.task_executions[0]

        self._await(lambda: self.is_task_error(task_ex.id))

        self._await(lambda: self.is_execution_error(wf_ex.id))

        wf_ex = db_api.get_workflow_execution(wf_ex.id)
        task_ex = wf_ex.task_executions[0]

        self.assertEqual(
            2,
            task_ex.runtime_context['retry_task_policy']['retry_no']
        )

    def test_retry_policy_one_line(self):
        retry_wb = """---
        version: '2.0'

        name: wb

        workflows:
          wf1:
            type: direct

            tasks:
              task1:
                action: std.fail
                retry: count=3 delay=1
        """
        wb_service.create_workbook_v2(retry_wb)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wb.wf1', {})

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)
        task_ex = wf_ex.task_executions[0]

        self._await(lambda: self.is_task_error(task_ex.id))

        self._await(lambda: self.is_execution_error(wf_ex.id))

        wf_ex = db_api.get_workflow_execution(wf_ex.id)
        task_ex = wf_ex.task_executions[0]

        self.assertEqual(
            2,
            task_ex.runtime_context['retry_task_policy']['retry_no']
        )

    def test_timeout_policy(self):
        wb_service.create_workbook_v2(TIMEOUT_WB)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wb.wf1', {})

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)
        task_ex = wf_ex.task_executions[0]

        self.assertEqual(states.RUNNING, task_ex.state)

        self._await(lambda: self.is_task_error(task_ex.id))

        wf_ex = db_api.get_workflow_execution(wf_ex.id)
        task_ex = self._assert_single_item(
            wf_ex.task_executions,
            name='task1'
        )

        self._await(lambda: self.is_execution_success(wf_ex.id))

    def test_timeout_policy_success_after_timeout(self):
        wb_service.create_workbook_v2(TIMEOUT_WB2)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wb.wf1', {})

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)
        task_ex = wf_ex.task_executions[0]

        self.assertEqual(states.RUNNING, task_ex.state)

        self._await(lambda: self.is_execution_error(wf_ex.id))

        # Wait until timeout exceeds.
        self._sleep(2)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)
        tasks_db = wf_ex.task_executions

        # Make sure that engine did not create extra tasks.
        self.assertEqual(1, len(tasks_db))

    def test_pause_before_policy(self):
        wb_service.create_workbook_v2(PAUSE_BEFORE_WB)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wb.wf1', {})

        wf_ex = db_api.get_workflow_execution(wf_ex.id)
        task_ex = self._assert_single_item(
            wf_ex.task_executions,
            name='task1'
        )

        self.assertEqual(states.IDLE, task_ex.state)

        self._await(lambda: self.is_execution_paused(wf_ex.id))
        self._sleep(1)
        self.engine.resume_workflow(wf_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)
        self._assert_single_item(wf_ex.task_executions, name='task1')

        self._await(lambda: self.is_execution_success(wf_ex.id))

        wf_ex = db_api.get_workflow_execution(wf_ex.id)
        task_ex = self._assert_single_item(
            wf_ex.task_executions,
            name='task1'
        )
        next_task_ex = self._assert_single_item(
            wf_ex.task_executions,
            name='task2'
        )

        self.assertEqual(states.SUCCESS, task_ex.state)
        self.assertEqual(states.SUCCESS, next_task_ex.state)

    def test_concurrency_is_in_runtime_context(self):
        wb_service.create_workbook_v2(CONCURRENCY_WB)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wb.wf1', {})

        self._await(lambda: self.is_execution_success(wf_ex.id))

        wf_ex = db_api.get_workflow_execution(wf_ex.id)
        task_ex = self._assert_single_item(
            wf_ex.task_executions,
            name='task1'
        )

        self.assertEqual(states.SUCCESS, task_ex.state)

        runtime_context = task_ex.runtime_context

        self.assertEqual(4, runtime_context['concurrency'])

    def test_wrong_policy_prop_type(self):
        wb = """---
        version: "2.0"
        name: wb
        workflows:
          wf1:
            type: direct
            input:
              - wait_before
            tasks:
              task1:
                action: std.echo output="Hi!"
                wait-before: <% $.wait_before %>
        """
        wb_service.create_workbook_v2(wb)

        # Start workflow.
        exception = self.assertRaises(
            exc.InvalidModelException,
            self.engine.start_workflow,
            'wb.wf1', {'wait_before': '1'}
        )

        self.assertIn('Invalid data type in WaitBeforePolicy', str(exception))

    def test_delayed_task_and_correct_finish_workflow(self):
        wf_delayed_state = """---
        version: "2.0"
        wf:
          type: direct
          tasks:

            task1:
              action: std.noop
              wait-before: 1

            task2:
              action: std.noop
        """
        wf_service.create_workflows(wf_delayed_state)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wf', {})

        self._await(lambda: self.is_execution_success(wf_ex.id))

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_execution(wf_ex.id)

        self.assertEqual(2, len(wf_ex.task_executions))
