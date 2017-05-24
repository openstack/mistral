# Copyright 2018 - Extreme Networks, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License");
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

import json
import mock

from oslo_config import cfg

from mistral.db.v2 import api as db_api
from mistral.notifiers import base as notif
from mistral.notifiers import notification_events as events
from mistral.services import workbooks as wb_svc
from mistral.services import workflows as wf_svc
from mistral.tests.unit.notifiers import base
from mistral.workflow import states
from mistral_lib import actions as ml_actions

# Use the set_default method to set value otherwise in certain test cases
# the change in value is not permanent.
cfg.CONF.set_default('auth_enable', False, group='pecan')

EVENT_LOGS = []


def log_event(ex_id, data, event, timestamp, **kwargs):
    EVENT_LOGS.append((ex_id, event))


class NotifyEventsTest(base.NotifierTestCase):

    def setUp(self):
        super(NotifyEventsTest, self).setUp()

        self.publishers = {
            'wbhk': notif.get_notification_publisher('webhook'),
            'noop': notif.get_notification_publisher('noop')
        }

        self.publishers['wbhk'].publish = mock.MagicMock(side_effect=log_event)
        self.publishers['wbhk'].publish.reset_mock()
        self.publishers['noop'].publish = mock.MagicMock(side_effect=log_event)
        self.publishers['noop'].publish.reset_mock()

        del EVENT_LOGS[:]

    def tearDown(self):
        cfg.CONF.set_default('notify', None, group='notifier')
        super(NotifyEventsTest, self).tearDown()

    def test_notify_all_explicit(self):
        wf_def = """
        version: '2.0'
        wf:
          tasks:
            t1:
              action: std.noop
              on-success:
                - t2
            t2:
              action: std.noop
        """

        wf_svc.create_workflows(wf_def)

        notify_options = [
            {
                'type': 'webhook',
                'events': events.EVENTS
            }
        ]

        params = {'notify': notify_options}

        wf_ex = self.engine.start_workflow('wf', '', **params)

        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
            task_exs = wf_ex.task_executions

        self.assertEqual(states.SUCCESS, wf_ex.state)
        self.assertIsNone(wf_ex.state_info)
        self.assertEqual(2, len(task_exs))

        t1_ex = self._assert_single_item(task_exs, name='t1')
        t2_ex = self._assert_single_item(task_exs, name='t2')

        self.assertEqual(states.SUCCESS, t1_ex.state)
        self.assertIsNone(t1_ex.state_info)
        self.assertEqual(states.SUCCESS, t2_ex.state)
        self.assertIsNone(t2_ex.state_info)

        self.assertTrue(self.publishers['wbhk'].publish.called)
        self.assertEqual(6, len(EVENT_LOGS))
        self.assertIn((wf_ex.id, events.WORKFLOW_LAUNCHED), EVENT_LOGS)
        self.assertIn((t1_ex.id, events.TASK_LAUNCHED), EVENT_LOGS)
        self.assertIn((t1_ex.id, events.TASK_SUCCEEDED), EVENT_LOGS)
        self.assertIn((t2_ex.id, events.TASK_LAUNCHED), EVENT_LOGS)
        self.assertIn((t2_ex.id, events.TASK_SUCCEEDED), EVENT_LOGS)
        self.assertIn((wf_ex.id, events.WORKFLOW_SUCCEEDED), EVENT_LOGS)

    def test_notify_all_implicit(self):
        wf_def = """
        version: '2.0'
        wf:
          tasks:
            t1:
              action: std.noop
              on-success:
                - t2
            t2:
              action: std.noop
        """

        wf_svc.create_workflows(wf_def)

        notify_options = [{'type': 'webhook'}]
        params = {'notify': notify_options}

        wf_ex = self.engine.start_workflow('wf', '', **params)

        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
            task_exs = wf_ex.task_executions

        self.assertEqual(states.SUCCESS, wf_ex.state)
        self.assertIsNone(wf_ex.state_info)
        self.assertEqual(2, len(task_exs))

        t1_ex = self._assert_single_item(task_exs, name='t1')
        t2_ex = self._assert_single_item(task_exs, name='t2')

        self.assertEqual(states.SUCCESS, t1_ex.state)
        self.assertIsNone(t1_ex.state_info)
        self.assertEqual(states.SUCCESS, t2_ex.state)
        self.assertIsNone(t2_ex.state_info)

        self.assertTrue(self.publishers['wbhk'].publish.called)
        self.assertEqual(6, len(EVENT_LOGS))
        self.assertIn((wf_ex.id, events.WORKFLOW_LAUNCHED), EVENT_LOGS)
        self.assertIn((t1_ex.id, events.TASK_LAUNCHED), EVENT_LOGS)
        self.assertIn((t1_ex.id, events.TASK_SUCCEEDED), EVENT_LOGS)
        self.assertIn((t2_ex.id, events.TASK_LAUNCHED), EVENT_LOGS)
        self.assertIn((t2_ex.id, events.TASK_SUCCEEDED), EVENT_LOGS)
        self.assertIn((wf_ex.id, events.WORKFLOW_SUCCEEDED), EVENT_LOGS)

    def test_notify_order(self):
        wf_def = """
        version: '2.0'
        wf:
          tasks:
            t1:
              action: std.noop
              on-success:
                - t2
            t2:
              action: std.noop
        """

        wf_svc.create_workflows(wf_def)

        notify_options = [
            {'type': 'webhook'}
        ]

        params = {'notify': notify_options}

        wf_ex = self.engine.start_workflow('wf', '', **params)

        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
            task_exs = wf_ex.task_executions

        self.assertEqual(states.SUCCESS, wf_ex.state)
        self.assertIsNone(wf_ex.state_info)
        self.assertEqual(2, len(task_exs))

        t1_ex = self._assert_single_item(task_exs, name='t1')
        t2_ex = self._assert_single_item(task_exs, name='t2')

        self.assertEqual(states.SUCCESS, t1_ex.state)
        self.assertIsNone(t1_ex.state_info)
        self.assertEqual(states.SUCCESS, t2_ex.state)
        self.assertIsNone(t2_ex.state_info)

        expected_order = [
            (wf_ex.id, events.WORKFLOW_LAUNCHED),
            (t1_ex.id, events.TASK_LAUNCHED),
            (t1_ex.id, events.TASK_SUCCEEDED),
            (t2_ex.id, events.TASK_LAUNCHED),
            (t2_ex.id, events.TASK_SUCCEEDED),
            (wf_ex.id, events.WORKFLOW_SUCCEEDED)
        ]

        self.assertTrue(self.publishers['wbhk'].publish.called)
        self.assertListEqual(expected_order, EVENT_LOGS)

    def test_notify_multiple(self):
        self.assertFalse(self.publishers['wbhk'].publish.called)
        self.assertFalse(self.publishers['noop'].publish.called)

        wf_def = """
        version: '2.0'
        wf:
          tasks:
            t1:
              action: std.noop
              on-success:
                - t2
            t2:
              action: std.noop
        """

        wf_svc.create_workflows(wf_def)

        notify_options = [
            {'type': 'webhook'},
            {'type': 'noop'}
        ]

        params = {'notify': notify_options}

        wf_ex = self.engine.start_workflow('wf', '', **params)

        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
            task_exs = wf_ex.task_executions

        self.assertEqual(states.SUCCESS, wf_ex.state)
        self.assertIsNone(wf_ex.state_info)
        self.assertEqual(2, len(task_exs))

        t1_ex = self._assert_single_item(task_exs, name='t1')
        t2_ex = self._assert_single_item(task_exs, name='t2')

        self.assertEqual(states.SUCCESS, t1_ex.state)
        self.assertIsNone(t1_ex.state_info)
        self.assertEqual(states.SUCCESS, t2_ex.state)
        self.assertIsNone(t2_ex.state_info)

        expected_order = [
            (wf_ex.id, events.WORKFLOW_LAUNCHED),
            (wf_ex.id, events.WORKFLOW_LAUNCHED),
            (t1_ex.id, events.TASK_LAUNCHED),
            (t1_ex.id, events.TASK_LAUNCHED),
            (t1_ex.id, events.TASK_SUCCEEDED),
            (t1_ex.id, events.TASK_SUCCEEDED),
            (t2_ex.id, events.TASK_LAUNCHED),
            (t2_ex.id, events.TASK_LAUNCHED),
            (t2_ex.id, events.TASK_SUCCEEDED),
            (t2_ex.id, events.TASK_SUCCEEDED),
            (wf_ex.id, events.WORKFLOW_SUCCEEDED),
            (wf_ex.id, events.WORKFLOW_SUCCEEDED)
        ]

        self.assertTrue(self.publishers['wbhk'].publish.called)
        self.assertTrue(self.publishers['noop'].publish.called)
        self.assertListEqual(expected_order, EVENT_LOGS)

    def test_notify_from_cfg(self):
        self.assertFalse(self.publishers['wbhk'].publish.called)
        self.assertFalse(self.publishers['noop'].publish.called)

        wf_def = """
        version: '2.0'
        wf:
          tasks:
            t1:
              action: std.noop
              on-success:
                - t2
            t2:
              action: std.noop
        """

        wf_svc.create_workflows(wf_def)

        notify_options = [
            {'type': 'webhook'},
            {'type': 'noop'}
        ]

        cfg.CONF.set_default(
            'notify',
            json.dumps(notify_options),
            group='notifier'
        )

        wf_ex = self.engine.start_workflow('wf', '')

        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
            task_exs = wf_ex.task_executions

        self.assertEqual(states.SUCCESS, wf_ex.state)
        self.assertIsNone(wf_ex.state_info)
        self.assertEqual(2, len(task_exs))

        t1_ex = self._assert_single_item(task_exs, name='t1')
        t2_ex = self._assert_single_item(task_exs, name='t2')

        self.assertEqual(states.SUCCESS, t1_ex.state)
        self.assertIsNone(t1_ex.state_info)
        self.assertEqual(states.SUCCESS, t2_ex.state)
        self.assertIsNone(t2_ex.state_info)

        expected_order = [
            (wf_ex.id, events.WORKFLOW_LAUNCHED),
            (wf_ex.id, events.WORKFLOW_LAUNCHED),
            (t1_ex.id, events.TASK_LAUNCHED),
            (t1_ex.id, events.TASK_LAUNCHED),
            (t1_ex.id, events.TASK_SUCCEEDED),
            (t1_ex.id, events.TASK_SUCCEEDED),
            (t2_ex.id, events.TASK_LAUNCHED),
            (t2_ex.id, events.TASK_LAUNCHED),
            (t2_ex.id, events.TASK_SUCCEEDED),
            (t2_ex.id, events.TASK_SUCCEEDED),
            (wf_ex.id, events.WORKFLOW_SUCCEEDED),
            (wf_ex.id, events.WORKFLOW_SUCCEEDED)
        ]

        self.assertTrue(self.publishers['wbhk'].publish.called)
        self.assertTrue(self.publishers['noop'].publish.called)
        self.assertListEqual(expected_order, EVENT_LOGS)

    def test_notify_from_cfg_and_params(self):
        self.assertFalse(self.publishers['wbhk'].publish.called)
        self.assertFalse(self.publishers['noop'].publish.called)

        wf_def = """
        version: '2.0'
        wf:
          tasks:
            t1:
              action: std.noop
              on-success:
                - t2
            t2:
              action: std.noop
        """

        wf_svc.create_workflows(wf_def)

        cfg.CONF.set_default(
            'notify',
            json.dumps([{'type': 'noop'}]),
            group='notifier'
        )

        params = {'notify': [{'type': 'webhook'}]}

        wf_ex = self.engine.start_workflow('wf', '', **params)

        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
            task_exs = wf_ex.task_executions

        self.assertEqual(states.SUCCESS, wf_ex.state)
        self.assertIsNone(wf_ex.state_info)
        self.assertEqual(2, len(task_exs))

        t1_ex = self._assert_single_item(task_exs, name='t1')
        t2_ex = self._assert_single_item(task_exs, name='t2')

        self.assertEqual(states.SUCCESS, t1_ex.state)
        self.assertIsNone(t1_ex.state_info)
        self.assertEqual(states.SUCCESS, t2_ex.state)
        self.assertIsNone(t2_ex.state_info)

        expected_order = [
            (wf_ex.id, events.WORKFLOW_LAUNCHED),
            (wf_ex.id, events.WORKFLOW_LAUNCHED),
            (t1_ex.id, events.TASK_LAUNCHED),
            (t1_ex.id, events.TASK_LAUNCHED),
            (t1_ex.id, events.TASK_SUCCEEDED),
            (t1_ex.id, events.TASK_SUCCEEDED),
            (t2_ex.id, events.TASK_LAUNCHED),
            (t2_ex.id, events.TASK_LAUNCHED),
            (t2_ex.id, events.TASK_SUCCEEDED),
            (t2_ex.id, events.TASK_SUCCEEDED),
            (wf_ex.id, events.WORKFLOW_SUCCEEDED),
            (wf_ex.id, events.WORKFLOW_SUCCEEDED)
        ]

        self.assertTrue(self.publishers['wbhk'].publish.called)
        self.assertTrue(self.publishers['noop'].publish.called)
        self.assertListEqual(expected_order, EVENT_LOGS)

    def test_workbook_notify(self):
        wb_def = """
        version: '2.0'
        name: wb
        workflows:
          wf1:
            tasks:
              t1:
                workflow: wf2
                on-success:
                  - t2
              t2:
                action: std.noop
          wf2:
            tasks:
              t1:
                action: std.noop
        """

        wb_svc.create_workbook_v2(wb_def)

        notify_options = [{'type': 'webhook'}]
        params = {'notify': notify_options}

        wf1_ex = self.engine.start_workflow('wb.wf1', '', **params)

        self.await_workflow_success(wf1_ex.id)

        with db_api.transaction():
            wf1_ex = db_api.get_workflow_execution(wf1_ex.id)
            wf1_task_exs = wf1_ex.task_executions

            wf1_t1_ex = self._assert_single_item(wf1_task_exs, name='t1')
            wf1_t2_ex = self._assert_single_item(wf1_task_exs, name='t2')

            wf1_t1_act_exs = db_api.get_workflow_executions(
                task_execution_id=wf1_t1_ex.id
            )

            wf2_ex = wf1_t1_act_exs[0]
            wf2_task_exs = wf2_ex.task_executions

            wf2_t1_ex = self._assert_single_item(wf2_task_exs, name='t1')

        self.assertEqual(states.SUCCESS, wf1_ex.state)
        self.assertIsNone(wf1_ex.state_info)
        self.assertEqual(2, len(wf1_task_exs))

        self.assertEqual(states.SUCCESS, wf1_t1_ex.state)
        self.assertIsNone(wf1_t1_ex.state_info)
        self.assertEqual(states.SUCCESS, wf1_t2_ex.state)
        self.assertIsNone(wf1_t2_ex.state_info)

        self.assertEqual(1, len(wf1_t1_act_exs))

        self.assertEqual(states.SUCCESS, wf2_ex.state)
        self.assertIsNone(wf2_ex.state_info)
        self.assertEqual(1, len(wf2_task_exs))

        self.assertEqual(states.SUCCESS, wf2_t1_ex.state)
        self.assertIsNone(wf2_t1_ex.state_info)

        expected_order = [
            (wf1_ex.id, events.WORKFLOW_LAUNCHED),
            (wf1_t1_ex.id, events.TASK_LAUNCHED),
            (wf2_ex.id, events.WORKFLOW_LAUNCHED),
            (wf2_t1_ex.id, events.TASK_LAUNCHED),
            (wf2_t1_ex.id, events.TASK_SUCCEEDED),
            (wf2_ex.id, events.WORKFLOW_SUCCEEDED),
            (wf1_t1_ex.id, events.TASK_SUCCEEDED),
            (wf1_t2_ex.id, events.TASK_LAUNCHED),
            (wf1_t2_ex.id, events.TASK_SUCCEEDED),
            (wf1_ex.id, events.WORKFLOW_SUCCEEDED)
        ]

        self.assertTrue(self.publishers['wbhk'].publish.called)
        self.assertListEqual(expected_order, EVENT_LOGS)

    def test_notify_task_error(self):
        wf_def = """
        version: '2.0'
        wf:
          tasks:
            t1:
              action: std.noop
              on-success:
                - t2
            t2:
              action: std.fail
        """

        wf_svc.create_workflows(wf_def)

        notify_options = [{'type': 'webhook'}]
        params = {'notify': notify_options}

        wf_ex = self.engine.start_workflow('wf', '', **params)

        self.await_workflow_error(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
            task_exs = wf_ex.task_executions

        self.assertEqual(states.ERROR, wf_ex.state)
        self.assertIsNotNone(wf_ex.state_info)
        self.assertEqual(2, len(task_exs))

        t1_ex = self._assert_single_item(task_exs, name='t1')
        t2_ex = self._assert_single_item(task_exs, name='t2')

        self.assertEqual(states.SUCCESS, t1_ex.state)
        self.assertIsNone(t1_ex.state_info)
        self.assertEqual(states.ERROR, t2_ex.state)
        self.assertIsNotNone(t2_ex.state_info)

        expected_order = [
            (wf_ex.id, events.WORKFLOW_LAUNCHED),
            (t1_ex.id, events.TASK_LAUNCHED),
            (t1_ex.id, events.TASK_SUCCEEDED),
            (t2_ex.id, events.TASK_LAUNCHED),
            (t2_ex.id, events.TASK_FAILED),
            (wf_ex.id, events.WORKFLOW_FAILED)
        ]

        self.assertTrue(self.publishers['wbhk'].publish.called)
        self.assertListEqual(expected_order, EVENT_LOGS)

    def test_notify_task_transition_fail(self):
        wf_def = """
        version: '2.0'
        wf:
          tasks:
            t1:
              action: std.noop
              on-complete:
                - fail
        """

        wf_svc.create_workflows(wf_def)

        notify_options = [{'type': 'webhook'}]
        params = {'notify': notify_options}

        wf_ex = self.engine.start_workflow('wf', '', **params)

        self.await_workflow_error(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
            task_exs = wf_ex.task_executions

        self.assertEqual(states.ERROR, wf_ex.state)
        self.assertIsNone(wf_ex.state_info)
        self.assertEqual(1, len(task_exs))

        t1_ex = self._assert_single_item(task_exs, name='t1')

        self.assertEqual(states.SUCCESS, t1_ex.state)
        self.assertIsNone(t1_ex.state_info)

        expected_order = [
            (wf_ex.id, events.WORKFLOW_LAUNCHED),
            (t1_ex.id, events.TASK_LAUNCHED),
            (t1_ex.id, events.TASK_SUCCEEDED),
            (wf_ex.id, events.WORKFLOW_FAILED)
        ]

        self.assertTrue(self.publishers['wbhk'].publish.called)
        self.assertListEqual(expected_order, EVENT_LOGS)

    def test_notify_with_items_task(self):
        wf_def = """
        version: '2.0'
        wf:
          tasks:
            t1:
              with-items: i in <% list(range(0, 3)) %>
              action: std.noop
              on-success:
                - t2
            t2:
              action: std.noop
        """

        wf_svc.create_workflows(wf_def)

        notify_options = [{'type': 'webhook'}]
        params = {'notify': notify_options}

        wf_ex = self.engine.start_workflow('wf', '', **params)

        self.await_workflow_success(wf_ex.id)
        self._sleep(1)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
            task_exs = wf_ex.task_executions

        self.assertEqual(states.SUCCESS, wf_ex.state)
        self.assertIsNone(wf_ex.state_info)
        self.assertEqual(2, len(task_exs))

        t1_ex = self._assert_single_item(task_exs, name='t1')
        t2_ex = self._assert_single_item(task_exs, name='t2')

        self.assertEqual(states.SUCCESS, t1_ex.state)
        self.assertIsNone(t1_ex.state_info)
        self.assertEqual(states.SUCCESS, t2_ex.state)
        self.assertIsNone(t2_ex.state_info)

        expected_order = [
            (wf_ex.id, events.WORKFLOW_LAUNCHED),
            (t1_ex.id, events.TASK_LAUNCHED),
            (t1_ex.id, events.TASK_SUCCEEDED),
            (t2_ex.id, events.TASK_LAUNCHED),
            (t2_ex.id, events.TASK_SUCCEEDED),
            (wf_ex.id, events.WORKFLOW_SUCCEEDED)
        ]

        self.assertTrue(self.publishers['wbhk'].publish.called)
        self.assertListEqual(expected_order, EVENT_LOGS)

    def test_notify_pause_resume(self):
        wf_def = """
        version: '2.0'
        wf:
          tasks:
            t1:
              action: std.async_noop
              on-success:
                - t2
            t2:
              action: std.noop
        """

        wf_svc.create_workflows(wf_def)

        notify_options = [{'type': 'webhook'}]
        params = {'notify': notify_options}

        wf_ex = self.engine.start_workflow('wf', '', **params)

        self.await_workflow_running(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
            task_exs = wf_ex.task_executions

        t1_ex = self._assert_single_item(task_exs, name='t1')
        t1_act_exs = db_api.get_action_executions(task_execution_id=t1_ex.id)

        self.assertEqual(states.RUNNING, wf_ex.state)
        self.assertEqual(1, len(task_exs))
        self.assertEqual(states.RUNNING, t1_ex.state)
        self.assertEqual(1, len(t1_act_exs))
        self.assertEqual(states.RUNNING, t1_act_exs[0].state)

        # Pause the workflow.
        self.engine.pause_workflow(wf_ex.id)
        self.await_workflow_paused(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
            task_exs = wf_ex.task_executions

        t1_ex = self._assert_single_item(task_exs, name='t1')
        t1_act_exs = db_api.get_action_executions(task_execution_id=t1_ex.id)

        # Workflow is paused but the task is still running as expected.
        self.assertEqual(states.PAUSED, wf_ex.state)
        self.assertEqual(1, len(task_exs))
        self.assertEqual(states.RUNNING, t1_ex.state)
        self.assertEqual(1, len(t1_act_exs))
        self.assertEqual(states.RUNNING, t1_act_exs[0].state)

        expected_order = [
            (wf_ex.id, events.WORKFLOW_LAUNCHED),
            (t1_ex.id, events.TASK_LAUNCHED),
            (wf_ex.id, events.WORKFLOW_PAUSED)
        ]

        self.assertTrue(self.publishers['wbhk'].publish.called)
        self.assertListEqual(expected_order, EVENT_LOGS)

        # Complete action execution of task 1.
        self.engine.on_action_complete(
            t1_act_exs[0].id,
            ml_actions.Result(data={'result': 'foobar'})
        )

        self.await_workflow_paused(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
            task_exs = wf_ex.task_executions

        self.assertEqual(states.PAUSED, wf_ex.state)
        self.assertIsNone(wf_ex.state_info)
        self.assertEqual(1, len(task_exs))

        t1_ex = self._assert_single_item(task_exs, name='t1')

        self.assertEqual(states.SUCCESS, t1_ex.state)
        self.assertIsNone(t1_ex.state_info)

        expected_order = [
            (wf_ex.id, events.WORKFLOW_LAUNCHED),
            (t1_ex.id, events.TASK_LAUNCHED),
            (wf_ex.id, events.WORKFLOW_PAUSED),
            (t1_ex.id, events.TASK_SUCCEEDED)
        ]

        self.assertTrue(self.publishers['wbhk'].publish.called)
        self.assertListEqual(expected_order, EVENT_LOGS)

        # Resume the workflow.
        self.engine.resume_workflow(wf_ex.id)
        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
            task_exs = wf_ex.task_executions

        self.assertEqual(states.SUCCESS, wf_ex.state)
        self.assertIsNone(wf_ex.state_info)
        self.assertEqual(2, len(task_exs))

        t1_ex = self._assert_single_item(task_exs, name='t1')
        t2_ex = self._assert_single_item(task_exs, name='t2')

        self.assertEqual(states.SUCCESS, t1_ex.state)
        self.assertIsNone(t1_ex.state_info)
        self.assertEqual(states.SUCCESS, t2_ex.state)
        self.assertIsNone(t2_ex.state_info)

        expected_order = [
            (wf_ex.id, events.WORKFLOW_LAUNCHED),
            (t1_ex.id, events.TASK_LAUNCHED),
            (wf_ex.id, events.WORKFLOW_PAUSED),
            (t1_ex.id, events.TASK_SUCCEEDED),
            (wf_ex.id, events.WORKFLOW_RESUMED),
            (t2_ex.id, events.TASK_LAUNCHED),
            (t2_ex.id, events.TASK_SUCCEEDED),
            (wf_ex.id, events.WORKFLOW_SUCCEEDED)
        ]

        self.assertTrue(self.publishers['wbhk'].publish.called)
        self.assertListEqual(expected_order, EVENT_LOGS)

    def test_notify_pause_resume_task(self):
        wf_def = """
        version: '2.0'
        wf:
          tasks:
            t1:
              action: std.async_noop
              on-success:
                - t2
            t2:
              action: std.noop
        """

        wf_svc.create_workflows(wf_def)

        notify_options = [{'type': 'webhook'}]
        params = {'notify': notify_options}

        wf_ex = self.engine.start_workflow('wf', '', **params)

        self.await_workflow_running(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
            task_exs = wf_ex.task_executions

        t1_ex = self._assert_single_item(task_exs, name='t1')
        t1_act_exs = db_api.get_action_executions(task_execution_id=t1_ex.id)

        self.assertEqual(states.RUNNING, wf_ex.state)
        self.assertEqual(1, len(task_exs))
        self.assertEqual(states.RUNNING, t1_ex.state)
        self.assertEqual(1, len(t1_act_exs))
        self.assertEqual(states.RUNNING, t1_act_exs[0].state)

        # Pause the action execution of task 1.
        self.engine.on_action_update(t1_act_exs[0].id, states.PAUSED)
        self.await_workflow_paused(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
            task_exs = wf_ex.task_executions

        t1_ex = self._assert_single_item(task_exs, name='t1')
        t1_act_exs = db_api.get_action_executions(task_execution_id=t1_ex.id)

        self.assertEqual(states.PAUSED, wf_ex.state)
        self.assertEqual(1, len(task_exs))
        self.assertEqual(states.PAUSED, t1_ex.state)
        self.assertEqual(1, len(t1_act_exs))
        self.assertEqual(states.PAUSED, t1_act_exs[0].state)

        expected_order = [
            (wf_ex.id, events.WORKFLOW_LAUNCHED),
            (t1_ex.id, events.TASK_LAUNCHED),
            (t1_ex.id, events.TASK_PAUSED),
            (wf_ex.id, events.WORKFLOW_PAUSED)
        ]

        self.assertTrue(self.publishers['wbhk'].publish.called)
        self.assertListEqual(expected_order, EVENT_LOGS)

        # Resume the action execution of task 1.
        self.engine.on_action_update(t1_act_exs[0].id, states.RUNNING)
        self.await_task_running(t1_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
            task_exs = wf_ex.task_executions

        t1_ex = self._assert_single_item(task_exs, name='t1')
        t1_act_exs = db_api.get_action_executions(task_execution_id=t1_ex.id)

        self.assertEqual(states.RUNNING, wf_ex.state)
        self.assertEqual(1, len(task_exs))
        self.assertEqual(states.RUNNING, t1_ex.state)
        self.assertEqual(1, len(t1_act_exs))
        self.assertEqual(states.RUNNING, t1_act_exs[0].state)

        # Complete action execution of task 1.
        self.engine.on_action_complete(
            t1_act_exs[0].id,
            ml_actions.Result(data={'result': 'foobar'})
        )

        # Wait for the workflow execution to complete.
        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
            task_exs = wf_ex.task_executions

        self.assertEqual(states.SUCCESS, wf_ex.state)
        self.assertIsNone(wf_ex.state_info)
        self.assertEqual(2, len(task_exs))

        t1_ex = self._assert_single_item(task_exs, name='t1')
        t2_ex = self._assert_single_item(task_exs, name='t2')

        self.assertEqual(states.SUCCESS, t1_ex.state)
        self.assertIsNone(t1_ex.state_info)
        self.assertEqual(states.SUCCESS, t2_ex.state)
        self.assertIsNone(t2_ex.state_info)

        # TASK_RESUMED comes before WORKFLOW_RESUMED because
        # this test resumed the workflow with on_action_update.
        expected_order = [
            (wf_ex.id, events.WORKFLOW_LAUNCHED),
            (t1_ex.id, events.TASK_LAUNCHED),
            (t1_ex.id, events.TASK_PAUSED),
            (wf_ex.id, events.WORKFLOW_PAUSED),
            (t1_ex.id, events.TASK_RESUMED),
            (wf_ex.id, events.WORKFLOW_RESUMED),
            (t1_ex.id, events.TASK_SUCCEEDED),
            (t2_ex.id, events.TASK_LAUNCHED),
            (t2_ex.id, events.TASK_SUCCEEDED),
            (wf_ex.id, events.WORKFLOW_SUCCEEDED)
        ]

        self.assertTrue(self.publishers['wbhk'].publish.called)
        self.assertListEqual(expected_order, EVENT_LOGS)

    def test_notify_cancel(self):
        wf_def = """
        version: '2.0'
        wf:
          tasks:
            t1:
              action: std.async_noop
              on-success:
                - t2
            t2:
              action: std.noop
        """

        wf_svc.create_workflows(wf_def)

        notify_options = [{'type': 'webhook'}]
        params = {'notify': notify_options}

        wf_ex = self.engine.start_workflow('wf', '', **params)

        self.await_workflow_running(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
            task_exs = wf_ex.task_executions

        t1_ex = self._assert_single_item(task_exs, name='t1')
        t1_act_exs = db_api.get_action_executions(task_execution_id=t1_ex.id)

        self.assertEqual(states.RUNNING, wf_ex.state)
        self.assertEqual(1, len(task_exs))
        self.assertEqual(states.RUNNING, t1_ex.state)
        self.assertEqual(1, len(t1_act_exs))
        self.assertEqual(states.RUNNING, t1_act_exs[0].state)

        # Cancel the workflow.
        self.engine.stop_workflow(wf_ex.id, states.CANCELLED)
        self.await_workflow_cancelled(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
            task_exs = wf_ex.task_executions

        t1_ex = self._assert_single_item(task_exs, name='t1')
        t1_act_exs = db_api.get_action_executions(task_execution_id=t1_ex.id)

        # Workflow is cancelled but the task is still running as expected.
        self.assertEqual(states.CANCELLED, wf_ex.state)
        self.assertEqual(1, len(task_exs))
        self.assertEqual(states.RUNNING, t1_ex.state)
        self.assertEqual(1, len(t1_act_exs))
        self.assertEqual(states.RUNNING, t1_act_exs[0].state)

        expected_order = [
            (wf_ex.id, events.WORKFLOW_LAUNCHED),
            (t1_ex.id, events.TASK_LAUNCHED),
            (wf_ex.id, events.WORKFLOW_CANCELLED)
        ]

        self.assertTrue(self.publishers['wbhk'].publish.called)
        self.assertListEqual(expected_order, EVENT_LOGS)

        # Complete action execution of task 1.
        self.engine.on_action_complete(
            t1_act_exs[0].id,
            ml_actions.Result(data={'result': 'foobar'})
        )

        self.await_workflow_cancelled(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
            task_exs = wf_ex.task_executions

        self.assertEqual(states.CANCELLED, wf_ex.state)
        self.assertIsNone(wf_ex.state_info)
        self.assertEqual(1, len(task_exs))

        t1_ex = self._assert_single_item(task_exs, name='t1')

        self.assertEqual(states.SUCCESS, t1_ex.state)
        self.assertIsNone(t1_ex.state_info)

        expected_order = [
            (wf_ex.id, events.WORKFLOW_LAUNCHED),
            (t1_ex.id, events.TASK_LAUNCHED),
            (wf_ex.id, events.WORKFLOW_CANCELLED),
            (t1_ex.id, events.TASK_SUCCEEDED)
        ]

        self.assertTrue(self.publishers['wbhk'].publish.called)
        self.assertListEqual(expected_order, EVENT_LOGS)

    def test_notify_cancel_task(self):
        wf_def = """
        version: '2.0'
        wf:
          tasks:
            t1:
              action: std.async_noop
              on-success:
                - t2
            t2:
              action: std.noop
        """

        wf_svc.create_workflows(wf_def)

        notify_options = [{'type': 'webhook'}]
        params = {'notify': notify_options}

        wf_ex = self.engine.start_workflow('wf', '', **params)

        self.await_workflow_running(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
            task_exs = wf_ex.task_executions

        t1_ex = self._assert_single_item(task_exs, name='t1')
        t1_act_exs = db_api.get_action_executions(task_execution_id=t1_ex.id)

        self.assertEqual(states.RUNNING, wf_ex.state)
        self.assertEqual(1, len(task_exs))
        self.assertEqual(states.RUNNING, t1_ex.state)
        self.assertEqual(1, len(t1_act_exs))
        self.assertEqual(states.RUNNING, t1_act_exs[0].state)

        # Cancel the action execution of task 1.
        self.engine.on_action_update(t1_act_exs[0].id, states.CANCELLED)
        self.await_workflow_cancelled(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
            task_exs = wf_ex.task_executions

        t1_ex = self._assert_single_item(task_exs, name='t1')
        t1_act_exs = db_api.get_action_executions(task_execution_id=t1_ex.id)

        self.assertEqual(states.CANCELLED, wf_ex.state)
        self.assertEqual(1, len(task_exs))
        self.assertEqual(states.CANCELLED, t1_ex.state)
        self.assertEqual(1, len(t1_act_exs))
        self.assertEqual(states.CANCELLED, t1_act_exs[0].state)

        expected_order = [
            (wf_ex.id, events.WORKFLOW_LAUNCHED),
            (t1_ex.id, events.TASK_LAUNCHED),
            (t1_ex.id, events.TASK_CANCELLED),
            (wf_ex.id, events.WORKFLOW_CANCELLED)
        ]

        self.assertTrue(self.publishers['wbhk'].publish.called)
        self.assertListEqual(expected_order, EVENT_LOGS)
