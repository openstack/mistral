# Copyright (c) 2016 Intel Corporation
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from mistral import exceptions as exc
from mistral.tests.unit.engine.rpc_backend.kombu import base
from mistral.tests.unit.engine.rpc_backend.kombu import fake_kombu

import mock
import socket

with mock.patch.dict('sys.modules', kombu=fake_kombu):
    from mistral.engine.rpc_backend.kombu import kombu_server


class TestException(exc.MistralError):
    pass


class KombuServerTestCase(base.KombuTestCase):

    def setUp(self):
        super(KombuServerTestCase, self).setUp()

        self.conf = {}
        self.conf['exchange'] = 'test_exchange'
        self.server = kombu_server.KombuRPCServer(self.conf)
        self.ctx = type('context', (object,), {'to_dict': lambda self: {}})()

    def test_is_running_is_running(self):
        self.server._running.set()
        self.assertTrue(self.server.is_running)

    def test_is_running_is_not_running(self):
        self.server._running.clear()
        self.assertFalse(self.server.is_running)

    def test_stop(self):
        self.server.stop()
        self.assertFalse(self.server.is_running)

    def test_publish_message(self):
        body = 'body'
        reply_to = 'reply_to'
        corr_id = 'corr_id'
        type = 'type'

        acquire_mock = mock.MagicMock()
        fake_kombu.producer.acquire.return_value = acquire_mock

        enter_mock = mock.MagicMock()
        acquire_mock.__enter__.return_value = enter_mock

        self.server.publish_message(body, reply_to, corr_id, type)
        enter_mock.publish.assert_called_once_with(
            body=body,
            exchange=self.conf['exchange'],
            routing_key=reply_to,
            correlation_id=corr_id,
            type=type,
            serializer='mistral_serialization'
        )

    def test_run_launch_successfully(self):
        acquire_mock = mock.MagicMock()
        acquire_mock.drain_events.side_effect = TestException()
        fake_kombu.connection.acquire.return_value = acquire_mock

        self.assertRaises(TestException, self.server.run)
        self.assertTrue(self.server.is_running)

    def test_run_launch_successfully_than_stop(self):

        def side_effect(*args, **kwargs):
            self.assertTrue(self.server.is_running)
            self.server.stop()

        acquire_mock = mock.MagicMock()
        acquire_mock.drain_events.side_effect = side_effect
        fake_kombu.connection.acquire.return_value = acquire_mock

        self.server.run()
        self.assertFalse(self.server.is_running)

    def test_run_raise_mistral_exception(self):
        acquire_mock = mock.MagicMock()
        acquire_mock.drain_events.side_effect = socket.error()
        fake_kombu.connection.acquire.return_value = acquire_mock

        self.assertRaises(exc.MistralException, self.server.run)

    def test_run_socket_timeout_still_running(self):

        def side_effect(*args, **kwargs):
            if acquire_mock.drain_events.call_count == 0:
                raise socket.timeout()
            raise TestException()

        acquire_mock = mock.MagicMock()
        acquire_mock.drain_events.side_effect = side_effect
        fake_kombu.connection.acquire.return_value = acquire_mock

        self.assertRaises(
            TestException,
            self.server.run
        )
        self.assertTrue(self.server.is_running)

    def test_run_keyboard_interrupt_not_running(self):
        acquire_mock = mock.MagicMock()
        acquire_mock.drain_events.side_effect = KeyboardInterrupt()
        fake_kombu.connection.acquire.return_value = acquire_mock

        self.assertEqual(self.server.run(), None)
        self.assertFalse(self.server.is_running)

    @mock.patch.object(
        kombu_server.KombuRPCServer,
        '_on_message',
        mock.MagicMock()
    )
    @mock.patch.object(kombu_server.KombuRPCServer, 'publish_message')
    def test__on_message_safe_message_processing_ok(self, publish_message):
        message = mock.MagicMock()

        self.server._on_message_safe(None, message)

        self.assertEqual(message.ack.call_count, 1)
        self.assertEqual(publish_message.call_count, 0)

    @mock.patch.object(kombu_server.KombuRPCServer, '_on_message')
    @mock.patch.object(kombu_server.KombuRPCServer, 'publish_message')
    def test__on_message_safe_message_processing_raise(
            self,
            publish_message,
            _on_message
    ):
        reply_to = 'reply_to'
        correlation_id = 'corr_id'
        message = mock.MagicMock()
        message.properties = {
            'reply_to': reply_to,
            'correlation_id': correlation_id
        }

        test_exception = TestException()
        _on_message.side_effect = test_exception

        self.server._on_message_safe(None, message)

        self.assertEqual(message.ack.call_count, 1)
        self.assertEqual(publish_message.call_count, 1)

    @mock.patch.object(
        kombu_server.KombuRPCServer,
        '_get_rpc_method',
        mock.MagicMock(return_value=None)
    )
    def test__on_message_rpc_method_not_found(self):
        request = {
            'rpc_ctx': {},
            'rpc_method': 'not_found_method',
            'arguments': {}
        }

        message = mock.MagicMock()
        message.properties = {
            'reply_to': None,
            'correlation_id': None
        }

        self.assertRaises(
            exc.MistralException,
            self.server._on_message,
            request,
            message
        )

    @mock.patch.object(kombu_server.KombuRPCServer, 'publish_message')
    @mock.patch.object(kombu_server.KombuRPCServer, '_get_rpc_method')
    @mock.patch('mistral.context.MistralContext')
    def test__on_message_is_async(self, mistral_context, get_rpc_method,
                                  publish_message):
        result = 'result'
        request = {
            'async': True,
            'rpc_ctx': {},
            'rpc_method': 'found_method',
            'arguments': {
                'a': 1,
                'b': 2
            }
        }

        message = mock.MagicMock()
        message.properties = {
            'reply_to': None,
            'correlation_id': None
        }
        message.delivery_info.get.return_value = False

        rpc_method = mock.MagicMock(return_value=result)
        get_rpc_method.return_value = rpc_method

        self.server._on_message(request, message)
        rpc_method.assert_called_once_with(
            rpc_ctx=mistral_context(),
            a=1,
            b=2
        )
        self.assertEqual(publish_message.call_count, 0)

    @mock.patch.object(kombu_server.KombuRPCServer, 'publish_message')
    @mock.patch.object(kombu_server.KombuRPCServer, '_get_rpc_method')
    @mock.patch('mistral.context.MistralContext')
    def test__on_message_is_sync(self, mistral_context, get_rpc_method,
                                 publish_message):
        result = 'result'
        request = {
            'async': False,
            'rpc_ctx': {},
            'rpc_method': 'found_method',
            'arguments': {
                'a': 1,
                'b': 2
            }
        }

        reply_to = 'reply_to'
        correlation_id = 'corr_id'
        message = mock.MagicMock()
        message.properties = {
            'reply_to': reply_to,
            'correlation_id': correlation_id
        }
        message.delivery_info.get.return_value = False

        rpc_method = mock.MagicMock(return_value=result)
        get_rpc_method.return_value = rpc_method

        self.server._on_message(request, message)
        rpc_method.assert_called_once_with(
            rpc_ctx=mistral_context(),
            a=1,
            b=2
        )
        publish_message.assert_called_once_with(
            result,
            reply_to,
            correlation_id
        )
