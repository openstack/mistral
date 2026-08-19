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
            {'type': 'webhook', 'url': 'http://x',
             'headers': {'X-Auth-Token': 'abc', 'Accept': 'application/json'}},
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
