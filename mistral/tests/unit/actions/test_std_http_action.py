# Copyright 2014 - Mirantis, Inc.
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

ACTION_LOGGER = 'mistral.actions.std_actions'


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
        mock_headers = {}
        mock_ctx.execution.workflow_propagated_headers = mock_headers

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
            json=None,
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
        mock_headers = {}
        mock_ctx.execution.workflow_propagated_headers = mock_headers

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
        mock_headers = {}
        mock_ctx.execution.workflow_propagated_headers = mock_headers

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
        mock_headers = {}
        mock_ctx.execution.workflow_propagated_headers = mock_headers

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
            mock_ctx = mock.Mock()
            mock_headers = {}
            mock_ctx.execution.workflow_propagated_headers = mock_headers

            result = action.run(mock_ctx)
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
        mock_headers = {}
        mock_ctx.execution.workflow_propagated_headers = mock_headers

        result = action.run(mock_ctx)

        self.assertIsNone(result['encoding'])

    @mock.patch.object(requests, 'request')
    def test_http_action_hides_request_body_if_needed(self, mocked_method):
        self.override_config(
            'hide_request_body',
            True,
            group='action_logging'
        )

        sensitive_data = 'I actually love anime.'

        action = std.HTTPAction(url=URL, method='POST', body=sensitive_data)

        mocked_method.return_value = get_fake_response(
            content='', code=201
        )
        mock_ctx = mock.Mock()
        mock_headers = {}
        mock_ctx.execution.workflow_propagated_headers = mock_headers

        with self.assertLogs(logger=ACTION_LOGGER, level='INFO') as logs:
            action.run(mock_ctx)

        self.assertEqual(2, len(logs.output))  # Request and response loglines

        log = logs.output[0]  # Request log
        msg = "Request body hidden due to action_logging configuration."
        self.assertNotIn(sensitive_data, log)
        self.assertIn(msg, log)

    @mock.patch.object(requests, 'request')
    def test_http_action_hides_request_headers_if_needed(self, mocked_method):
        sensitive_header = 'Authorization'
        self.override_config(
            'sensitive_headers',
            [sensitive_header],
            group='action_logging'
        )

        headers = {
            sensitive_header: 'Bearer 13e7aa3fc23e50bc1529dc136791d34d'
        }

        action = std.HTTPAction(url=URL, method='GET', headers=headers)

        mocked_method.return_value = get_fake_response(
            content='', code=200
        )
        mock_ctx = mock.Mock()
        mock_headers = {}
        mock_ctx.execution.workflow_propagated_headers = mock_headers

        with self.assertLogs(logger=ACTION_LOGGER, level='INFO') as logs:
            action.run(mock_ctx)

        self.assertEqual(2, len(logs.output))  # Request and response loglines

        log = logs.output[0]  # Request log
        self.assertNotIn(headers[sensitive_header], log)
        self.assertIn('headers={}', log)

    @mock.patch.object(requests, 'request')
    def test_http_action_hides_response_body_if_needed(self, mocked_method):
        self.override_config(
            'hide_response_body',
            True,
            group='action_logging'
        )

        action = std.HTTPAction(url=URL, method='GET')

        sensitive_data = 'I actually love anime.'

        mocked_method.return_value = get_fake_response(
            content=sensitive_data, code=200
        )
        mock_ctx = mock.Mock()
        mock_headers = {}
        mock_ctx.execution.workflow_propagated_headers = mock_headers

        with self.assertLogs(logger=ACTION_LOGGER, level='INFO') as logs:
            action.run(mock_ctx)

        self.assertEqual(2, len(logs.output))  # Request and response loglines

        log = logs.output[1]  # Response log
        msg = "Response body hidden due to action_logging configuration."
        self.assertNotIn(sensitive_data, log)
        self.assertIn(msg, log)

    @mock.patch.object(requests, 'request')
    def test_http_action_get_headers_from_context(self, mocked_method):
        headers = {'Header1': "qwerty", 'Header2': "123",
                   'Header3': "wow"}

        mocked_method.return_value = get_success_fake_response()
        mock_ctx = mock.Mock()
        mock_ctx.execution.workflow_propagated_headers = headers

        action = std.HTTPAction(
            url=URL,
            method='GET',
            headers=headers.copy(),
        )
        result = action.run(mock_ctx)

        self.assertIn('headers', result)

        args, kwargs = mocked_method.call_args
        self.assertEqual(headers, kwargs['headers'])

    @mock.patch.object(requests, 'request')
    def test_http_action_with_mistral_headers(self, mocked_method):
        mocked_method.return_value = get_success_fake_response()
        mock_ctx = mock.Mock()
        mock_headers = {}
        mock_ctx.execution.workflow_propagated_headers = mock_headers

        mock_ex = mock_ctx.execution

        headers = {
            'Mistral-Workflow-Name': mock_ex.workflow_name,
            'Mistral-Task-Id': mock_ex.task_execution_id,
            'Mistral-Action-Execution-Id': mock_ex.action_execution_id,
            'Mistral-Workflow-Execution-Id': mock_ex.workflow_execution_id
        }

        action = std.HTTPAction(
            url=URL,
            method='GET',
            headers=headers.copy(),
            mistral_headers=True
        )

        action.run(mock_ctx)

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
