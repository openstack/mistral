# -*- coding: utf-8 -*-
#
# Copyright 2013 - Mirantis, Inc.
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

import unittest2
import mock

from mistralclient.api import client


class FakeResponse(object):
    """Fake response for testing Mistral Client."""

    def __init__(self, status_code, json_values={}, content=None):
        self.status_code = status_code
        self.json_values = json_values
        self.content = content

    def json(self):
        return self.json_values


class BaseClientTest(unittest2.TestCase):
    @mock.patch('keystoneclient.v3.client.Client')
    def setUp(self, keystone):
        keystone.return_value = mock.Mock()
        self._client = client.Client(project_name="test",
                                     auth_url="v3.0",
                                     mistral_url="test")
        self.workbooks = self._client.workbooks
        self.executions = self._client.executions
        self.tasks = self._client.tasks
        self.listeners = self._client.listeners

    def mock_http_get(self, json, status_code=200):
        self._client.http_client.get = \
            mock.MagicMock(return_value=FakeResponse(status_code, json))

    def mock_http_post(self, json, status_code=201):
        self._client.http_client.post = \
            mock.MagicMock(return_value=FakeResponse(status_code, json))

    def mock_http_put(self, json, status_code=200):
        self._client.http_client.put = \
            mock.MagicMock(return_value=FakeResponse(status_code, json))

    def mock_http_delete(self, status_code=204):
        self._client.http_client.delete = \
            mock.MagicMock(return_value=FakeResponse(status_code))
