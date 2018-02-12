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

from eventlet import timeout
import mock
from oslo_config import cfg
import requests

from mistral.actions import std_actions
from mistral.db.v2 import api as db_api
from mistral.db.v2.sqlalchemy import models
from mistral.engine import policies
from mistral import exceptions as exc
from mistral.lang import parser as spec_parser
from mistral.services import workbooks as wb_service
from mistral.services import workflows as wf_service
from mistral.tests.unit.engine import base
from mistral.workflow import states
from mistral_lib.actions import types


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
        wait-before: %d
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
        wait-after: %d
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
          count: %(count)d
          delay: %(delay)d
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
        timeout: %d
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
        concurrency: %d
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
        self.assertEqual('<% $.my_val = 10 %>', p._break_on_clause)

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
        wb_service.create_workbook_v2(WAIT_BEFORE_WB % 1)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wb.wf1')

        with db_api.transaction():
            # Note: We need to reread execution to access related tasks.
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_ex = wf_ex.task_executions[0]

        self.assertEqual(states.RUNNING_DELAYED, task_ex.state)
        self.assertDictEqual(
            {'wait_before_policy': {'skip': True}},
            task_ex.runtime_context
        )

        self.await_workflow_success(wf_ex.id)

    def test_wait_before_policy_zero_seconds(self):
        wb_service.create_workbook_v2(WAIT_BEFORE_WB % 0)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wb.wf1')

        with db_api.transaction():
            # Note: We need to reread execution to access related tasks.
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_ex = wf_ex.task_executions[0]

        self.assertEqual(states.RUNNING, task_ex.state)

        self.await_workflow_success(wf_ex.id)

    def test_wait_before_policy_negative_number(self):
        self.assertRaises(
            exc.InvalidModelException,
            wb_service.create_workbook_v2,
            WAIT_BEFORE_WB % -1
        )

    def test_wait_before_policy_from_var(self):
        wb_service.create_workbook_v2(WAIT_BEFORE_FROM_VAR)

        # Start workflow.
        wf_ex = self.engine.start_workflow(
            'wb.wf1',
            wf_input={'wait_before': 1}
        )

        with db_api.transaction():
            # Note: We need to reread execution to access related tasks.
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_ex = wf_ex.task_executions[0]

        self.assertEqual(states.RUNNING_DELAYED, task_ex.state)

        self.await_workflow_success(wf_ex.id)

    def test_wait_before_policy_from_var_zero_seconds(self):
        wb_service.create_workbook_v2(WAIT_BEFORE_FROM_VAR)

        # Start workflow.
        wf_ex = self.engine.start_workflow(
            'wb.wf1',
            wf_input={'wait_before': 0}
        )

        with db_api.transaction():
            # Note: We need to reread execution to access related tasks.
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_ex = wf_ex.task_executions[0]

        # If wait_before is 0 start the task immediately without delay.
        self.assertEqual(states.RUNNING, task_ex.state)

        self.await_workflow_success(wf_ex.id)

    def test_wait_before_policy_from_var_negative_number(self):
        wb_service.create_workbook_v2(WAIT_BEFORE_FROM_VAR)

        # Start workflow.
        wf_ex = self.engine.start_workflow(
            'wb.wf1',
            wf_input={'wait_before': -1}
        )

        with db_api.transaction():
            # Note: We need to reread execution to access related tasks.
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_ex = wf_ex.task_executions[0]

        # If wait_before value is less than 0 the task should fail with
        # InvalidModelException.
        self.assertEqual(states.ERROR, task_ex.state)

        self.await_workflow_error(wf_ex.id)

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

        wf_ex = self.engine.start_workflow('wf')

        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_execs = wf_ex.task_executions

        self.assertEqual(2, len(task_execs))

        self._assert_multiple_items(task_execs, 2, state=states.SUCCESS)

    def test_wait_after_policy(self):
        wb_service.create_workbook_v2(WAIT_AFTER_WB % 2)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wb.wf1')

        with db_api.transaction():
            # Note: We need to reread execution to access related tasks.
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_ex = wf_ex.task_executions[0]

        self.assertEqual(states.RUNNING, task_ex.state)
        self.assertDictEqual({}, task_ex.runtime_context)

        self.await_task_delayed(task_ex.id, delay=0.5)
        self.await_task_success(task_ex.id)

    def test_wait_after_policy_zero_seconds(self):
        wb_service.create_workbook_v2(WAIT_AFTER_WB % 0)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wb.wf1')

        with db_api.transaction():
            # Note: We need to reread execution to access related tasks.
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_ex = wf_ex.task_executions[0]

        self.assertEqual(states.RUNNING, task_ex.state)
        self.assertDictEqual({}, task_ex.runtime_context)

        try:
            self.await_task_delayed(task_ex.id, delay=0.5)
        except AssertionError:
            # There was no delay as expected.
            pass
        else:
            self.fail("Shouldn't happen")
        self.await_task_success(task_ex.id)

    def test_wait_after_policy_negative_number(self):
        self.assertRaises(
            exc.InvalidModelException,
            wb_service.create_workbook_v2,
            WAIT_AFTER_WB % -1
        )

    def test_wait_after_policy_from_var(self):
        wb_service.create_workbook_v2(WAIT_AFTER_FROM_VAR)

        # Start workflow.
        wf_ex = self.engine.start_workflow(
            'wb.wf1',
            wf_input={'wait_after': 2}
        )

        with db_api.transaction():
            # Note: We need to reread execution to access related tasks.
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_ex = wf_ex.task_executions[0]

        self.assertEqual(states.RUNNING, task_ex.state)
        self.assertDictEqual({}, task_ex.runtime_context)

        self.await_task_delayed(task_ex.id, delay=0.5)
        self.await_task_success(task_ex.id)

    def test_wait_after_policy_from_var_zero_seconds(self):
        wb_service.create_workbook_v2(WAIT_AFTER_FROM_VAR)

        # Start workflow.
        wf_ex = self.engine.start_workflow(
            'wb.wf1',
            wf_input={'wait_after': 0}
        )

        with db_api.transaction():
            # Note: We need to reread execution to access related tasks.
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_ex = wf_ex.task_executions[0]

        self.assertEqual(states.RUNNING, task_ex.state)
        self.assertDictEqual({}, task_ex.runtime_context)

        try:
            self.await_task_delayed(task_ex.id, delay=0.5)
        except AssertionError:
            # There was no delay as expected.
            pass
        else:
            self.fail("Shouldn't happen")
        self.await_task_success(task_ex.id)

    def test_wait_after_policy_from_var_negative_number(self):
        wb_service.create_workbook_v2(WAIT_AFTER_FROM_VAR)

        # Start workflow.
        wf_ex = self.engine.start_workflow(
            'wb.wf1',
            wf_input={'wait_after': -1}
        )

        with db_api.transaction():
            # Note: We need to reread execution to access related tasks.
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_ex = wf_ex.task_executions[0]

        # If wait_after value is less than 0 the task should fail with
        # InvalidModelException.
        self.assertEqual(states.ERROR, task_ex.state)

        self.await_workflow_error(wf_ex.id)

        self.assertDictEqual({}, task_ex.runtime_context)

    @mock.patch.object(
        requests,
        'request',
        mock.MagicMock(side_effect=Exception())
    )
    def test_retry_policy(self):
        wb_service.create_workbook_v2(RETRY_WB % {'count': 3, 'delay': 1})

        # Start workflow.
        wf_ex = self.engine.start_workflow('wb.wf1')

        with db_api.transaction():
            # Note: We need to reread execution to access related tasks.
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_ex = wf_ex.task_executions[0]

        self.assertEqual(states.RUNNING, task_ex.state)
        self.assertDictEqual({}, task_ex.runtime_context)

        self.await_task_delayed(task_ex.id, delay=0.5)
        self.await_task_error(task_ex.id)

        self.await_workflow_error(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_ex = wf_ex.task_executions[0]

        self.assertEqual(
            3,
            task_ex.runtime_context["retry_task_policy"]["retry_no"]
        )

    @mock.patch.object(
        requests,
        'request',
        mock.MagicMock(side_effect=Exception())
    )
    def test_retry_policy_zero_count(self):
        wb_service.create_workbook_v2(RETRY_WB % {'count': 0, 'delay': 1})

        # Start workflow.
        wf_ex = self.engine.start_workflow('wb.wf1')

        with db_api.transaction():
            # Note: We need to reread execution to access related tasks.
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_ex = wf_ex.task_executions[0]

        self.assertEqual(states.RUNNING, task_ex.state)
        self.assertDictEqual({}, task_ex.runtime_context)

        try:
            self.await_task_delayed(task_ex.id, delay=0.5)
        except AssertionError:
            # There were no scheduled tasks as expected.
            pass
        else:
            self.fail("Shouldn't happen")

        self.await_task_error(task_ex.id)

        self.await_workflow_error(wf_ex.id)

        self.assertNotIn("retry_task_policy", task_ex.runtime_context)

    @mock.patch.object(
        requests,
        'request',
        mock.MagicMock(side_effect=Exception())
    )
    def test_retry_policy_negative_numbers(self):
        # Negative delay is not accepted.
        self.assertRaises(
            exc.InvalidModelException,
            wb_service.create_workbook_v2,
            RETRY_WB % {'count': 1, 'delay': -1}
        )

        # Negative count is not accepted.
        self.assertRaises(
            exc.InvalidModelException,
            wb_service.create_workbook_v2,
            RETRY_WB % {'count': -1, 'delay': 1}
        )

    @mock.patch.object(
        requests,
        'request',
        mock.MagicMock(side_effect=Exception())
    )
    def test_retry_policy_from_var(self):
        wb_service.create_workbook_v2(RETRY_WB_FROM_VAR)

        # Start workflow.
        wf_ex = self.engine.start_workflow(
            'wb.wf1',
            wf_input={'count': 3, 'delay': 1}
        )

        with db_api.transaction():
            # Note: We need to reread execution to access related tasks.
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_ex = wf_ex.task_executions[0]

        self.assertEqual(states.RUNNING, task_ex.state)
        self.assertDictEqual({}, task_ex.runtime_context)

        self.await_task_delayed(task_ex.id, delay=0.5)
        self.await_task_error(task_ex.id)

        self.await_workflow_error(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_ex = wf_ex.task_executions[0]

        self.assertEqual(
            3,
            task_ex.runtime_context["retry_task_policy"]["retry_no"]
        )

    @mock.patch.object(
        requests,
        'request',
        mock.MagicMock(side_effect=Exception())
    )
    def test_retry_policy_from_var_zero_iterations(self):
        wb_service.create_workbook_v2(RETRY_WB_FROM_VAR)

        # Start workflow.
        wf_ex = self.engine.start_workflow(
            'wb.wf1',
            wf_input={'count': 0, 'delay': 1}
        )

        with db_api.transaction():
            # Note: We need to reread execution to access related tasks.
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_ex = wf_ex.task_executions[0]

        self.assertEqual(states.RUNNING, task_ex.state)
        self.assertDictEqual({}, task_ex.runtime_context)

        try:
            self.await_task_delayed(task_ex.id, delay=0.5)
        except AssertionError:
            # There were no scheduled tasks as expected.
            pass
        else:
            self.fail("Shouldn't happen")

        self.await_task_error(task_ex.id)

        self.await_workflow_error(wf_ex.id)

        self.assertNotIn("retry_task_policy", task_ex.runtime_context)

    @mock.patch.object(
        requests,
        'request',
        mock.MagicMock(side_effect=Exception())
    )
    def test_retry_policy_from_var_negative_numbers(self):
        wb_service.create_workbook_v2(RETRY_WB_FROM_VAR)

        # Start workflow with negative count.
        wf_ex = self.engine.start_workflow(
            'wb.wf1',
            wf_input={'count': -1, 'delay': 1}
        )

        with db_api.transaction():
            # Note: We need to reread execution to access related tasks.
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_ex = wf_ex.task_executions[0]

        self.assertEqual(states.ERROR, task_ex.state)
        self.assertDictEqual({}, task_ex.runtime_context)

        self.await_workflow_error(wf_ex.id)

        # Start workflow with negative delay.
        wf_ex = self.engine.start_workflow(
            'wb.wf1',
            wf_input={'count': 1, 'delay': -1}
        )

        with db_api.transaction():
            # Note: We need to reread execution to access related tasks.
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_ex = wf_ex.task_executions[0]

        self.assertEqual(states.ERROR, task_ex.state)
        self.assertDictEqual({}, task_ex.runtime_context)

        self.await_workflow_error(wf_ex.id)

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
        wf_ex = self.engine.start_workflow('wb.wf1')

        with db_api.transaction():
            # Note: We need to reread execution to access related tasks.
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_ex = wf_ex.task_executions[0]

        self.await_task_success(task_ex.id)

        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
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
        wf_ex = self.engine.start_workflow('wb.wf1')

        with db_api.transaction():
            # Note: We need to reread execution to access related tasks.
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_ex = wf_ex.task_executions[0]

        self.await_task_error(task_ex.id)

        self.await_workflow_error(wf_ex.id)

        with db_api.transaction():
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
        wf_ex = self.engine.start_workflow('wb.wf1')

        with db_api.transaction():
            # Note: We need to reread execution to access related tasks.
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_ex = wf_ex.task_executions[0]

        self.await_task_error(task_ex.id)

        self.await_workflow_error(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_ex = wf_ex.task_executions[0]

        self.assertEqual(
            3,
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
        wf_ex = self.engine.start_workflow('wb.wf1')

        with db_api.transaction():
            # Note: We need to reread execution to access related tasks.
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_ex = wf_ex.task_executions[0]

        self.await_task_success(task_ex.id)

        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
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
        wf_ex = self.engine.start_workflow('wb.wf1')

        with db_api.transaction():
            # Note: We need to reread execution to access related tasks.
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_ex = wf_ex.task_executions[0]

        self.await_task_success(task_ex.id)
        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
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
        wf_ex = self.engine.start_workflow('wb.wf1')

        with db_api.transaction():
            # Note: We need to reread execution to access related tasks.
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_ex = wf_ex.task_executions[0]

        self.await_task_error(task_ex.id)
        self.await_workflow_error(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_ex = wf_ex.task_executions[0]

        self.assertEqual(
            3,
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
        wf_ex = self.engine.start_workflow('wb.main')

        with db_api.transaction():
            # Note: We need to reread execution to access related tasks.
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_ex = wf_ex.task_executions[0]

        self.await_task_error(task_ex.id)
        self.await_workflow_error(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
            task_ex = wf_ex.task_executions[0]

        self.assertEqual(
            3,
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
        wf_ex = self.engine.start_workflow('wb.wf1')

        with db_api.transaction():
            # Note: We need to reread execution to access related tasks.
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_ex = wf_ex.task_executions[0]

        self.await_task_success(task_ex.id)
        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            wf_output = wf_ex.output
            task_ex = wf_ex.task_executions[0]

        self.assertDictEqual(
            {'retry_no': 1},
            task_ex.runtime_context['retry_task_policy']
        )

        self.assertDictEqual({'result': 'mocked result'}, wf_output)

    @mock.patch.object(
        std_actions.EchoAction,
        'run',
        mock.MagicMock(side_effect=[exc.ActionException(), 'value'])
    )
    def test_retry_policy_succeed_after_failure_with_publish(self):
        retry_wf = """---
        version: '2.0'

        wf1:
            output:
              result: <% task(task2).result %>

            tasks:
              task1:
                action: std.noop
                publish:
                  key: value
                on-success:
                  - task2

              task2:
                action: std.echo output=<% $.key %>
                retry:
                  count: 3
                  delay: 1
        """

        wf_service.create_workflows(retry_wf)
        wf_ex = self.engine.start_workflow('wf1')

        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            wf_output = wf_ex.output
            task_execs = wf_ex.task_executions

        retry_task = self._assert_single_item(task_execs, name='task2')

        self.assertDictEqual(
            {'retry_no': 1},
            retry_task.runtime_context['retry_task_policy']
        )

        self.assertDictEqual({'result': 'value'}, wf_output)

    def test_timeout_policy(self):
        wb_service.create_workbook_v2(TIMEOUT_WB % 2)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wb.wf1')

        with db_api.transaction():
            # Note: We need to reread execution to access related tasks.
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_ex = wf_ex.task_executions[0]

        self.assertEqual(states.RUNNING, task_ex.state)

        self.await_task_error(task_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_execs = wf_ex.task_executions

        self._assert_single_item(task_execs, name='task1')

        self.await_workflow_success(wf_ex.id)

    def test_timeout_policy_zero_seconds(self):
        wb = """---
        version: '2.0'

        name: wb

        workflows:
          wf1:
            type: direct

            tasks:
              task1:
                action: std.echo output="Hi!"
                timeout: 0
        """
        wb_service.create_workbook_v2(wb)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wb.wf1')

        with db_api.transaction():
            # Note: We need to reread execution to access related tasks.
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_ex = wf_ex.task_executions[0]

        self.assertEqual(states.RUNNING, task_ex.state)

        self.await_task_success(task_ex.id)

        self.await_workflow_success(wf_ex.id)

    def test_timeout_policy_negative_number(self):
        # Negative timeout is not accepted.
        self.assertRaises(
            exc.InvalidModelException,
            wb_service.create_workbook_v2,
            TIMEOUT_WB % -1
        )

    def test_timeout_policy_success_after_timeout(self):
        wb_service.create_workbook_v2(TIMEOUT_WB2)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wb.wf1')

        with db_api.transaction():
            # Note: We need to reread execution to access related tasks.
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_ex = wf_ex.task_executions[0]

        self.assertEqual(states.RUNNING, task_ex.state)

        self.await_task_error(task_ex.id)

        self.await_workflow_error(wf_ex.id)

        # Wait until timeout exceeds.
        self._sleep(1)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_execs = wf_ex.task_executions

        # Make sure that engine did not create extra tasks.
        self.assertEqual(1, len(task_execs))

    def test_timeout_policy_from_var(self):
        wb_service.create_workbook_v2(TIMEOUT_FROM_VAR)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wb.wf1', wf_input={'timeout': 1})

        with db_api.transaction():
            # Note: We need to reread execution to access related tasks.
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_ex = wf_ex.task_executions[0]

        self.assertEqual(states.RUNNING, task_ex.state)

        self.await_task_error(task_ex.id)

        self.await_workflow_error(wf_ex.id)

    def test_timeout_policy_from_var_zero_seconds(self):
        wb = """---
        version: '2.0'

        name: wb

        workflows:
          wf1:
            type: direct

            input:
              - timeout

            tasks:
              task1:
                action: std.echo output="Hi!"
                timeout: <% $.timeout %>
        """

        wb_service.create_workbook_v2(wb)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wb.wf1', wf_input={'timeout': 0})

        with db_api.transaction():
            # Note: We need to reread execution to access related tasks.
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_ex = wf_ex.task_executions[0]

        self.assertEqual(states.RUNNING, task_ex.state)

        self.await_task_success(task_ex.id)

        self.await_workflow_success(wf_ex.id)

    def test_timeout_policy_from_var_negative_number(self):
        wb_service.create_workbook_v2(TIMEOUT_FROM_VAR)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wb.wf1', wf_input={'timeout': -1})

        with db_api.transaction():
            # Note: We need to reread execution to access related tasks.
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_ex = wf_ex.task_executions[0]

        self.assertEqual(states.ERROR, task_ex.state)

        self.await_workflow_error(wf_ex.id)

    def test_action_timeout(self):
        wf_text = """---
        version: '2.0'
        wf1:
          tasks:
            task1:
              action: std.sleep seconds=10
              timeout: 2
        """

        wf_service.create_workflows(wf_text)
        wf_ex = self.engine.start_workflow('wf1')

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
            task_ex = wf_ex.task_executions[0]
            action_ex = task_ex.action_executions[0]

        with timeout.Timeout(8):
            self.await_workflow_error(wf_ex.id)
            self.await_task_error(task_ex.id)
            self.await_action_error(action_ex.id)

    def test_pause_before_policy(self):
        wb_service.create_workbook_v2(PAUSE_BEFORE_WB)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wb.wf1')

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_execs = wf_ex.task_executions

        task_ex = self._assert_single_item(task_execs, name='task1')

        self.assertEqual(states.IDLE, task_ex.state)

        self.await_workflow_paused(wf_ex.id)

        self._sleep(1)

        self.engine.resume_workflow(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_execs = wf_ex.task_executions

        self._assert_single_item(task_execs, name='task1')

        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_execs = wf_ex.task_executions

        task_ex = self._assert_single_item(task_execs, name='task1')
        next_task_ex = self._assert_single_item(task_execs, name='task2')

        self.assertEqual(states.SUCCESS, task_ex.state)
        self.assertEqual(states.SUCCESS, next_task_ex.state)

    def test_pause_before_with_delay_policy(self):
        wb_service.create_workbook_v2(PAUSE_BEFORE_DELAY_WB)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wb.wf1')

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_execs = wf_ex.task_executions

        task_ex = self._assert_single_item(task_execs, name='task1')

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

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_execs = wf_ex.task_executions

        self._assert_single_item(task_execs, name='task1')

        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_execs = wf_ex.task_executions

        task_ex = self._assert_single_item(task_execs, name='task1')
        next_task_ex = self._assert_single_item(task_execs, name='task2')

        self.assertEqual(states.SUCCESS, task_ex.state)
        self.assertEqual(states.SUCCESS, next_task_ex.state)

    def test_concurrency_is_in_runtime_context(self):
        wb_service.create_workbook_v2(CONCURRENCY_WB % 4)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wb.wf1')

        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_execs = wf_ex.task_executions

        task_ex = self._assert_single_item(task_execs, name='task1')

        self.assertEqual(states.SUCCESS, task_ex.state)
        self.assertEqual(4, task_ex.runtime_context['concurrency'])

    def test_concurrency_is_in_runtime_context_zero_value(self):
        wb_service.create_workbook_v2(CONCURRENCY_WB % 0)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wb.wf1')

        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_execs = wf_ex.task_executions

        task_ex = self._assert_single_item(task_execs, name='task1')

        self.assertEqual(states.SUCCESS, task_ex.state)
        self.assertNotIn('concurrency', task_ex.runtime_context)

    def test_concurrency_is_in_runtime_context_negative_number(self):
        # Negative concurrency value is not accepted.
        self.assertRaises(
            exc.InvalidModelException,
            wb_service.create_workbook_v2,
            CONCURRENCY_WB % -1
        )

    def test_concurrency_is_in_runtime_context_from_var(self):
        wb_service.create_workbook_v2(CONCURRENCY_WB_FROM_VAR)

        # Start workflow.
        wf_ex = self.engine.start_workflow(
            'wb.wf1',
            wf_input={'concurrency': 4}
        )

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_execs = wf_ex.task_executions

        task_ex = self._assert_single_item(task_execs, name='task1')

        self.assertEqual(4, task_ex.runtime_context['concurrency'])

    def test_concurrency_is_in_runtime_context_from_var_zero_value(self):
        wb_service.create_workbook_v2(CONCURRENCY_WB_FROM_VAR)

        # Start workflow.
        wf_ex = self.engine.start_workflow(
            'wb.wf1',
            wf_input={'concurrency': 0}
        )

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_execs = wf_ex.task_executions

        task_ex = self._assert_single_item(task_execs, name='task1')

        self.assertNotIn('concurrency', task_ex.runtime_context)

    def test_concurrency_is_in_runtime_context_from_var_negative_number(self):
        wb_service.create_workbook_v2(CONCURRENCY_WB_FROM_VAR)

        # Start workflow.
        wf_ex = self.engine.start_workflow(
            'wb.wf1',
            wf_input={'concurrency': -1}
        )

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_ex = wf_ex.task_executions[0]

        self.assertEqual(states.ERROR, task_ex.state)

        self.await_workflow_error(wf_ex.id)

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
        wf_ex = self.engine.start_workflow(
            'wb.wf1',
            wf_input={'wait_before': '1'}
        )

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
        wf_ex = self.engine.start_workflow('wf')

        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            # Note: We need to reread execution to access related tasks.
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            self.assertEqual(2, len(wf_ex.task_executions))

    @mock.patch('mistral.actions.std_actions.EchoAction.run')
    def test_retry_policy_break_on_with_dict(self, run_method):
        run_method.return_value = types.Result(error={'key-1': 15})

        wf_retry_break_on_with_dictionary = """---
        version: '2.0'

        name: wb
        workflows:
          wf1:
            tasks:
              fail_task:
                action: std.echo output='mock'
                retry:
                  count: 3
                  delay: 1
                  break-on: <% task().result['key-1'] = 15 %>
        """

        wb_service.create_workbook_v2(wf_retry_break_on_with_dictionary)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wb.wf1')

        self.await_workflow_error(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            fail_task_ex = wf_ex.task_executions[0]

        self.assertEqual(states.ERROR, fail_task_ex.state)

        self.assertEqual(
            {},
            fail_task_ex.runtime_context["retry_task_policy"]
        )
