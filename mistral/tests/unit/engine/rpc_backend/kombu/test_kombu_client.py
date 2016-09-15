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
from mistral import utils

import mock
import socket

with mock.patch.dict('sys.modules', kombu=fake_kombu):
    from mistral.engine.rpc_backend.kombu import kombu_client


class TestException(exc.MistralException):
    pass


class KombuClientTestCase(base.KombuTestCase):

    _RESPONSE = "response"

    def setUp(self):
        super(KombuClientTestCase, self).setUp()
        conf = mock.MagicMock()

        self.client = kombu_client.KombuRPCClient(conf)
        self.ctx = type('context', (object,), {'to_dict': lambda self: {}})()

    @mock.patch.object(utils, 'set_thread_local', mock.MagicMock())
    @mock.patch.object(utils, 'get_thread_local')
    def test_sync_call_result_get(self, get_thread_local):

        def side_effect(var_name):
            if var_name == kombu_client.IS_RECEIVED:
                return True
            elif var_name == kombu_client.RESULT:
                return self._RESPONSE

        get_thread_local.side_effect = side_effect

        response = self.client.sync_call(self.ctx, 'method')
        self.assertEqual(response, self._RESPONSE)
        # check if consumer.consume was called once
        self.assertEqual(self.client.consumer.consume.call_count, 1)

    @mock.patch.object(utils, 'set_thread_local', mock.MagicMock())
    @mock.patch.object(utils, 'get_thread_local')
    def test_sync_call_result_not_get(self, get_thread_local):

        def side_effect(var_name):
            if var_name == kombu_client.IS_RECEIVED:
                return False
            elif var_name == kombu_client.RESULT:
                return self._RESPONSE

        get_thread_local.side_effect = side_effect

        self.client.conn.drain_events = mock.MagicMock(
            side_effect=socket.timeout
        )

        self.assertRaises(
            exc.MistralException,
            self.client.sync_call,
            self.ctx,
            'method_not_found'
        )
        # Check if consumer.consume was called once.
        self.assertEqual(self.client.consumer.consume.call_count, 1)

    @mock.patch.object(utils, 'set_thread_local', mock.MagicMock())
    @mock.patch.object(utils, 'get_thread_local')
    def test_sync_call_result_type_error(self, get_thread_local):

        def side_effect(var_name):
            if var_name == kombu_client.IS_RECEIVED:
                return True
            elif var_name == kombu_client.RESULT:
                return TestException()
            elif var_name == kombu_client.TYPE:
                return 'error'

        get_thread_local.side_effect = side_effect

        self.client.conn.drain_events = mock.MagicMock()

        self.assertRaises(
            TestException,
            self.client.sync_call,
            self.ctx,
            'method'
        )
        # check if consumer.consume was called once
        self.assertEqual(self.client.consumer.consume.call_count, 1)

    @mock.patch.object(utils, 'set_thread_local', mock.MagicMock())
    @mock.patch.object(utils, 'get_thread_local')
    def test_async_call(self, get_thread_local):

        def side_effect(var_name):
            if var_name == kombu_client.IS_RECEIVED:
                return True
            elif var_name == kombu_client.RESULT:
                return self._RESPONSE

        get_thread_local.side_effect = side_effect

        response = self.client.async_call(self.ctx, 'method')
        self.assertEqual(response, None)
        # check if consumer.consume was called once
        self.assertEqual(self.client.consumer.consume.call_count, 1)

    def test__on_response_message_ack_fail(self):
        message = mock.MagicMock()
        message.ack.side_effect = Exception('Test Exception')
        response = 'response'

        kombu_client.LOG = mock.MagicMock()

        self.client._on_response(response, message)
        self.assertEqual(kombu_client.LOG.debug.call_count, 1)
        self.assertEqual(kombu_client.LOG.exception.call_count, 1)

    @mock.patch.object(utils, 'get_thread_local', mock.MagicMock(
        return_value=False
    ))
    def test__on_response_message_ack_ok_corr_id_not_match(self):
        message = mock.MagicMock()
        message.properties = mock.MagicMock()
        message.properties.__getitem__ = lambda *args, **kwargs: True
        response = 'response'

        kombu_client.LOG = mock.MagicMock()

        self.client._on_response(response, message)
        self.assertEqual(kombu_client.LOG.debug.call_count, 2)
        self.assertEqual(kombu_client.LOG.exception.call_count, 0)

    @mock.patch.object(utils, 'set_thread_local')
    @mock.patch.object(utils, 'get_thread_local', mock.MagicMock(
        return_value=True
    ))
    def test__on_response_message_ack_ok_messsage_type_error(
            self,
            set_thread_local
    ):
        message = mock.MagicMock()
        message.properties = mock.MagicMock()
        message.properties.__getitem__ = lambda *args, **kwargs: True
        message.properties.get.return_value = 'error'
        response = TestException('response')

        kombu_client.LOG = mock.MagicMock()

        self.client._on_response(response, message)

        self.assertEqual(kombu_client.LOG.debug.call_count, 2)
        self.assertEqual(kombu_client.LOG.exception.call_count, 0)
        self.assertEqual(set_thread_local.call_count, 3)

    @mock.patch.object(utils, 'set_thread_local')
    @mock.patch.object(utils, 'get_thread_local', mock.MagicMock(
        return_value=True
    ))
    def test__on_response_message_ack_ok(self, set_thread_local):

        message = mock.MagicMock()
        message.properties = mock.MagicMock()
        message.properties.__getitem__ = lambda *args, **kwargs: True
        response = 'response'

        kombu_client.LOG = mock.MagicMock()

        self.client._on_response(response, message)

        self.assertEqual(kombu_client.LOG.debug.call_count, 2)
        self.assertEqual(kombu_client.LOG.exception.call_count, 0)
        self.assertEqual(set_thread_local.call_count, 2)
