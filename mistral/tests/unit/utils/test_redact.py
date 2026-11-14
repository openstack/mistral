# Copyright 2026 - OVHcloud.
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

from mistral.tests.unit import base
from mistral.utils import redact


class RedactSensitiveTest(base.BaseTest):
    def test_masks_sensitive_keys(self):
        data = {
            'user': 'bob',
            'password': 'p4ss',
            'api_key': 'k',
            'auth_token': 't',
            'nested': {'secret': 's', 'keep': 'v'},
        }

        out = redact.redact_sensitive(data)

        self.assertEqual('bob', out['user'])
        self.assertEqual('***', out['password'])
        self.assertEqual('***', out['api_key'])
        self.assertEqual('***', out['auth_token'])
        self.assertEqual('***', out['nested']['secret'])
        self.assertEqual('v', out['nested']['keep'])

    def test_masks_auth_headers_in_list(self):
        publishers = [
            {
                'type': 'webhook',
                'url': 'http://x',
                'headers': {
                    'X-Auth-Token': 'abc',
                    'Accept': 'application/json',
                },
            },
        ]

        out = redact.redact_sensitive(publishers)

        self.assertEqual('***', out[0]['headers']['X-Auth-Token'])
        self.assertEqual('application/json', out[0]['headers']['Accept'])
        self.assertEqual('http://x', out[0]['url'])

    def test_does_not_mutate_input(self):
        data = {'password': 'p4ss'}

        redact.redact_sensitive(data)

        self.assertEqual('p4ss', data['password'])

    def test_non_dict_values_pass_through(self):
        self.assertEqual(42, redact.redact_sensitive(42))
        self.assertEqual('plain', redact.redact_sensitive('plain'))
        self.assertEqual([1, 2], redact.redact_sensitive([1, 2]))


class RedactUrlTest(base.BaseTest):
    def test_masks_password(self):
        self.assertEqual(
            'http://bob:***@example.com:8080/p?a=1',
            redact.redact_url('http://bob:s3cr3t@example.com:8080/p?a=1'),
        )

    def test_masks_user_only_userinfo(self):
        self.assertEqual(
            'https://***@example.com/',
            redact.redact_url('https://tok3n@example.com/'),
        )

    def test_masks_sensitive_query_values(self):
        out = redact.redact_url(
            'https://example.com/x?token=abc&page=2&api_key=k'
        )

        self.assertEqual(
            'https://example.com/x?token=***&page=2&api_key=***', out
        )

    def test_url_without_credentials_is_unchanged(self):
        url = 'http://example.com/path?page=2'

        self.assertEqual(url, redact.redact_url(url))

    def test_schemeless_proxy(self):
        self.assertEqual(
            '***@proxy:3128', redact.redact_url('bob:pw@proxy:3128')
        )

    def test_non_string_passes_through(self):
        self.assertIsNone(redact.redact_url(None))

    def test_proxies(self):
        out = redact.redact_proxies(
            {
                'http': 'http://bob:pw@proxy:3128',
                'https': 'http://proxy:3128',
                'no_proxy': 'localhost',
            }
        )

        self.assertEqual(
            {
                'http': 'http://bob:***@proxy:3128',
                'https': 'http://proxy:3128',
                'no_proxy': 'localhost',
            },
            out,
        )
        self.assertIsNone(redact.redact_proxies(None))
