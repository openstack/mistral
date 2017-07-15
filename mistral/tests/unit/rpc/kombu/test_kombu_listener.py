# Copyright (c) 2017 Intel Corporation
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
from mistral.tests.unit.rpc.kombu import base
from mistral.tests.unit.rpc.kombu import fake_kombu
from mistral import utils

import mock
from six import moves

with mock.patch.dict('sys.modules', kombu=fake_kombu):
    from mistral.rpc.kombu import base as kombu_base
    from mistral.rpc.kombu import kombu_listener


class TestException(exc.MistralException):
    pass


class KombuListenerTestCase(base.KombuTestCase):

    def setUp(self):
        super(KombuListenerTestCase, self).setUp()

        self.listener = kombu_listener.KombuRPCListener(
            [mock.MagicMock()],
            mock.MagicMock()
        )
        self.ctx = type('context', (object,), {'to_dict': lambda self: {}})()

    def test_add_listener(self):
        correlation_id = utils.generate_unicode_uuid()

        self.listener.add_listener(correlation_id)

        self.assertEqual(
            type(self.listener._results.get(correlation_id)),
            moves.queue.Queue
        )

        self.assertEqual(0, self.listener._results[correlation_id].qsize())

    def test_remove_listener_correlation_id_in_results(self):
        correlation_id = utils.generate_unicode_uuid()

        self.listener.add_listener(correlation_id)

        self.assertEqual(
            type(self.listener._results.get(correlation_id)),
            moves.queue.Queue
        )

        self.listener.remove_listener(correlation_id)

        self.assertIsNone(
            self.listener._results.get(correlation_id)
        )

    def test_remove_listener_correlation_id_not_in_results(self):
        correlation_id = utils.generate_unicode_uuid()

        self.listener.add_listener(correlation_id)

        self.assertEqual(
            type(self.listener._results.get(correlation_id)),
            moves.queue.Queue
        )

        self.listener.remove_listener(utils.generate_unicode_uuid())

        self.assertEqual(
            type(self.listener._results.get(correlation_id)),
            moves.queue.Queue
        )

    @mock.patch('threading.Thread')
    def test_start_thread_not_set(self, thread_class_mock):
        thread_mock = mock.MagicMock()
        thread_class_mock.return_value = thread_mock

        self.listener.start()

        self.assertTrue(thread_mock.daemon)
        self.assertEqual(thread_mock.start.call_count, 1)

    @mock.patch('threading.Thread')
    def test_start_thread_set(self, thread_class_mock):
        thread_mock = mock.MagicMock()
        thread_class_mock.return_value = thread_mock

        self.listener._thread = mock.MagicMock()
        self.listener.start()

        self.assertEqual(thread_mock.start.call_count, 0)

    def test_get_result_results_in_queue(self):
        expected_result = 'abcd'
        correlation_id = utils.generate_unicode_uuid()

        self.listener.add_listener(correlation_id)
        self.listener._results.get(correlation_id).put(expected_result)

        result = self.listener.get_result(correlation_id, 5)

        self.assertEqual(result, expected_result)

    def test_get_result_not_in_queue(self):
        correlation_id = utils.generate_unicode_uuid()

        self.listener.add_listener(correlation_id)

        self.assertRaises(
            moves.queue.Empty,
            self.listener.get_result,
            correlation_id,
            1  # timeout
        )

    def test_get_result_lack_of_queue(self):
        correlation_id = utils.generate_unicode_uuid()

        self.assertRaises(
            KeyError,
            self.listener.get_result,
            correlation_id,
            1  # timeout
        )

    def test__on_response_message_ack_fail(self):
        message = mock.MagicMock()
        message.ack.side_effect = Exception('Test Exception')
        response = 'response'

        kombu_listener.LOG = mock.MagicMock()

        self.listener.on_message(response, message)
        self.assertEqual(kombu_listener.LOG.debug.call_count, 1)
        self.assertEqual(kombu_listener.LOG.exception.call_count, 1)

    def test__on_response_message_ack_ok_corr_id_not_match(self):
        message = mock.MagicMock()
        message.properties = mock.MagicMock()
        message.properties.__getitem__ = lambda *args, **kwargs: True
        response = 'response'

        kombu_listener.LOG = mock.MagicMock()

        self.listener.on_message(response, message)
        self.assertEqual(kombu_listener.LOG.debug.call_count, 3)
        self.assertEqual(kombu_listener.LOG.exception.call_count, 0)

    def test__on_response_message_ack_ok_messsage_type_error(self):
        correlation_id = utils.generate_unicode_uuid()

        message = mock.MagicMock()
        message.properties = dict()
        message.properties['type'] = 'error'
        message.properties['correlation_id'] = correlation_id

        response = TestException('response')

        kombu_listener.LOG = mock.MagicMock()

        self.listener.add_listener(correlation_id)
        self.listener.on_message(response, message)

        self.assertEqual(kombu_listener.LOG.debug.call_count, 2)
        self.assertEqual(kombu_listener.LOG.exception.call_count, 0)

        result = self.listener.get_result(correlation_id, 5)

        self.assertDictEqual(
            result,
            {
                kombu_base.TYPE: 'error',
                kombu_base.RESULT: response
            }
        )

    def test__on_response_message_ack_ok(self):
        correlation_id = utils.generate_unicode_uuid()

        message = mock.MagicMock()
        message.properties = dict()
        message.properties['type'] = None
        message.properties['correlation_id'] = correlation_id

        response = 'response'

        kombu_listener.LOG = mock.MagicMock()

        self.listener.add_listener(correlation_id)
        self.listener.on_message(response, message)

        self.assertEqual(kombu_listener.LOG.debug.call_count, 2)
        self.assertEqual(kombu_listener.LOG.exception.call_count, 0)

        result = self.listener.get_result(correlation_id, 5)

        self.assertDictEqual(
            result,
            {
                kombu_base.TYPE: None,
                kombu_base.RESULT: response
            }
        )
