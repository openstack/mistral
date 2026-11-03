# Copyright 2026 - Fivetime, Ltd.
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

from mistral import messaging
from mistral.tests.unit import base

CONF = cfg.CONF


class StartListenerTest(base.BaseTest):

    @mock.patch.object(messaging.listener, 'get_notification_listener')
    @mock.patch('oslo_messaging.notify.get_notification_transport')
    def test_start_listener(self, get_transport, get_listener):
        result = messaging.start_listener(
            CONF, 'cinder', 'versioned_notifications', []
        )

        get_transport.assert_called_once_with(CONF)

        args, kwargs = get_listener.call_args
        self.assertEqual(get_transport.return_value, args[0])
        self.assertEqual(
            [('cinder', 'versioned_notifications')],
            [(t.exchange, t.topic) for t in args[1]]
        )
        self.assertEqual(messaging.get_pool_name('cinder'), kwargs['pool'])
        self.assertEqual(get_listener.return_value, result)
        result.start.assert_called_once_with()


class NotificationEndpointTest(base.BaseTest):

    def _match(self, event_types, event_type):
        endpoint_cls = type(
            'Endpoint',
            (messaging.NotificationEndpoint,),
            {'event_types': event_types}
        )
        rule = endpoint_cls(mock.Mock()).filter_rule

        return rule.match({}, 'publisher', event_type, {}, {})

    def test_filter_matches_exact_event(self):
        events = ['compute.instance.create.end', 'image.upload']

        self.assertTrue(self._match(events, 'compute.instance.create.end'))
        self.assertTrue(self._match(events, 'image.upload'))

    def test_filter_dot_is_not_a_wildcard(self):
        events = ['compute.instance.create.end']

        self.assertFalse(self._match(events, 'computeXinstance.create.end'))
        self.assertFalse(
            self._match(events, 'compute.instance.create.end.extra')
        )
        self.assertFalse(self._match(events, 'compute.instance.create.end\n'))

    def test_filter_escapes_regex_metacharacters(self):
        self.assertFalse(self._match(['(a+)+$'], 'aaaa'))
        self.assertTrue(self._match(['(a+)+$'], '(a+)+$'))
        self.assertFalse(self._match(['.*'], 'image.upload'))
