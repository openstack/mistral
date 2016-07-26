# Copyright 2015 - StackStorm, Inc.
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

import mock
from oslo_config import cfg
import requests

from mistral.actions import std_actions
from mistral.db.v2 import api as db_api
from mistral.services import workflows as wf_service
from mistral.tests.unit import base as test_base
from mistral.tests.unit.engine import base
from mistral.workflow import states


# Use the set_default method to set value otherwise in certain test cases
# the change in value is not permanent.
cfg.CONF.set_default('auth_enable', False, group='pecan')

ENV = {
    '__actions': {
        'std.http': {
            'auth': 'librarian:password123',
            'timeout': 30,
        }
    }
}

EXPECTED_ENV_AUTH = ('librarian', 'password123')

WORKFLOW1 = """
---
version: "2.0"
wf1:
  type: direct
  tasks:
    task1:
      action: std.http url="https://api.library.org/books"
      publish:
        result: <% $ %>
"""

WORKFLOW2 = """
---
version: "2.0"
wf2:
  type: direct
  tasks:
    task1:
      action: std.http url="https://api.library.org/books" timeout=60
      publish:
        result: <% $ %>
"""

WORKFLOW1_WITH_ITEMS = """
---
version: "2.0"
wf1_with_items:
  type: direct
  input:
    - links
  tasks:
    task1:
      with-items: link in <% $.links %>
      action: std.http url=<% $.link %>
      publish:
        result: <% $ %>
"""

WORKFLOW2_WITH_ITEMS = """
---
version: "2.0"
wf2_with_items:
  type: direct
  input:
    - links
  tasks:
    task1:
      with-items: link in <% $.links %>
      action: std.http url=<% $.link %> timeout=60
      publish:
        result: <% $ %>
"""


class ActionDefaultTest(base.EngineTestCase):

    @mock.patch.object(
        requests, 'request',
        mock.MagicMock(return_value=test_base.FakeHTTPResponse('', 200, 'OK')))
    @mock.patch.object(
        std_actions.HTTPAction, 'is_sync',
        mock.MagicMock(return_value=True))
    def test_action_defaults_from_env(self):
        wf_service.create_workflows(WORKFLOW1)

        wf_ex = self.engine.start_workflow('wf1', None, env=ENV)

        self.await_workflow_success(wf_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.SUCCESS, wf_ex.state)
        self._assert_single_item(wf_ex.task_executions, name='task1')

        requests.request.assert_called_with(
            'GET', 'https://api.library.org/books',
            params=None, data=None, headers=None, cookies=None,
            allow_redirects=None, proxies=None, verify=None,
            auth=EXPECTED_ENV_AUTH,
            timeout=ENV['__actions']['std.http']['timeout'])

    @mock.patch.object(
        requests, 'request',
        mock.MagicMock(return_value=test_base.FakeHTTPResponse('', 200, 'OK')))
    @mock.patch.object(
        std_actions.HTTPAction, 'is_sync',
        mock.MagicMock(return_value=True))
    def test_action_defaults_from_env_not_applied(self):
        wf_service.create_workflows(WORKFLOW2)

        wf_ex = self.engine.start_workflow('wf2', None, env=ENV)

        self.await_workflow_success(wf_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.SUCCESS, wf_ex.state)
        self._assert_single_item(wf_ex.task_executions, name='task1')

        requests.request.assert_called_with(
            'GET', 'https://api.library.org/books',
            params=None, data=None, headers=None, cookies=None,
            allow_redirects=None, proxies=None, verify=None,
            auth=EXPECTED_ENV_AUTH,
            timeout=60
        )

    @mock.patch.object(
        requests, 'request',
        mock.MagicMock(return_value=test_base.FakeHTTPResponse('', 200, 'OK')))
    @mock.patch.object(
        std_actions.HTTPAction, 'is_sync',
        mock.MagicMock(return_value=True))
    def test_with_items_action_defaults_from_env(self):
        wf_service.create_workflows(WORKFLOW1_WITH_ITEMS)

        wf_input = {
            'links': [
                'https://api.library.org/books',
                'https://api.library.org/authors'
            ]
        }

        wf_ex = self.engine.start_workflow(
            'wf1_with_items',
            wf_input,
            env=ENV
        )

        self.await_workflow_success(wf_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.SUCCESS, wf_ex.state)
        self._assert_single_item(wf_ex.task_executions, name='task1')

        calls = [mock.call('GET', url, params=None, data=None,
                           headers=None, cookies=None,
                           allow_redirects=None, proxies=None,
                           auth=EXPECTED_ENV_AUTH, verify=None,
                           timeout=ENV['__actions']['std.http']['timeout'])
                 for url in wf_input['links']]

        requests.request.assert_has_calls(calls, any_order=True)

    @mock.patch.object(
        requests, 'request',
        mock.MagicMock(return_value=test_base.FakeHTTPResponse('', 200, 'OK')))
    @mock.patch.object(
        std_actions.HTTPAction, 'is_sync',
        mock.MagicMock(return_value=True))
    def test_with_items_action_defaults_from_env_not_applied(self):
        wf_service.create_workflows(WORKFLOW2_WITH_ITEMS)

        wf_input = {
            'links': [
                'https://api.library.org/books',
                'https://api.library.org/authors'
            ]
        }

        wf_ex = self.engine.start_workflow(
            'wf2_with_items',
            wf_input,
            env=ENV
        )

        self.await_workflow_success(wf_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.SUCCESS, wf_ex.state)
        self._assert_single_item(wf_ex.task_executions, name='task1')

        calls = [mock.call('GET', url, params=None, data=None,
                           headers=None, cookies=None,
                           allow_redirects=None, proxies=None,
                           auth=EXPECTED_ENV_AUTH, verify=None,
                           timeout=60)
                 for url in wf_input['links']]

        requests.request.assert_has_calls(calls, any_order=True)
