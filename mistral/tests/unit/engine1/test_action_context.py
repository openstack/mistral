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

import json

import mock
from oslo.config import cfg
import requests

from mistral.actions import std_actions
from mistral.db.v2 import api as db_api
from mistral.engine import states
from mistral.openstack.common import log as logging
from mistral.services import workbooks as wb_service
from mistral.tests.unit.engine1 import base


LOG = logging.getLogger(__name__)

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
          result: $
"""


class FakeResponse(object):

    def __init__(self, text, status_code, reason):
        self.text = text
        self.content = text
        self.headers = {}
        self.status_code = status_code
        self.reason = reason

    def json(self):
        return json.loads(self.text)


class ActionContextTest(base.EngineTestCase):

    @mock.patch.object(
        requests, 'request',
        mock.MagicMock(return_value=FakeResponse('', 200, 'OK')))
    @mock.patch.object(
        std_actions.MistralHTTPAction, 'is_sync',
        mock.MagicMock(return_value=True))
    def test_action_context(self):
        wb_service.create_workbook_v2({'definition': WORKBOOK})
        exec_db = self.engine.start_workflow('wb.wf1', {})
        self._await(lambda: self.is_execution_success(exec_db.id))

        exec_db = db_api.get_execution(exec_db.id)
        self.assertEqual(states.SUCCESS, exec_db.state)
        task = self._assert_single_item(exec_db.tasks, name='task1')

        headers = {
            'Mistral-Workflow-Name': exec_db.wf_name,
            'Mistral-Task-Id': task.id,
            'Mistral-Execution-Id': exec_db.id
        }

        requests.request.assert_called_with(
            'GET', 'https://wiki.openstack.org/wiki/mistral',
            params=None, data=None, headers=headers, cookies=None, auth=None,
            timeout=None, allow_redirects=None, proxies=None)
