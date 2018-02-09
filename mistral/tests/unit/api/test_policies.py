# Copyright 2016 NEC Corporation. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.


import datetime

import mock

from mistral.db.v2 import api as db_api
from mistral.db.v2.sqlalchemy import models
from mistral.tests.unit.api import base
from mistral.tests.unit.mstrlfixtures import policy_fixtures

WF_DEFINITION = """
---
version: '2.0'

flow:
  type: direct
  input:
    - param1

  tasks:
    task1:
      action: std.echo output="Hi"
"""

WF_DB = models.WorkflowDefinition(
    id='123e4567-e89b-12d3-a456-426655440000',
    name='flow',
    definition=WF_DEFINITION,
    created_at=datetime.datetime(1970, 1, 1),
    updated_at=datetime.datetime(1970, 1, 1),
    spec={'input': ['param1']}
)

WF = {
    'id': '123e4567-e89b-12d3-a456-426655440000',
    'name': 'flow',
    'definition': WF_DEFINITION,
    'created_at': '1970-01-01 00:00:00',
    'updated_at': '1970-01-01 00:00:00',
    'input': 'param1'
}

MOCK_WF = mock.MagicMock(return_value=WF_DB)


class TestPolicies(base.APITest):
    @mock.patch.object(db_api, "get_workflow_definition", MOCK_WF)
    def get(self):
        resp = self.app.get('/v2/workflows/123', expect_errors=True)
        return resp.status_int

    def test_disable_workflow_api(self):
        self.policy = self.useFixture(policy_fixtures.PolicyFixture())
        rules = {"workflows:get": "role:FAKE"}
        self.policy.change_policy_definition(rules)
        response_value = self.get()
        self.assertEqual(403, response_value)

    def test_enable_workflow_api(self):
        self.policy = self.useFixture(policy_fixtures.PolicyFixture())
        rules = {"workflows:get": "role:FAKE or rule:admin_or_owner"}
        self.policy.change_policy_definition(rules)
        response_value = self.get()
        self.assertEqual(200, response_value)
