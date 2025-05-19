# Copyright 2018 - Extreme Networks, Inc.
# Modified in 2025 by NetCracker Technology Corp.
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

from unittest import mock

from oslo_config import cfg
from stevedore import exception as sd_exc

from mistral import context
from mistral.db.v2 import api as db_api
from mistral.notifiers import base as notif
from mistral.notifiers import default_notifier as d_notif
from mistral.notifiers import notification_events as events
from mistral.notifiers import remote_notifier as r_notif
from mistral.services import workflows as wf_svc
from mistral.tests.unit import base as test_base
from mistral.tests.unit.notifiers import base
from mistral.workflow import states
import requests

# Use the set_default method to set value otherwise in certain test cases
# the change in value is not permanent.
cfg.CONF.set_default('auth_enable', False, group='pecan')

EVENT_LOGS = []


def publisher_process(ctx, ex_id, data, event, timestamp, **kwargs):
    if not isinstance(ctx, context.MistralContext):
        raise TypeError('ctx is not type of MistralContext.')

    EVENT_LOGS.append((ex_id, event))


def notifier_process(ex_id, data, event, timestamp, publishers):
    EVENT_LOGS.append((ex_id, event))


class ServerPluginTest(base.NotifierTestCase):
    def tearDown(self):
        super(ServerPluginTest, self).tearDown()

        notif.cleanup()

    def test_get_bad_notifier(self):
        self.assertRaises(sd_exc.NoMatches, notif.get_notifier, 'foobar')


@mock.patch.object(
    r_notif.RemoteNotifier,
    'notify',
    mock.MagicMock(return_value=None)
)
class LocalNotifServerTest(base.NotifierTestCase):
    @classmethod
    def setUpClass(cls):
        super(LocalNotifServerTest, cls).setUpClass()

        cfg.CONF.set_default('type', 'local', group='notifier')

    @classmethod
    def tearDownClass(cls):
        cfg.CONF.set_default('type', 'remote', group='notifier')

        super(LocalNotifServerTest, cls).tearDownClass()

    def setUp(self):
        super(LocalNotifServerTest, self).setUp()

        self.publisher = notif.get_notification_publisher('webhook')
        self.publisher.publish = mock.MagicMock(side_effect=publisher_process)
        self.publisher.publish.reset_mock()

        del EVENT_LOGS[:]

    def tearDown(self):
        super(LocalNotifServerTest, self).tearDown()

        notif.cleanup()

    def test_get_notifier(self):
        notifier = notif.get_notifier(cfg.CONF.notifier.type)

        self.assertEqual('local', cfg.CONF.notifier.type)
        self.assertIsInstance(notifier, d_notif.DefaultNotifier)

    def test_notify(self):
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

        notif_options = [{'type': 'webhook'}]

        wf_ex = self.engine.start_workflow(
            'wf',
            '',
            wf_input={},
            notify=notif_options
        )

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
            (wf_ex.id, events.WORKFLOW_SUCCEEDED),
            (t2_ex.id, events.TASK_SUCCEEDED)
        ]

        self.assertFalse(r_notif.RemoteNotifier.notify.called)
        self.assertListEqual(expected_order, EVENT_LOGS)


@mock.patch.object(
    r_notif.RemoteNotifier,
    'notify',
    mock.MagicMock(side_effect=notifier_process)
)
class RemoteNotifServerTest(base.NotifierTestCase):
    @classmethod
    def setUpClass(cls):
        super(RemoteNotifServerTest, cls).setUpClass()

        cfg.CONF.set_default('type', 'remote', group='notifier')

    def setUp(self):
        super(RemoteNotifServerTest, self).setUp()

        del EVENT_LOGS[:]

    def tearDown(self):
        super(RemoteNotifServerTest, self).tearDown()

        notif.cleanup()

    def test_get_notifier(self):
        notifier = notif.get_notifier(cfg.CONF.notifier.type)

        self.assertEqual('remote', cfg.CONF.notifier.type)
        self.assertIsInstance(notifier, r_notif.RemoteNotifier)

    def test_notify(self):
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

        notif_options = [{'type': 'foobar'}]

        wf_ex = self.engine.start_workflow(
            'wf',
            '',
            wf_input={},
            notify=notif_options
        )

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

        self.assertTrue(r_notif.RemoteNotifier.notify.called)
        self.assertListEqual(expected_order, EVENT_LOGS)


@mock.patch.object(
    r_notif.RemoteNotifier,
    'notify',
    mock.MagicMock(return_value=None)
)
class HeadersPropagationTest(base.NotifierTestCase):

    wf_def = """
        version: '2.0'
        wf:
          tasks:
            t1:
              action: std.noop
        """
    params = {
        "headers": {
            "Header1": "qwerty",
            "Header2": "123",
            "Header3": "wow",
        }
    }
    expected_headers = {'Header1': "qwerty", 'Header2': "123",
                        'Header3': "wow"}

    @classmethod
    def setUpClass(cls):
        super(HeadersPropagationTest, cls).setUpClass()

        cfg.CONF.set_default('type', 'local', group='notifier')

    @classmethod
    def tearDownClass(cls):
        cfg.CONF.set_default('type', 'remote', group='notifier')

        super(HeadersPropagationTest, cls).tearDownClass()

    def setUp(self):
        super(HeadersPropagationTest, self).setUp()

        self.publisher = notif.get_notification_publisher('webhook')

        del EVENT_LOGS[:]

    def tearDown(self):
        super(HeadersPropagationTest, self).tearDown()

        notif.cleanup()

    @mock.patch.object(d_notif.DefaultNotifier, 'notify')
    def test_headers_propagation_for_workflow_and_task(self, mock_notify):

        mock_notify.side_effect = notifier_process
        notif_options = [{'type': 'webhook'}]
        wf_svc.create_workflows(self.wf_def)
        wf_ex = self.engine.start_workflow(
            'wf',
            '',
            wf_input={},
            notify=notif_options,
            **self.params
        )
        self.assertFalse(d_notif.DefaultNotifier.notify.call_args)

        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.SUCCESS, wf_ex.state)
        self.assertIsNone(wf_ex.state_info)

        call_args_list = mock_notify.call_args_list
        wf_has_headers = False
        task_has_headers = False
        for args in call_args_list:
            _, data, _, _, _ = args[0]
            if 'name' in data and 'headers' in data:
                if data['name'] == 'wf' and \
                        data['headers'] == self.expected_headers:
                    wf_has_headers = True
                if data['name'] == 't1' and \
                        data['headers'] == self.expected_headers:
                    task_has_headers = True

        self.assertTrue(wf_has_headers)
        self.assertTrue(task_has_headers)

        self.assertFalse(r_notif.RemoteNotifier.notify.call_args)
        self.assertFalse(r_notif.RemoteNotifier.notify.called)

    @mock.patch.object(
        requests, 'post',
        mock.MagicMock(return_value=test_base.FakeHTTPResponse('', 200, 'OK')))
    def test_headers_propagation_webhook_publish(self):

        notif_options = [{'type': 'webhook', "url": "http://example.com"}]

        wf_svc.create_workflows(self.wf_def)

        wf_ex = self.engine.start_workflow(
            'wf',
            '',
            wf_input={},
            notify=notif_options,
            **self.params
        )

        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.SUCCESS, wf_ex.state)
        self.assertIsNone(wf_ex.state_info)
        self.assertTrue(
            requests.post.call_args[1]['headers'] == self.expected_headers)
