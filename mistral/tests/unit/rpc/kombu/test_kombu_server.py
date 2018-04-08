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

import futurist
from mistral import context
from mistral import exceptions as exc
from mistral.tests.unit.rpc.kombu import base
from mistral.tests.unit.rpc.kombu import fake_kombu

import mock
import socket
from stevedore import driver

with mock.patch.dict('sys.modules', kombu=fake_kombu):
    from mistral.rpc.kombu import kombu_server


class TestException(exc.MistralError):
    pass


class KombuServerTestCase(base.KombuTestCase):

    def setUp(self):
        super(KombuServerTestCase, self).setUp()

        self.conf = mock.MagicMock()
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
            body={'body': '"body"'},
            exchange='openstack',
            routing_key=reply_to,
            correlation_id=corr_id,
            type=type,
            serializer='json'
        )

    def test_run_launch_successfully(self):
        acquire_mock = mock.MagicMock()
        acquire_mock.drain_events.side_effect = TestException()
        fake_kombu.connection.acquire.return_value = acquire_mock

        self.assertRaises(TestException, self.server._run, 'blocking')
        self.assertTrue(self.server.is_running)

    def test_run_launch_successfully_than_stop(self):

        def side_effect(*args, **kwargs):
            self.assertTrue(self.server.is_running)
            raise KeyboardInterrupt

        acquire_mock = mock.MagicMock()
        acquire_mock.drain_events.side_effect = side_effect
        fake_kombu.connection.acquire.return_value = acquire_mock

        self.server._run('blocking')
        self.assertFalse(self.server.is_running)
        self.assertEqual(self.server._sleep_time, 1)

    def test_run_socket_error_reconnect(self):

        def side_effect(*args, **kwargs):
            if acquire_mock.drain_events.call_count == 1:
                raise socket.error()
            raise TestException()

        acquire_mock = mock.MagicMock()
        acquire_mock.drain_events.side_effect = side_effect
        fake_kombu.connection.acquire.return_value = acquire_mock

        self.assertRaises(TestException, self.server._run, 'blocking')
        self.assertEqual(self.server._sleep_time, 1)

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
            self.server._run,
            'blocking'
        )
        self.assertTrue(self.server.is_running)

    def test_run_keyboard_interrupt_not_running(self):
        acquire_mock = mock.MagicMock()
        acquire_mock.drain_events.side_effect = KeyboardInterrupt()
        fake_kombu.connection.acquire.return_value = acquire_mock

        self.assertIsNone(self.server.run())
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
    @mock.patch('mistral.context.MistralContext.from_dict')
    def test__on_message_is_async(self, mock_get_context, get_rpc_method,
                                  publish_message):
        result = 'result'
        request = {
            'async': True,
            'rpc_ctx': {},
            'rpc_method': 'found_method',
            'arguments': self.server._serialize_message({
                'a': 1,
                'b': 2
            })
        }

        message = mock.MagicMock()
        message.properties = {
            'reply_to': None,
            'correlation_id': None
        }
        message.delivery_info.get.return_value = False

        rpc_method = mock.MagicMock(return_value=result)
        get_rpc_method.return_value = rpc_method

        ctx = context.MistralContext()
        mock_get_context.return_value = ctx

        self.server._on_message(request, message)

        rpc_method.assert_called_once_with(
            rpc_ctx=ctx,
            a=1,
            b=2
        )
        self.assertEqual(publish_message.call_count, 0)

    @mock.patch.object(kombu_server.KombuRPCServer, 'publish_message')
    @mock.patch.object(kombu_server.KombuRPCServer, '_get_rpc_method')
    @mock.patch('mistral.context.MistralContext.from_dict')
    def test__on_message_is_sync(self, mock_get_context, get_rpc_method,
                                 publish_message):
        result = 'result'
        request = {
            'async': False,
            'rpc_ctx': {},
            'rpc_method': 'found_method',
            'arguments': self.server._serialize_message({
                'a': 1,
                'b': 2
            })
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

        ctx = context.MistralContext()
        mock_get_context.return_value = ctx

        self.server._on_message(request, message)

        rpc_method.assert_called_once_with(
            rpc_ctx=ctx,
            a=1,
            b=2
        )
        publish_message.assert_called_once_with(
            result,
            reply_to,
            correlation_id
        )

    def test__prepare_worker(self):
        self.server._prepare_worker('blocking')
        self.assertEqual(
            futurist.SynchronousExecutor,
            type(self.server._worker)
        )

        self.server._prepare_worker('threading')
        self.assertEqual(
            futurist.ThreadPoolExecutor,
            type(self.server._worker)
        )

        self.server._prepare_worker('eventlet')
        self.assertEqual(
            futurist.GreenThreadPoolExecutor,
            type(self.server._worker)
        )

    @mock.patch('stevedore.driver.DriverManager')
    def test__prepare_worker_no_valid_executor(self, driver_manager_mock):

        driver_manager_mock.side_effect = driver.NoMatches()

        self.assertRaises(
            driver.NoMatches,
            self.server._prepare_worker,
            'non_valid_executor'
        )
