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

from mistral import context
from mistral import exceptions
from mistral.tests.unit.engine import base


class ContextTestCase(base.EngineTestCase):

    def test_target_insecure(self):
        # Defaults to False if X-Target-Auth-Uri isn't passed.
        headers = context._extract_mistral_auth_params({
            'X-Target-Insecure': 'True',
        })
        self.assertFalse(headers['insecure'])

        headers = {
            "X-Target-Auth-Uri": "uri",
            'X-Target-Auth-Token': 'Token',
        }

        params = context._extract_mistral_auth_params(headers)
        self.assertFalse(params['insecure'])

        headers['X-Target-Insecure'] = 'True'
        params = context._extract_mistral_auth_params(headers)
        self.assertTrue(params['insecure'])

        headers['X-Target-Insecure'] = 'False'
        params = context._extract_mistral_auth_params(headers)
        self.assertFalse(params['insecure'])

        headers['X-Target-Insecure'] = 'S3cure'
        self.assertRaises(
            exceptions.MistralException,
            context._extract_mistral_auth_params, headers)
