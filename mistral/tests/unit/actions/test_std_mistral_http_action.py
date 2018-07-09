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

import mock
import requests

from mistral.actions import std_actions as std
from mistral.tests.unit import base
from mistral_lib import actions as mistral_lib_actions


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


def get_error_fake_response():
    return get_fake_response(
        json.dumps(DATA),
        401
    )


class MistralHTTPActionTest(base.BaseTest):
    @mock.patch.object(requests, 'request')
    def test_http_action(self, mocked_method):
        mocked_method.return_value = get_success_fake_response()
        mock_ctx = mock.Mock()

        action = std.MistralHTTPAction(
            url=URL,
            method='POST',
            body=DATA,
            timeout=20,
            allow_redirects=True
        )

        DATA_STR = json.dumps(DATA)

        self.assertEqual(DATA_STR, action.body)
        self.assertEqual(URL, action.url)

        result = action.run(mock_ctx)

        self.assertIsInstance(result, dict)
        self.assertEqual(DATA, result['content'])
        self.assertIn('headers', result)
        self.assertEqual(200, result['status'])

        mock_ex = mock_ctx.execution

        headers = {
            'Mistral-Workflow-Name': mock_ex.workflow_name,
            'Mistral-Task-Id': mock_ex.task_execution_id,
            'Mistral-Callback-URL': mock_ex.callback_url,
            'Mistral-Action-Execution-Id': mock_ex.action_execution_id,
            'Mistral-Workflow-Execution-Id': mock_ex.workflow_execution_id
        }

        mocked_method.assert_called_with(
            'POST',
            URL,
            data=DATA_STR,
            headers=headers,
            cookies=None,
            params=None,
            timeout=20,
            auth=None,
            allow_redirects=True,
            proxies=None,
            verify=None
        )

    @mock.patch.object(requests, 'request')
    def test_http_action_error_result(self, mocked_method):
        mocked_method.return_value = get_error_fake_response()
        mock_ctx = mock.Mock()

        action = std.MistralHTTPAction(
            url=URL,
            method='POST',
            body=DATA,
            timeout=20,
            allow_redirects=True
        )

        result = action.run(mock_ctx)

        self.assertIsInstance(result, mistral_lib_actions.Result)
        self.assertEqual(401, result.error['status'])
