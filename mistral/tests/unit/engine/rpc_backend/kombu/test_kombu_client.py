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
from six import moves

with mock.patch.dict('sys.modules', kombu=fake_kombu):
    from mistral.engine.rpc_backend.kombu import base as kombu_base
    from mistral.engine.rpc_backend.kombu import kombu_client


class TestException(exc.MistralException):
    pass


class KombuClientTestCase(base.KombuTestCase):

    _RESPONSE = "response"

    def setUp(self):
        super(KombuClientTestCase, self).setUp()
        conf = mock.MagicMock()

        kombu_client.kombu_listener.KombuRPCListener = mock.MagicMock()
        self.client = kombu_client.KombuRPCClient(conf)
        self.ctx = type('context', (object,), {'to_dict': lambda self: {}})()

    def test_sync_call_result_get(self):
        self.client._listener.get_result = mock.MagicMock(
            return_value={
                kombu_base.TYPE: None,
                kombu_base.RESULT: self.client._serialize_message({
                    'body': self._RESPONSE
                })
            }
        )
        response = self.client.sync_call(self.ctx, 'method')

        self.assertEqual(response, self._RESPONSE)

    def test_sync_call_result_not_get(self):
        self.client._listener.get_result = mock.MagicMock(
            side_effect=moves.queue.Empty
        )

        self.assertRaises(
            exc.MistralException,
            self.client.sync_call,
            self.ctx,
            'method_not_found'
        )

    def test_sync_call_result_type_error(self):

        def side_effect(*args, **kwargs):
            result = {}
            result[kombu_base.TYPE] = 'error'
            result[kombu_base.RESULT] = TestException()
            return result

        self.client._wait_for_result = mock.MagicMock(side_effect=side_effect)

        self.assertRaises(
            TestException,
            self.client.sync_call,
            self.ctx,
            'method'
        )

    def test_async_call(self):
        response = self.client.async_call(self.ctx, 'method')
        self.assertIsNone(response)
