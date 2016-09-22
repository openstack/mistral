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
from oslo_config import cfg

from mistral.actions import std_actions
from mistral.db.v2 import api as db_api
from mistral.db.v2.sqlalchemy import models
from mistral.engine import policies
from mistral import exceptions as exc
from mistral.services import workbooks as wb_service
from mistral.services import workflows as wf_service
from mistral.tests.unit.engine import base
from mistral.workbook import parser as spec_parser
from mistral.workflow import states


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


WAIT_AFTER_FROM_VAR = """
---
version: '2.0'

name: wb

workflows:
  wf1:
    type: direct

    input:
      - wait_after
    tasks:
      task1:
        action: std.echo output="Hi!"
        wait-after: <% $.wait_after %>
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


RETRY_WB_FROM_VAR = """
---
version: '2.0'

name: wb

workflows:
  wf1:
    type: direct

    input:
      - count
      - delay

    tasks:
      task1:
        action: std.http url="http://some_non-existing_host"
        retry:
          count: <% $.count %>
          delay: <% $.delay %>
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
        action: std.async_noop
        timeout: 1
"""


TIMEOUT_FROM_VAR = """
---
version: '2.0'
name: wb
workflows:
  wf1:
    type: direct

    input:
      - timeout

    tasks:
      task1:
        action: std.async_noop
        timeout: <% $.timeout %>
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


