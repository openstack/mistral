# Copyright 2014 - Mirantis, Inc.
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


class HTTPActionTest(base.BaseTest):
    @mock.patch.object(requests, 'request')
    def test_http_action(self, mocked_method):
        mocked_method.return_value = get_success_fake_response()
        mock_ctx = mock.Mock()

        action = std.HTTPAction(
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

        mocked_method.assert_called_with(
            'POST',
            URL,
            data=DATA_STR,
            headers=None,
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

        action = std.HTTPAction(
            url=URL,
            method='POST',
            body=DATA,
            timeout=20,
            allow_redirects=True
        )

        result = action.run(mock_ctx)

        self.assertIsInstance(result, mistral_lib_actions.Result)
        self.assertEqual(401, result.error['status'])

    @mock.patch.object(requests, 'request')
    def test_http_action_with_auth(self, mocked_method):
        mocked_method.return_value = get_success_fake_response()
        mock_ctx = mock.Mock()

        action = std.HTTPAction(
            url=URL,
            method='POST',
            auth='user:password'
        )

        action.run(mock_ctx)

        args, kwargs = mocked_method.call_args
        self.assertEqual(('user', 'password'), kwargs['auth'])

    @mock.patch.object(requests, 'request')
    def test_http_action_with_headers(self, mocked_method):
        mocked_method.return_value = get_success_fake_response()
        mock_ctx = mock.Mock()

        headers = {'int_header': 33, 'bool_header': True,
                   'float_header': 3.0, 'regular_header': 'teststring'}

        safe_headers = {'int_header': '33', 'bool_header': 'True',
                        'float_header': '3.0', 'regular_header': 'teststring'}

        action = std.HTTPAction(
            url=URL,
            method='POST',
            headers=headers.copy(),
        )

        result = action.run(mock_ctx)

        self.assertIn('headers', result)

        args, kwargs = mocked_method.call_args
        self.assertEqual(safe_headers, kwargs['headers'])

    @mock.patch.object(requests, 'request')
    def test_http_action_empty_resp(self, mocked_method):

        def invoke(content):
            action = std.HTTPAction(
                url=URL,
                method='GET',
            )
            mocked_method.return_value = get_fake_response(
                content=content, code=200
            )
            result = action.run(mock.Mock())
            self.assertEqual(content, result['content'])

        invoke(None)
        invoke('')

    @mock.patch.object(requests, 'request')
    def test_http_action_none_encoding_not_empty_resp(self, mocked_method):
        action = std.HTTPAction(
            url=URL,
            method='GET',
        )

        mocked_method.return_value = get_fake_response(
            content='', code=200, encoding=None
        )
        mock_ctx = mock.Mock()
        result = action.run(mock_ctx)

        self.assertIsNone(result['encoding'])
