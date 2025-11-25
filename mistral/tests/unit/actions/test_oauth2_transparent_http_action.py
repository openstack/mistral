# Modified in 2025 by NetCracker Technology Corp.
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

import json
from unittest import mock

import requests

from mistral.actions import oauth2
from mistral.tests.unit import base


URL = 'http://some_url'

DATA = {
    'server': {
        'id': '12345',
        'metadata': {
            'name': 'super_server'
        }
    }
}


def get_fake_response(content, code, **kwargs):
    return base.FakeHTTPResponse(
        content,
        code,
        **kwargs
    )


def get_success_fake_response():
    return get_fake_response(
        json.dumps(DATA),
        200,
        headers={'Content-Type': 'application/json'}
    )


class TransparentHTTPActionTest(base.BaseTest):
    @mock.patch.object(requests, 'request')
    def test_http_action(self, mocked_method):
        mocked_method.return_value = get_success_fake_response()
        mock_ctx = mock.Mock()
        mock_headers = {}
        mock_ctx.execution.workflow_propagated_headers = mock_headers
        headers = {
            'Authorization': 'Bearer 1234567890'
        }

        action = oauth2.TransparentAuthHTTPAction(
            url=URL,
            method='GET',
            headers=headers
        )

        self.assertEqual(URL, action.url)

        result = action.run(mock_ctx)

        self.assertIsInstance(result, dict)
        self.assertEqual(DATA, result['content'])
        self.assertIn('headers', result)
        self.assertEqual(200, result['status'])

        mocked_method.assert_called_with(
            'GET',
            URL,
            data=None,
            json=None,
            headers=headers,
            cookies=None,
            params=None,
            timeout=None,
            auth=None,
            allow_redirects=None,
            proxies=None,
            verify=None
        )