PAUSE_BEFORE_DELAY_WB = """
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
        pause-before: true
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


CONCURRENCY_WB_FROM_VAR = """
---
version: '2.0'
name: wb
workflows:
  wf1:
    type: direct

    input:
      - concurrency

    tasks:
      task1:
        action: std.echo output="Hi!"
        concurrency: <% $.concurrency %>
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

        wf_ex = models.WorkflowExecution(
            id='1-2-3-4',
            context={},
            input={}
        )

        task_ex = models.TaskExecution(in_context={'int_var': 5})
        task_ex.workflow_execution = wf_ex

        policy.delay = "<% $.int_var %>"

        # Validation is ok.
        policy.before_task_start(task_ex, None)

        policy.delay = "some_string"

        # Validation is failing now.
        exception = self.assertRaises(
            exc.InvalidModelException,
            policy.before_task_start,
            task_ex,
            None
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

        self.assertEqual(states.RUNNING_DELAYED, task_ex.state)
        self.assertDictEqual(
            {'wait_before_policy': {'skip': True}},
            task_ex.runtime_context
        )

        self.await_workflow_success(wf_ex.id)

    def test_wait_before_policy_from_var(self):
        wb_service.create_workbook_v2(WAIT_BEFORE_FROM_VAR)

        # Start workflow.
        exec_db = self.engine.start_workflow('wb.wf1', {'wait_before': 1})

        # Note: We need to reread execution to access related tasks.
        exec_db = db_api.get_workflow_execution(exec_db.id)
        task_db = exec_db.task_executions[0]

        self.assertEqual(states.RUNNING_DELAYED, task_db.state)

        self.await_workflow_success(exec_db.id)

    def test_wait_before_policy_two_tasks(self):
        wf_text = """---
        version: '2.0'

        wf:
          tasks:
            a:
              wait-before: 2
              on-success: b
            b:
              action: std.noop

        """

        wf_service.create_workflows(wf_text)

        wf_ex = self.engine.start_workflow('wf', {})

        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
            task_execs = wf_ex.task_executions

        self.assertEqual(2, len(task_execs))

        self._assert_multiple_items(task_execs, 2, state=states.SUCCESS)

    def test_wait_after_policy(self):
        wb_service.create_workbook_v2(WAIT_AFTER_WB)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wb.wf1', {})

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)
        task_ex = wf_ex.task_executions[0]

        self.assertEqual(states.RUNNING, task_ex.state)
        self.assertDictEqual({}, task_ex.runtime_context)

        self.await_task_delayed(task_ex.id, delay=0.5)
        self.await_task_success(task_ex.id)

    def test_wait_after_policy_from_var(self):
        wb_service.create_workbook_v2(WAIT_AFTER_FROM_VAR)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wb.wf1', {'wait_after': 2})

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)
        task_ex = wf_ex.task_executions[0]

        self.assertEqual(states.RUNNING, task_ex.state)
        self.assertDictEqual({}, task_ex.runtime_context)

        # TODO(rakhmerov): This check doesn't make sense anymore because
        # we don't store evaluated value anywhere.
        # Need to create a better test.
        # self.assertEqual(2, task_ex.in_context['wait_after'])

    def test_retry_policy(self):
        wb_service.create_workbook_v2(RETRY_WB)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wb.wf1', {})

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)
        task_ex = wf_ex.task_executions[0]

        self.assertEqual(states.RUNNING, task_ex.state)
        self.assertDictEqual({}, task_ex.runtime_context)

        self.await_task_delayed(task_ex.id, delay=0.5)
        self.await_task_error(task_ex.id)

        self.await_workflow_error(wf_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)
        task_ex = wf_ex.task_executions[0]

        self.assertEqual(
            2,
            task_ex.runtime_context["retry_task_policy"]["retry_no"]
        )

    def test_retry_policy_from_var(self):
        wb_service.create_workbook_v2(RETRY_WB_FROM_VAR)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wb.wf1', {'count': 3, 'delay': 1})

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)
        task_ex = wf_ex.task_executions[0]

        self.assertEqual(states.RUNNING, task_ex.state)
        self.assertDictEqual({}, task_ex.runtime_context)

        # TODO(rakhmerov): This check doesn't make sense anymore because
        # we don't store evaluated values anywhere.
        # Need to create a better test.
        # self.assertEqual(3, task_ex.in_context["count"])
        # self.assertEqual(1, task_ex.in_context["delay"])

    def test_retry_policy_never_happen(self):
        retry_wb = """---
        version: '2.0'

        name: wb

        workflows:
          wf1:
            tasks:
              task1:
                action: std.echo output="hello"
                retry:
                  count: 3
                  delay: 1
        """
        wb_service.create_workbook_v2(retry_wb)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wb.wf1', {})

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)
        task_ex = wf_ex.task_executions[0]

        self.await_task_success(task_ex.id)

        self.await_workflow_success(wf_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)
        task_ex = wf_ex.task_executions[0]

        self.assertEqual(
            {},
            task_ex.runtime_context["retry_task_policy"]
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

        self.await_task_error(task_ex.id)

        self.await_workflow_error(wf_ex.id)

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

        self.await_task_error(task_ex.id)

        self.await_workflow_error(wf_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)
        task_ex = wf_ex.task_executions[0]

        self.assertEqual(
            2,
            task_ex.runtime_context['retry_task_policy']['retry_no']
        )

    @mock.patch.object(
        std_actions.EchoAction, 'run', mock.Mock(side_effect=[1, 2, 3, 4])
    )
    def test_retry_continue_on(self):
        retry_wb = """---
        version: '2.0'

        name: wb

        workflows:
          wf1:
            tasks:
              task1:
                action: std.echo output="mocked result"
                retry:
                  count: 4
                  delay: 1
                  continue-on: <% task(task1).result < 3 %>
        """
        wb_service.create_workbook_v2(retry_wb)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wb.wf1', {})

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)
        task_ex = wf_ex.task_executions[0]

        self.await_task_success(task_ex.id)

        self.await_workflow_success(wf_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)
        task_ex = wf_ex.task_executions[0]

        self.assertEqual(
            2,
            task_ex.runtime_context['retry_task_policy']['retry_no']
        )

    def test_retry_continue_on_not_happened(self):
        retry_wb = """---
        version: '2.0'

        name: wb

        workflows:
          wf1:
            tasks:
              task1:
                action: std.echo output=4
                retry:
                  count: 4
                  delay: 1
                  continue-on: <% task(task1).result <= 3 %>
        """
        wb_service.create_workbook_v2(retry_wb)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wb.wf1', {})

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)
        task_ex = wf_ex.task_executions[0]

        self.await_task_success(task_ex.id)

        self.await_workflow_success(wf_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)
        task_ex = wf_ex.task_executions[0]

        self.assertEqual(
            {},
            task_ex.runtime_context['retry_task_policy']
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

        self.await_task_error(task_ex.id)

        self.await_workflow_error(wf_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)
        task_ex = wf_ex.task_executions[0]

        self.assertEqual(
            2,
            task_ex.runtime_context['retry_task_policy']['retry_no']
        )

    def test_retry_policy_subworkflow_force_fail(self):
        retry_wb = """---
        version: '2.0'

        name: wb

        workflows:
          main:
            tasks:
              task1:
                workflow: work
                retry:
                  count: 3
                  delay: 1

          work:
            tasks:
              do:
                action: std.fail
                on-error:
                  - fail
        """
        wb_service.create_workbook_v2(retry_wb)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wb.main', {})

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)
        task_ex = wf_ex.task_executions[0]

        self.await_task_error(task_ex.id)
        self.await_workflow_error(wf_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)
        task_ex = wf_ex.task_executions[0]

        self.assertEqual(
            2,
            task_ex.runtime_context['retry_task_policy']['retry_no']
        )

    @mock.patch.object(
        std_actions.EchoAction,
        'run',
        mock.Mock(side_effect=[exc.ActionException(), "mocked result"])
    )
    def test_retry_policy_succeed_after_failure(self):
        retry_wb = """---
        version: '2.0'

        name: wb

        workflows:
          wf1:
            output:
              result: <% task(task1).result %>

            tasks:
              task1:
                action: std.echo output="mocked result"
                retry:
                  count: 3
                  delay: 1
        """
        wb_service.create_workbook_v2(retry_wb)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wb.wf1', {})

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)
        task_ex = wf_ex.task_executions[0]

        self.await_task_success(task_ex.id)

        self.await_workflow_success(wf_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)
        task_ex = wf_ex.task_executions[0]

        self.assertDictEqual(
            {'retry_no': 1},
            task_ex.runtime_context['retry_task_policy']
        )

        self.assertDictEqual({'result': 'mocked result'}, wf_ex.output)

    def test_timeout_policy(self):
        wb_service.create_workbook_v2(TIMEOUT_WB)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wb.wf1', {})

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)
        task_ex = wf_ex.task_executions[0]

        self.assertEqual(states.RUNNING, task_ex.state)

        self.await_task_error(task_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self._assert_single_item(wf_ex.task_executions, name='task1')

        self.await_workflow_success(wf_ex.id)

    def test_timeout_policy_success_after_timeout(self):
        wb_service.create_workbook_v2(TIMEOUT_WB2)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wb.wf1', {})

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)
        task_ex = wf_ex.task_executions[0]

        self.assertEqual(states.RUNNING, task_ex.state)

        self.await_workflow_error(wf_ex.id)

        # Wait until timeout exceeds.
        self._sleep(1)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)
        tasks_db = wf_ex.task_executions

        # Make sure that engine did not create extra tasks.
        self.assertEqual(1, len(tasks_db))

    def test_timeout_policy_from_var(self):
        wb_service.create_workbook_v2(TIMEOUT_FROM_VAR)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wb.wf1', {'timeout': 1})

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)
        task_ex = wf_ex.task_executions[0]

        self.assertEqual(states.RUNNING, task_ex.state)

        # TODO(rakhmerov): This check doesn't make sense anymore because
        # we don't store evaluated 'timeout' value anywhere.
        # Need to create a better test.
        # self.assertEqual(1, task_ex.in_context['timeout'])

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

        self.await_workflow_paused(wf_ex.id)

        self._sleep(1)

        self.engine.resume_workflow(wf_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)
        self._assert_single_item(wf_ex.task_executions, name='task1')

        self.await_workflow_success(wf_ex.id)

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

    def test_pause_before_with_delay_policy(self):
        wb_service.create_workbook_v2(PAUSE_BEFORE_DELAY_WB)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wb.wf1', {})

        wf_ex = db_api.get_workflow_execution(wf_ex.id)
        task_ex = self._assert_single_item(
            wf_ex.task_executions,
            name='task1'
        )

        self.assertEqual(states.IDLE, task_ex.state)

        # Verify wf paused by pause-before
        self.await_workflow_paused(wf_ex.id)

        # Allow wait-before to expire
        self._sleep(2)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        # Verify wf still paused (wait-before didn't reactivate)
        self.await_workflow_paused(wf_ex.id)

        task_ex = db_api.get_task_execution(task_ex.id)
        self.assertEqual(states.IDLE, task_ex.state)

        self.engine.resume_workflow(wf_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)
        self._assert_single_item(wf_ex.task_executions, name='task1')

        self.await_workflow_success(wf_ex.id)

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

        self.await_workflow_success(wf_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)
        task_ex = self._assert_single_item(
            wf_ex.task_executions,
            name='task1'
        )

        self.assertEqual(states.SUCCESS, task_ex.state)

        self.assertEqual(4, task_ex.runtime_context['concurrency'])

    def test_concurrency_is_in_runtime_context_from_var(self):
        wb_service.create_workbook_v2(CONCURRENCY_WB_FROM_VAR)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wb.wf1', {'concurrency': 4})

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        task_ex = self._assert_single_item(
            wf_ex.task_executions,
            name='task1'
        )

        self.assertEqual(4, task_ex.runtime_context['concurrency'])

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
        wf_ex = self.engine.start_workflow('wb.wf1', {'wait_before': '1'})

        self.assertIn(
            'Invalid data type in WaitBeforePolicy',
            wf_ex.state_info
        )
        self.assertEqual(states.ERROR, wf_ex.state)

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

        self.await_workflow_success(wf_ex.id)

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(2, len(wf_ex.task_executions))
