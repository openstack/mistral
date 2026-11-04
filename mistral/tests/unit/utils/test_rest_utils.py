# Copyright 2018 - Nokia, Inc.
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

from wsme import exc as wsme_exc

from mistral.tests.unit import base
from mistral.utils import rest_utils


class RestUtilsTest(base.BaseTest):
    def test_validate_fields(self):
        rest_utils.validate_fields(["a", "b"], ["a", "b", "c"])

        e = self.assertRaises(wsme_exc.ClientSideError,
                              rest_utils.validate_fields, ["d"], ["a"])
        self.assertIn("[d]", str(e))

    def test_clear_sensitive_headers_defaults(self):
        headers = {
            'authorization': 'Bearer secret',
            'X-AUTH-TOKEN': 'token',
            'X-Subject-Token': 'subject',
            'Cookie': 'session=1',
            'x-api-key': 'key',
            'Content-Type': 'application/json'
        }

        self.assertEqual(
            {'Content-Type': 'application/json'},
            rest_utils.clear_sensitive_headers(headers)
        )
        self.assertEqual('Bearer secret', headers['authorization'])

    def test_clear_sensitive_headers_custom(self):
        self.override_config(
            'sensitive_headers',
            ['X-Custom'],
            group='action_logging'
        )

        self.assertEqual(
            {'Authorization': 'Bearer secret'},
            rest_utils.clear_sensitive_headers(
                {'Authorization': 'Bearer secret', 'x-custom': 'secret'}
            )
        )

    def test_clear_sensitive_headers_empty(self):
        self.assertIsNone(rest_utils.clear_sensitive_headers(None))
        self.assertEqual({}, rest_utils.clear_sensitive_headers({}))

    def test_prepare_response_body_log_truncates(self):
        self.override_config(
            'response_body_log_limit',
            5,
            group='action_logging'
        )

        self.assertEqual(
            'abcde... (truncated, total length 10)',
            rest_utils.prepare_response_body_log('abcdefghij')
        )
        self.assertEqual(
            'abcde',
            rest_utils.prepare_response_body_log('abcde')
        )

    def test_prepare_response_body_log_no_limit(self):
        self.override_config(
            'response_body_log_limit',
            0,
            group='action_logging'
        )
        body = 'a' * 5000

        self.assertEqual(body, rest_utils.prepare_response_body_log(body))

    def test_prepare_response_body_log_default_limit(self):
        log = rest_utils.prepare_response_body_log('a' * 5000)

        self.assertTrue(log.startswith('a' * 1024 + '...'))
        self.assertIn('total length 5000', log)

    def test_prepare_response_body_log_hidden(self):
        self.override_config(
            'hide_response_body',
            True,
            group='action_logging'
        )

        self.assertEqual(
            'Response body hidden due to action_logging configuration.',
            rest_utils.prepare_response_body_log('secret')
        )
