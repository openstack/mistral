# -*- coding: utf-8 -*-
#
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
from mistral.tests import base


URL = "http://some_url"

DATA = {
    "server": {
        "id": "12345",
        "metadata": {
            "name": "super_server"
        }
    }
}


def get_fake_response():
    response = mock.Mock()

    response.content = json.dumps(DATA)
    response.json = mock.MagicMock(return_value=DATA)
    response.headers = {'Content-Type': 'application/json'}
    response.status_code = 200

    return response


class HTTPActionTest(base.BaseTest):
    @mock.patch.object(requests, "request")
    def test_http_action(self, mocked_method):
        mocked_method.return_value = get_fake_response()

        action = std.HTTPAction(
            url=URL,
            method="POST",
            body=DATA,
            timeout=20,
            allow_redirects=True)

        DATA_STR = json.dumps(DATA)

        self.assertEqual(DATA_STR, action.body)
        self.assertEqual(URL, action.url)

        result = action.run()

        self.assertIsInstance(result, dict)
        self.assertEqual(DATA, result['content'])
        self.assertIn('headers', result)
        self.assertEqual(200, result['status'])

        mocked_method.assert_called_with(
            "POST",
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

    @mock.patch.object(requests, "request")
    def test_http_action_with_auth(self, mocked_method):
        mocked_method.return_value = get_fake_response()

        action = std.HTTPAction(
            url=URL,
            method="POST",
            body=DATA,
            auth="user:password")

        data_str = json.dumps(DATA)

        self.assertEqual(data_str, action.body)
        self.assertEqual(URL, action.url)

        result = action.run()

        self.assertIsInstance(result, dict)
        self.assertEqual(DATA, result['content'])
        self.assertIn('headers', result)
        self.assertEqual(200, result['status'])

        mocked_method.assert_called_with(
            "POST",
            URL,
            data=data_str,
            headers=None,
            cookies=None,
            params=None,
            timeout=None,
            auth=('user', 'password'),
            allow_redirects=None,
            proxies=None,
            verify=None
        )
