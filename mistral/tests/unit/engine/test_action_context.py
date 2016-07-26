# Copyright 2014 - StackStorm, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
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
from mistral.services import workbooks as wb_service
from mistral.tests.unit import base as test_base
from mistral.tests.unit.engine import base
from mistral.workflow import states


# Use the set_default method to set value otherwise in certain test cases
# the change in value is not permanent.
cfg.CONF.set_default('auth_enable', False, group='pecan')


WORKBOOK = """
---
version: '2.0'

name: wb

workflows:
  wf1:
    type: direct

    tasks:
      task1:
        action: std.mistral_http
        input:
          url: https://wiki.openstack.org/wiki/mistral
        publish:
          result: <% task(task1).result %>
"""


class ActionContextTest(base.EngineTestCase):

    @mock.patch.object(
        requests, 'request',
        mock.MagicMock(return_value=test_base.FakeHTTPResponse('', 200, 'OK')))
    @mock.patch.object(
        std_actions.MistralHTTPAction, 'is_sync',
        mock.MagicMock(return_value=True))
    def test_action_context(self):
        wb_service.create_workbook_v2(WORKBOOK)

        wf_ex = self.engine.start_workflow('wb.wf1', {})

        self.await_workflow_success(wf_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.SUCCESS, wf_ex.state)
        task_ex = self._assert_single_item(wf_ex.task_executions, name='task1')
        action_ex = self._assert_single_item(task_ex.executions)

        headers = {
            'Mistral-Workflow-Name': wf_ex.workflow_name,
            'Mistral-Workflow-Execution-Id': wf_ex.id,
            'Mistral-Task-Id': task_ex.id,
            'Mistral-Action-Execution-Id': action_ex.id,
            'Mistral-Callback-URL': '/v2/action_executions/%s' % action_ex.id
        }

        requests.request.assert_called_with(
            'GET',
            'https://wiki.openstack.org/wiki/mistral',
            params=None,
            data=None,
            headers=headers,
            cookies=None,
            auth=None,
            timeout=None,
            allow_redirects=None,
            proxies=None,
            verify=None
        )

    @mock.patch.object(
        requests, 'request',
        mock.MagicMock(return_value=test_base.FakeHTTPResponse('', 200, 'OK')))
    def test_single_async_saved_action_context(self):
        action_ex = self.engine.start_action(
            'std.mistral_http',
            {'url': 'https://wiki.openstack.org/wiki/mistral'},
            save_result=True
        )

        action_context = {
            'action_execution_id': action_ex.id,
            'callback_url': '/v2/action_executions/%s' % action_ex.id,
            'task_id': None,
            'task_name': None,
            'task_tags': None,
            'workflow_name': None,
            'workflow_execution_id': None
        }

        self.assertIn('action_context', action_ex.input)
        self.assertEqual(action_context, action_ex.input['action_context'])

    @mock.patch.object(
        requests, 'request',
        mock.MagicMock(return_value=test_base.FakeHTTPResponse('', 200, 'OK')))
    def test_single_async_action_context(self):
        action_ex = self.engine.start_action(
            'std.mistral_http',
            {'url': 'https://wiki.openstack.org/wiki/mistral'},
            save_result=False
        )

        action_context = {
            'action_execution_id': action_ex.id,
            'callback_url': '/v2/action_executions/%s' % action_ex.id,
            'task_id': None,
            'task_name': None,
            'task_tags': None,
            'workflow_name': None,
            'workflow_execution_id': None
        }

        self.assertIn('action_context', action_ex.input)
        self.assertEqual(action_context, action_ex.input['action_context'])

    @mock.patch.object(
        requests, 'request',
        mock.MagicMock(return_value=test_base.FakeHTTPResponse('', 200, 'OK')))
    @mock.patch.object(
        std_actions.MistralHTTPAction, 'is_sync',
        mock.MagicMock(return_value=True))
    def test_single_sync_saved_action_context(self):
        action_ex = self.engine.start_action(
            'std.mistral_http',
            {'url': 'https://wiki.openstack.org/wiki/mistral'},
            save_result=True
        )

        action_context = {
            'action_execution_id': action_ex.id,
            'callback_url': '/v2/action_executions/%s' % action_ex.id,
            'task_id': None,
            'task_name': None,
            'task_tags': None,
            'workflow_name': None,
            'workflow_execution_id': None
        }

        self.assertIn('action_context', action_ex.input)
        self.assertEqual(action_context, action_ex.input['action_context'])

    @mock.patch.object(
        requests, 'request',
        mock.MagicMock(return_value=test_base.FakeHTTPResponse('', 200, 'OK')))
    @mock.patch.object(
        std_actions.MistralHTTPAction, 'is_sync',
        mock.MagicMock(return_value=True))
    def test_single_sync_action_context(self):
        action_ex = self.engine.start_action(
            'std.mistral_http',
            {'url': 'https://wiki.openstack.org/wiki/mistral'},
            save_result=False
        )

        action_context = {
            'action_execution_id': None,
            'callback_url': None,
            'task_id': None,
            'task_name': None,
            'task_tags': None,
            'workflow_name': None,
            'workflow_execution_id': None
        }

        self.assertIn('action_context', action_ex.input)
        self.assertEqual(action_context, action_ex.input['action_context'])
