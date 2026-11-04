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

from unittest import mock

import fixtures
from oslo_config import cfg
from oslo_utils import importutils
import requests

from mistral.actions import std_actions
from mistral import context as auth_context
from mistral.db.sqlalchemy import base as db_base
from mistral.db.v2 import api as db_api
from mistral.db.v2.sqlalchemy import models
from mistral.engine import policies
from mistral.engine import task_handler
from mistral.engine import tasks
from mistral import exceptions as exc
from mistral.lang import parser as spec_parser
from mistral.rpc import clients as rpc
from mistral.scheduler import base as sched_base
from mistral.services import workbooks as wb_service
from mistral.services import workflows as wf_service
from mistral.tests.unit import base as test_base
from mistral.tests.unit.engine import base
from mistral.workflow import states
from mistral_lib import actions as ml_actions
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
            input={},
            params={}
        )

        task_ex = models.TaskExecution(in_context={'int_var': 5})
        task_ex.workflow_execution = wf_ex

        policy.delay = "<% $.int_var %>"

        engine_task = tasks.RegularTask(wf_ex, None, None, {}, task_ex)

        # Validation is ok.
        policy.before_task_start(engine_task)

        policy.delay = "some_string"

        # Validation is failing now.
        exception = self.assertRaises(
            exc.InvalidModelException,
            policy.before_task_start,
            engine_task,
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
        wb_service.create_workbook_v2(WAIT_BEFORE_WB % 10)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wb.wf1')

        with db_api.transaction():
            # Note: We need to reread execution to access related tasks.
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_ex = wf_ex.task_executions[0]

        self.await_task_delayed(task_ex.id)
        with db_api.transaction():
            # Note: We need to reread execution to access related tasks.
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_ex = wf_ex.task_executions[0]

        self.assertDictEqual(
            {'wait_before_policy': {'skip': True}},
            task_ex.runtime_context
        )

        self.await_workflow_success(wf_ex.id)

    def test_wait_before_policy_zero_seconds(self):
        wb_service.create_workbook_v2(WAIT_BEFORE_WB % 0)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wb.wf1')
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
            wf_input={'wait_before': 10}
        )

        with db_api.transaction():
            # Note: We need to reread execution to access related tasks.
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_ex = wf_ex.task_executions[0]

        self.await_task_delayed(task_ex.id)

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
        self.await_task_error(task_ex.id)

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
        self.await_task_error(task_ex.id)

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

        self.await_task_error(task_ex.id)
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

        self.await_task_error(task_ex.id)
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

    @mock.patch.object(
        std_actions.EchoAction,
        'run',
        mock.Mock(side_effect=[
            {'status': 'pending'},
            {'status': 'done', 'value': 42}
        ])
    )
    def test_retry_continue_on_publish_intermediate_result(self):
        wf_text = """---
        version: '2.0'

        wf:
          tasks:
            task1:
              action: std.echo output="mocked result"
              retry:
                count: 3
                delay: 0
                continue-on: <% task().result.status = 'pending' %>
              publish:
                value: <% task().result.value %>
        """

        wf_service.create_workflows(wf_text)

        wf_ex = self.engine.start_workflow('wf')

        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_ex = wf_ex.task_executions[0]

        self.assertEqual({'value': 42}, task_ex.published)
        self.assertEqual(
            1,
            task_ex.runtime_context['retry_task_policy']['retry_no']
        )

    def test_retry_continue_on_publish_error_on_last_iteration(self):
        wf_text = """---
        version: '2.0'

        wf:
          tasks:
            task1:
              action: std.noop
              retry:
                count: 2
                delay: 0
                continue-on: <% true %>
              publish:
                value: <% $.missing %>
        """

        wf_service.create_workflows(wf_text)

        wf_ex = self.engine.start_workflow('wf')

        self.await_workflow_error(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_ex = wf_ex.task_executions[0]

        self.assertEqual(states.ERROR, task_ex.state)
        self.assertIn('Can not evaluate YAQL expression', task_ex.state_info)
        self.assertEqual(
            2,
            task_ex.runtime_context['retry_task_policy']['retry_no']
        )

    def test_retry_continue_on_published_var_publish_error(self):
        wf_text = """---
        version: '2.0'

        wf:
          tasks:
            task1:
              action: std.noop
              retry:
                count: 2
                delay: 0
                continue-on: <% $.value > 0 %>
              publish:
                value: <% $.missing %>
        """

        wf_service.create_workflows(wf_text)

        wf_ex = self.engine.start_workflow('wf')

        self.await_workflow_error(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_ex = wf_ex.task_executions[0]

        self.assertEqual(states.ERROR, task_ex.state)
        self.assertIn('expression=$.missing', task_ex.state_info)

    @mock.patch.object(
        std_actions.EchoAction,
        'run',
        mock.Mock(side_effect=[
            {'status': 'pending', 'value': 1},
            {'status': 'done'},
            {'status': 'done'},
            {'status': 'done'}
        ])
    )
    def test_retry_continue_on_stale_published_after_publish_error(self):
        wf_text = """---
        version: '2.0'

        wf:
          tasks:
            task1:
              action: std.echo output="mocked result"
              retry:
                count: 3
                delay: 0
                continue-on: <% $.status = 'pending' %>
              publish:
                status: <% task().result.status %>
                value: <% task().result.value %>
        """

        wf_service.create_workflows(wf_text)

        wf_ex = self.engine.start_workflow('wf')

        self.await_workflow_error(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_ex = wf_ex.task_executions[0]

        self.assertEqual(states.ERROR, task_ex.state)
        self.assertIn('expression=task().result.value', task_ex.state_info)
        self.assertEqual({}, task_ex.published)
        self.assertEqual(
            1,
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

    def test_retry_join_task_after_failed_task(self):
        retry_wb = """---
        version: '2.0'
        name: wb
        workflows:
          wf1:
            task-defaults:
              retry:
                count: 1
                delay: 0
            tasks:
              task1:
                on-success: join_task
              task2:
                action: std.fail
                on-success: join_task
              join_task:
                join: all
        """
        wb_service.create_workbook_v2(retry_wb)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wb.wf1')

        self.await_workflow_error(wf_ex.id)

        with db_api.transaction():
            # Note: We need to reread execution to access related tasks.
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_execs = wf_ex.task_executions

        self._assert_single_item(task_execs, name="task2", state=states.ERROR)
        self._assert_single_item(
            task_execs,
            name="join_task",
            state=states.ERROR
        )

    def test_retry_join_task_after_idle_task(self):
        retry_wb = """---
        version: '2.0'
        name: wb
        workflows:
          wf1:
            task-defaults:
              retry:
                count: 1
                delay: 0
            tasks:
              task1:
                on-success: join_task
              task2:
                action: std.fail
                on-success: task3
              task3:
                on-success: join_task
              join_task:
                join: all
        """
        wb_service.create_workbook_v2(retry_wb)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wb.wf1')

        self.await_workflow_error(wf_ex.id)

        with db_api.transaction():
            # Note: We need to reread execution to access related tasks.
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_execs = wf_ex.task_executions

        self._assert_single_item(task_execs, name="task2", state=states.ERROR)
        self._assert_single_item(
            task_execs,
            name="join_task",
            state=states.ERROR
        )

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

    @mock.patch.object(
        std_actions.MistralHTTPAction,
        'run',
        mock.MagicMock(return_value='mock')
    )
    def test_retry_async_action(self):
        """Test that an action won't be done twice

        When completing an action, we are supposed to receive the completion
        only once. If we receive it twice or more, it should raise an error.

        If we want to retry that action, then the engine will create a new
        action execution.
        """
        retry_wf = """---
          version: '2.0'
          repeated_retry:
            tasks:
              async_http:
                retry:
                  delay: 0
                  count: 2
                action: std.mistral_http url='https://opendev.org'
            """

        # Create and wait for the wf to be running
        wf_service.create_workflows(retry_wf)
        wf_ex = self.engine.start_workflow('repeated_retry')
        self.await_workflow_running(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
            task_ex = wf_ex.task_executions[0]

        # Wait for the task to be running
        self.await_task_running(task_ex.id)

        with db_api.transaction():
            # We need to it back to be bound to a db transaction
            task_ex = db_api.get_task_execution(task_ex.id)
            first_action_ex = task_ex.executions[0]

        # Now wait for this action to be running
        # Note that the task won't actually run because it's mocked
        self.await_action_state(first_action_ex.id, states.RUNNING)

        # Send an action complete event with error so the task will retry
        complete_action_params = (
            first_action_ex.id,
            ml_actions.Result(error="mock")
        )
        rpc.get_engine_client().on_action_complete(*complete_action_params)

        # Send it a second time -- this should raise a ValueError
        self.assertRaises(
            exc.MistralException,
            rpc.get_engine_client().on_action_complete,
            *complete_action_params
        )

        # And the task should be restarted
        self.await_task_running(task_ex.id)

        with db_api.transaction():
            task_ex = db_api.get_task_execution(task_ex.id)
            second_action_ex = task_ex.executions[1]

        # This time, send a success action complete
        complete_action_params = (
            second_action_ex.id,
            ml_actions.Result(data="mock")
        )
        rpc.get_engine_client().on_action_complete(*complete_action_params)

        # Wait for the wf to finish
        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
        self.await_workflow_success(wf_ex.id)

        # Now check the results
        with db_api.transaction():
            task_ex = db_api.get_task_execution(task_ex.id)
            action_exs = task_ex.executions
            # We are supposed to have two actions
            self.assertEqual(2, len(action_exs))
            # First is in error
            self.assertEqual(states.ERROR, action_exs[0].state)
            # Second is success
            self.assertEqual(states.SUCCESS, action_exs[1].state)

    def _get_task_ex(self, wf_ex_id):
        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex_id)

            return wf_ex.task_executions[0]

    def _assert_task(self, task_ex_id, state, action_count):
        with db_api.transaction():
            task_ex = db_api.get_task_execution(task_ex_id)

            self.assertEqual(state, task_ex.state)
            self.assertEqual(action_count, len(task_ex.action_executions))

    def _hold_delayed_jobs(self):
        # Delayed policy jobs are kept here instead of being scheduled, so
        # the test decides when a delay ends instead of the clock.
        sched = sched_base.get_system_scheduler()
        schedule = sched.schedule
        has_scheduled_jobs = sched.has_scheduled_jobs
        self.delayed_jobs = []

        def _schedule(job):
            if job.run_after and job.func_name in (
                    policies._CONTINUE_TASK_PATH,
                    task_handler._REFRESH_TASK_STATE_PATH):
                self.delayed_jobs.append(job)
            else:
                schedule(job)

        # The engine skips a join refresh when one is already pending, so
        # held jobs must still count as scheduled.
        def _has_scheduled_jobs(**filters):
            if 'key' in filters and any(
                    j.key == filters['key'] for j in self.delayed_jobs):
                return True

            return has_scheduled_jobs(**filters)

        self.has_scheduled_jobs = mock.Mock(side_effect=_has_scheduled_jobs)

        self.useFixture(fixtures.MockPatchObject(sched, 'schedule', _schedule))
        self.useFixture(fixtures.MockPatchObject(
            sched, 'has_scheduled_jobs', self.has_scheduled_jobs
        ))

    def _run_delayed_job(self, func_path):
        self._await(lambda: self.delayed_jobs, delay=0.1)

        job = self.delayed_jobs.pop(0)

        self.assertEqual(func_path, job.func_name)

        importutils.import_class(func_path)(**job.func_args)

    def _fail_running_action(self, task_ex_id):
        def _running_action():
            with db_api.transaction():
                for a_ex in db_api.get_task_execution(
                        task_ex_id).action_executions:
                    if a_ex.state == states.RUNNING:
                        return a_ex.id

        def _refresh_pending():
            with db_api.transaction():
                return db_api.get_scheduled_jobs_count(
                    key=task_handler._get_refresh_state_job_key(task_ex_id)
                )

        self._await(lambda: _running_action() is not None, delay=0.1)

        # Each joined branch queues its own refresh; a late one would rerun
        # the task as soon as it is WAITING, skipping the retry delay.
        self._await(lambda: not _refresh_pending(), delay=0.1)

        self.engine.on_action_complete(
            _running_action(),
            ml_actions.Result(error='Fail')
        )

    def _start_join_task(self, wf_ex_id):
        def _join_task_execs():
            with db_api.transaction():
                return db_api.get_task_executions(
                    workflow_execution_id=wf_ex_id,
                    name='join_task'
                )

        self._await(lambda: len(_join_task_execs()) == 1, delay=0.1)

        task_ex = _join_task_execs()[0]

        self._fail_running_action(task_ex.id)
        self._assert_task(task_ex.id, states.WAITING, 1)

        return task_ex

    def test_retry_policy_paused_workflow(self):
        self._hold_delayed_jobs()

        wf_text = """---
        version: '2.0'

        wf1:
          tasks:
            task1:
              action: std.fail
              retry:
                count: 2
                delay: 2
        """

        wf_service.create_workflows(wf_text)

        wf_ex = self.engine.start_workflow('wf1')
        task_ex = self._get_task_ex(wf_ex.id)

        self.await_task_delayed(task_ex.id, delay=0.1)

        self.engine.pause_workflow(wf_ex.id)
        self.await_workflow_paused(wf_ex.id)

        self._run_delayed_job(policies._CONTINUE_TASK_PATH)
        self._assert_task(task_ex.id, states.IDLE, 1)

        self.engine.resume_workflow(wf_ex.id)

        self._run_delayed_job(policies._CONTINUE_TASK_PATH)

        self.await_workflow_error(wf_ex.id)
        self._assert_task(task_ex.id, states.ERROR, 3)

    def test_retry_policy_join_task_paused_workflow(self):
        self._hold_delayed_jobs()

        wf_text = """---
        version: '2.0'

        wf1:
          tasks:
            task1:
              action: std.noop
              on-success: join_task
            task2:
              action: std.noop
              on-success: join_task
            join_task:
              join: all
              action: std.async_noop
              retry:
                count: 2
                delay: 2
        """

        wf_service.create_workflows(wf_text)

        wf_ex = self.engine.start_workflow('wf1')
        task_ex = self._start_join_task(wf_ex.id)

        self.engine.pause_workflow(wf_ex.id)
        self.await_workflow_paused(wf_ex.id)

        self._run_delayed_job(task_handler._REFRESH_TASK_STATE_PATH)
        self._assert_task(task_ex.id, states.WAITING, 1)

        # Resume refreshes the WAITING join task right away.
        self.engine.resume_workflow(wf_ex.id)
        self._fail_running_action(task_ex.id)

        self._run_delayed_job(task_handler._REFRESH_TASK_STATE_PATH)
        self._fail_running_action(task_ex.id)

        self.await_workflow_error(wf_ex.id)
        self._assert_task(task_ex.id, states.ERROR, 3)

    def test_retry_policy_join_task_resumed_before_delay(self):
        self._hold_delayed_jobs()

        wf_text = """---
        version: '2.0'

        wf1:
          tasks:
            task1:
              action: std.noop
              on-success: join_task
            task2:
              action: std.noop
              on-success: join_task
            join_task:
              join: all
              action: std.async_noop
              retry:
                count: 1
                delay: 5
        """

        wf_service.create_workflows(wf_text)

        wf_ex = self.engine.start_workflow('wf1')
        task_ex = self._start_join_task(wf_ex.id)

        self.engine.pause_workflow(wf_ex.id)
        self.await_workflow_paused(wf_ex.id)

        self.has_scheduled_jobs.reset_mock()
        self.engine.resume_workflow(wf_ex.id)

        # Resume refreshes WAITING tasks after its transaction; this call
        # means that refresh ran and found the held retry still pending.
        self._await(lambda: self.has_scheduled_jobs.called, delay=0.1)
        self._assert_task(task_ex.id, states.WAITING, 1)
        self.assertEqual(1, len(self.delayed_jobs))

        self._run_delayed_job(task_handler._REFRESH_TASK_STATE_PATH)
        self._fail_running_action(task_ex.id)

        self.await_workflow_error(wf_ex.id)
        self._assert_task(task_ex.id, states.ERROR, 2)

    def test_retry_policy_cancelled_workflow(self):
        self._hold_delayed_jobs()

        wf_text = """---
        version: '2.0'

        wf1:
          tasks:
            task1:
              action: std.fail
              retry:
                count: 2
                delay: 2
        """

        wf_service.create_workflows(wf_text)

        wf_ex = self.engine.start_workflow('wf1')
        task_ex = self._get_task_ex(wf_ex.id)

        self.await_task_delayed(task_ex.id, delay=0.1)

        self.engine.stop_workflow(wf_ex.id, states.CANCELLED)
        self.await_workflow_cancelled(wf_ex.id)

        self._run_delayed_job(policies._CONTINUE_TASK_PATH)

        self._assert_task(task_ex.id, states.CANCELLED, 1)

    def test_retry_policy_paused_then_cancelled_workflow(self):
        self._hold_delayed_jobs()

        wf_text = """---
        version: '2.0'

        wf1:
          tasks:
            task1:
              action: std.fail
              retry:
                count: 2
                delay: 2
        """

        wf_service.create_workflows(wf_text)

        wf_ex = self.engine.start_workflow('wf1')
        task_ex = self._get_task_ex(wf_ex.id)

        self.await_task_delayed(task_ex.id, delay=0.1)

        self.engine.pause_workflow(wf_ex.id)
        self.await_workflow_paused(wf_ex.id)

        self._run_delayed_job(policies._CONTINUE_TASK_PATH)
        self._assert_task(task_ex.id, states.IDLE, 1)

        self.engine.stop_workflow(wf_ex.id, states.CANCELLED)
        self.await_workflow_cancelled(wf_ex.id)

        self._assert_task(task_ex.id, states.CANCELLED, 1)

    def test_retry_policy_action_fails_after_cancel(self):
        self._hold_delayed_jobs()

        wf_text = """---
        version: '2.0'

        wf1:
          tasks:
            task1:
              action: std.async_noop
              retry:
                count: 2
                delay: 2
        """

        wf_service.create_workflows(wf_text)

        wf_ex = self.engine.start_workflow('wf1')
        task_ex = self._get_task_ex(wf_ex.id)

        self.await_task_running(task_ex.id)

        with db_api.transaction():
            action_ex_id = db_api.get_task_execution(
                task_ex.id
            ).action_executions[0].id

        self.engine.stop_workflow(wf_ex.id, states.CANCELLED)
        self.await_workflow_cancelled(wf_ex.id)

        self.engine.on_action_complete(
            action_ex_id,
            ml_actions.Result(error='Fail')
        )

        self.await_task_error(task_ex.id)
        self._assert_task(task_ex.id, states.ERROR, 1)
        self.assertEqual([], self.delayed_jobs)

    def test_wait_before_policy_paused_workflow(self):
        self._hold_delayed_jobs()

        wf_text = """---
        version: '2.0'

        wf1:
          tasks:
            task1:
              action: std.noop
              wait-before: 2
        """

        wf_service.create_workflows(wf_text)

        wf_ex = self.engine.start_workflow('wf1')
        task_ex = self._get_task_ex(wf_ex.id)

        self.await_task_delayed(task_ex.id, delay=0.1)

        self.engine.pause_workflow(wf_ex.id)
        self.await_workflow_paused(wf_ex.id)

        self._run_delayed_job(policies._CONTINUE_TASK_PATH)
        self._assert_task(task_ex.id, states.IDLE, 0)

        self.engine.resume_workflow(wf_ex.id)
        self.await_workflow_success(wf_ex.id)

        self._assert_task(task_ex.id, states.SUCCESS, 1)

    def test_timeout_policy(self):
        wb_service.create_workbook_v2(TIMEOUT_WB % 2)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wb.wf1')

        with db_api.transaction():
            # Note: We need to reread execution to access related tasks.
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_ex = wf_ex.task_executions[0]

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

        # NOTE(amorin) we used to test the task state here
        # but this is not possible because we cannot be sure the task is
        # actually IDLE, RUNNING or even ERROR (because it's suppose to fail)
        # It depends on the server load / latency
        # So now, we will only await for it to be in error
        # See lp-2051040
        self.await_task_error(task_ex.id)

        # And workflow
        self.await_workflow_error(wf_ex.id)

        # Wait until timeout exceeds.
        self._sleep(1)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_execs = wf_ex.task_executions

        # Make sure that engine did not create extra tasks.
        self.assertEqual(1, len(task_execs))

    def test_timeout_policy_with_retry(self):
        wf_text = """---
        version: '2.0'

        wf1:
          tasks:
            task1:
              action: std.async_noop
              timeout: 1
              retry:
                count: 3
                delay: 0
        """

        wf_service.create_workflows(wf_text)

        wf_ex = self.engine.start_workflow('wf1')

        self.await_workflow_error(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
            task_ex = wf_ex.task_executions[0]

            self.assertEqual(states.ERROR, task_ex.state)
            self.assertIn('Task timed out', task_ex.state_info)
            self.assertEqual(1, len(task_ex.action_executions))
            self.assertNotIn('retry_task_policy', task_ex.runtime_context)

    def test_timeout_policy_during_retry_delay(self):
        wf_text = """---
        version: '2.0'

        wf1:
          tasks:
            task1:
              action: std.fail
              timeout: 1
              retry:
                count: 3
                delay: 3
              on-error: task2

            task2:
              action: std.async_noop
        """

        wf_service.create_workflows(wf_text)

        wf_ex = self.engine.start_workflow('wf1')

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
            task_ex = wf_ex.task_executions[0]

        self.await_task_error(task_ex.id, delay=0.2)

        self._await(
            lambda: not db_api.get_scheduled_jobs_count(
                func_name=policies._CONTINUE_TASK_PATH
            ),
            delay=0.2
        )

        with db_api.transaction():
            task_ex = db_api.get_task_execution(task_ex.id)

            self.assertEqual(states.ERROR, task_ex.state)
            self.assertIn('Task timed out', task_ex.state_info)
            self.assertEqual(1, len(task_ex.action_executions))

    def test_retry_job_fires_after_timeout_while_paused(self):
        wf_text = """---
        version: '2.0'

        wf1:
          tasks:
            task1:
              action: std.fail
              retry:
                count: 3
                delay: 60
        """

        wf_service.create_workflows(wf_text)

        wf_ex = self.engine.start_workflow('wf1')

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
            task_ex_id = wf_ex.task_executions[0].id

        self.await_task_delayed(task_ex_id)

        self.engine.pause_workflow(wf_ex.id)

        self.await_workflow_paused(wf_ex.id)

        @db_base.session_aware()
        def _timeout_and_resume(session=None):
            task_table = models.TaskExecution.__table__
            wf_table = models.WorkflowExecution.__table__

            session.execute(
                task_table.update().where(
                    task_table.c.id == task_ex_id
                ).values(state=states.ERROR)
            )
            session.execute(
                wf_table.update().where(
                    wf_table.c.id == wf_ex.id
                ).values(state=states.RUNNING)
            )

        acquire_lock = db_api.acquire_lock

        def _acquire_lock(*args, **kwargs):
            _timeout_and_resume()

            return acquire_lock(*args, **kwargs)

        with mock.patch.object(db_api, 'acquire_lock', _acquire_lock):
            policies._continue_task(task_ex_id)

        with db_api.transaction():
            task_ex = db_api.get_task_execution(task_ex_id)

            self.assertEqual(states.ERROR, task_ex.state)
            self.assertEqual(1, len(task_ex.action_executions))

    def test_timeout_policy_concurrent_update(self):
        wf_text = """---
        version: '2.0'

        wf1:
          tasks:
            task1:
              action: std.async_noop
              retry:
                count: 3
                delay: 60
        """

        wf_service.create_workflows(wf_text)

        wf_ex = self.engine.start_workflow('wf1')

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
            task_ex_id = wf_ex.task_executions[0].id

        self.await_task_running(task_ex_id)

        retry_ctx = {'retry_task_policy': {'retry_no': 1}}

        @db_base.session_aware()
        def _concurrent_update(session=None):
            table = models.TaskExecution.__table__

            session.execute(
                table.update().where(table.c.id == task_ex_id).values(
                    state=states.RUNNING_DELAYED,
                    runtime_context=retry_ctx
                )
            )

        load = db_api.load_task_execution

        def _load(*args, **kwargs):
            task_ex = load(*args, **kwargs)

            _concurrent_update()

            return task_ex

        with mock.patch.object(db_api, 'load_task_execution', _load):
            policies._fail_task_if_incomplete(task_ex_id, 1)

        with db_api.transaction():
            task_ex = db_api.get_task_execution(task_ex_id)

            self.assertEqual(states.ERROR, task_ex.state)
            self.assertEqual(
                {'retry_no': 1},
                task_ex.runtime_context['retry_task_policy']
            )
            self.assertTrue(task_ex.runtime_context['timed_out'])

    def test_timeout_policy_admin_other_project(self):
        wf_text = """---
        version: '2.0'

        wf1:
          tasks:
            task1:
              action: std.async_noop
        """

        wf_service.create_workflows(wf_text)

        wf_ex = self.engine.start_workflow('wf1')

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
            task_ex_id = wf_ex.task_executions[0].id

        self.await_task_running(task_ex_id)

        self.override_config('auth_enable', True, group='pecan')

        auth_context.set_ctx(test_base.get_context(default=False, admin=True))

        policies._fail_task_if_incomplete(task_ex_id, 1)

        auth_context.set_ctx(self.ctx)

        with db_api.transaction():
            task_ex = db_api.get_task_execution(task_ex_id)

            self.assertEqual(states.ERROR, task_ex.state)
            self.assertIn('Task timed out', task_ex.state_info)

    def test_timeout_policy_from_var(self):
        wb_service.create_workbook_v2(TIMEOUT_FROM_VAR)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wb.wf1', wf_input={'timeout': 1})

        with db_api.transaction():
            # Note: We need to reread execution to access related tasks.
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_ex = wf_ex.task_executions[0]

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

        self.await_task_error(task_ex.id)

        self.await_workflow_error(wf_ex.id)

    def test_retry_with_input(self):
        wf_text = """---
        version: '2.0'

        wf1:
          tasks:
            task1:
              action: std.noop
              on-success:
                - task2
              publish:
                success: task4

            task2:
              action: std.noop
              on-success:
               - task4: <% $.success = 'task4' %>
               - task5: <% $.success = 'task5' %>

            task4:
              on-complete:
                - task5
              publish:
                param: data

            task5:
              action: std.echo
              input:
                output: {
                    "status": 200,
                    "param": <% $.param %>
                  }
              publish:
                res: <% task(task5).result %>
              retry:
                continue-on: <% $.res.status < 300 %>
                count: 1
                delay: 1
        """
        wf_service.create_workflows(wf_text)

        wf_ex = self.engine.start_workflow('wf1')

        self.await_workflow_success(wf_ex.id)

    def test_action_timeout(self):
        wf_text = """---
        version: '2.0'
        wf1:
          tasks:
            task1:
              action: std.sleep seconds=2
              timeout: 1
        """

        wf_service.create_workflows(wf_text)

        wf_ex = self.engine.start_workflow('wf1')

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
            task_ex = wf_ex.task_executions[0]
        self.await_task_processed(task_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
            task_ex = wf_ex.task_executions[0]
            action_ex = task_ex.action_executions[0]

        self.await_workflow_error(wf_ex.id, delay=1)
        self.await_task_error(task_ex.id, delay=1)
        # The action can take a little bit longer than workflow and task
        # because we can't stop the thread running the action
        self.await_action_error(action_ex.id, delay=2)

    def test_pause_before_policy(self):
        wb_service.create_workbook_v2(PAUSE_BEFORE_WB)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wb.wf1')

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_execs = wf_ex.task_executions

        task_ex = self._assert_single_item(task_execs, name='task1')

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

        # Verify wf paused by pause-before
        self.await_workflow_paused(wf_ex.id)

        # Allow wait-before to expire
        self._sleep(2)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        # Verify wf still paused (wait-before didn't reactivate)
        self.await_workflow_paused(wf_ex.id)

        task_ex = db_api.get_task_execution(task_ex.id)

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
        self.await_task_success(task_ex.id)

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

        self.await_task_error(task_ex.id)

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
        self.await_workflow_error(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
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

        wb_text = """---
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

        wb_service.create_workbook_v2(wb_text)

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

    def test_fail_on_true_condition(self):
        retry_wb = """---
        version: '2.0'

        name: wb

        workflows:
          wf1:
            tasks:
              task1:
                action: std.echo output=4
                fail-on: <% task(task1).result <= 4 %>
        """
        wb_service.create_workbook_v2(retry_wb)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wb.wf1')

        self.await_workflow_error(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
            task_ex = wf_ex.task_executions[0]

        self.assertEqual(task_ex.state, states.ERROR, "Check task state")

    def test_fail_on_false_condition(self):
        retry_wb = """---
        version: '2.0'

        name: wb

        workflows:
          wf1:
            tasks:
              task1:
                action: std.echo output=4
                fail-on: <% task(task1).result != 4 %>
        """
        wb_service.create_workbook_v2(retry_wb)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wb.wf1')

        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
            task_ex = wf_ex.task_executions[0]

        self.assertEqual(task_ex.state, states.SUCCESS, "Check task state")

    def test_fail_on_true_condition_task_defaults(self):
        retry_wb = """---
        version: '2.0'

        name: wb

        workflows:
          wf1:
            task-defaults:
              fail-on: <% task().result <= 4 %>
            tasks:
              task1:
                action: std.echo output=4
        """
        wb_service.create_workbook_v2(retry_wb)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wb.wf1')

        self.await_workflow_error(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
            task_ex = wf_ex.task_executions[0]

        self.assertEqual(task_ex.state, states.ERROR, "Check task state")

    @mock.patch.object(
        std_actions.EchoAction,
        'run',
        mock.Mock(side_effect=[1, 2, 3, 4])
    )
    def test_fail_on_with_retry(self):
        retry_wb = """---
        version: '2.0'

        name: wb

        workflows:
          wf1:
            tasks:
              task1:
                action: std.echo output="mocked"
                fail-on: <% task(task1).result <= 2 %>
                retry:
                  count: 3
                  delay: 0
        """
        wb_service.create_workbook_v2(retry_wb)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wb.wf1')

        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
            task_ex = wf_ex.task_executions[0]

        self.assertEqual(task_ex.state, states.SUCCESS, "Check task state")
        self.assertEqual(
            2,
            task_ex.runtime_context['retry_task_policy']['retry_no']
        )

    @mock.patch.object(
        std_actions.EchoAction,
        'run',
        mock.Mock(side_effect=[1, 2, 3, 4])
    )
    def test_fail_on_with_retry_and_with_items(self):
        retry_wb = """---
        version: '2.0'

        name: wb

        workflows:
          wf1:
            tasks:
              task1:
                with-items: x in [1, 2]
                action: std.echo output="mocked"
                fail-on: <% not task(task1).result.contains(4) %>
                retry:
                  count: 3
                  delay: 0
        """
        wb_service.create_workbook_v2(retry_wb)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wb.wf1')

        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
            task_ex = wf_ex.task_executions[0]

        self.assertEqual(task_ex.state, states.SUCCESS, "Check task state")
        self.assertEqual(
            1,
            task_ex.runtime_context['retry_task_policy']['retry_no']
        )
