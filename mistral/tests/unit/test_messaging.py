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
