# Copyright 2016 NEC Corporation. All rights reserved.
# Copyright 2018 OVH SAS. All rights reserved.
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

MOCK_DELETE = mock.MagicMock(return_value=None)

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
MOCK_WF = mock.MagicMock(return_value=WF_DB)


class TestWorkflowPolicy(base.APITest):
    """Test workflow related policies

    Policies to test:
    - workflows:create
    - workflows:delete
    - workflows:get
    - workflows:list
    - workflows:list:all_projects
    - workflows:publicize (on POST & PUT)
    - workflows:update
    """

    def setUp(self):
        self.policy = self.useFixture(policy_fixtures.PolicyFixture())
        super(TestWorkflowPolicy, self).setUp()

    @mock.patch.object(db_api, "create_workflow_definition")
    def test_workflow_create_not_allowed(self, mock_obj):
        self.policy.change_policy_definition(
            {"workflows:create": "role:FAKE"}
        )
        resp = self.app.post(
            '/v2/workflows',
            WF_DEFINITION,
            headers={'Content-Type': 'text/plain'},
            expect_errors=True
        )

        self.assertEqual(403, resp.status_int)

    @mock.patch.object(db_api, "create_workflow_definition")
    def test_workflow_create_allowed(self, mock_obj):
        self.policy.change_policy_definition(
            {"workflows:create": "role:FAKE or rule:admin_or_owner"}
        )
        resp = self.app.post(
            '/v2/workflows',
            WF_DEFINITION,
            headers={'Content-Type': 'text/plain'},
            expect_errors=True
        )

        self.assertEqual(201, resp.status_int)

    @mock.patch.object(db_api, "create_workflow_definition")
    def test_workflow_create_public_not_allowed(self, mock_obj):
        self.policy.change_policy_definition({
            "workflows:create": "role:FAKE or rule:admin_or_owner",
            "workflows:publicize": "role:FAKE"
        })
        resp = self.app.post(
            '/v2/workflows?scope=public',
            WF_DEFINITION,
            headers={'Content-Type': 'text/plain'},
            expect_errors=True
        )

        self.assertEqual(403, resp.status_int)

    @mock.patch.object(db_api, "create_workflow_definition")
    def test_workflow_create_public_allowed(self, mock_obj):
        self.policy.change_policy_definition({
            "workflows:create": "role:FAKE or rule:admin_or_owner",
            "workflows:publicize": "role:FAKE or rule:admin_or_owner"
        })
        resp = self.app.post(
            '/v2/workflows?scope=public',
            WF_DEFINITION,
            headers={'Content-Type': 'text/plain'},
            expect_errors=True
        )

        self.assertEqual(201, resp.status_int)

    @mock.patch.object(db_api, "delete_workflow_definition", MOCK_DELETE)
    @mock.patch.object(db_api, "get_workflow_definition", MOCK_WF)
    def test_workflow_delete_not_allowed(self):
        self.policy.change_policy_definition(
            {"workflows:delete": "role:FAKE"}
        )
        resp = self.app.delete(
            '/v2/workflows/123',
            expect_errors=True
        )

        self.assertEqual(403, resp.status_int)

    @mock.patch.object(db_api, "delete_workflow_definition", MOCK_DELETE)
    @mock.patch.object(db_api, "get_workflow_definition", MOCK_WF)
    def test_workflow_delete_allowed(self):
        self.policy.change_policy_definition(
            {"workflows:delete": "role:FAKE or rule:admin_or_owner"}
        )
        resp = self.app.delete(
            '/v2/workflows/123',
            expect_errors=True
        )

        self.assertEqual(204, resp.status_int)

    @mock.patch.object(db_api, "get_workflow_definition", MOCK_WF)
    def test_workflow_get_not_allowed(self):
        self.policy.change_policy_definition(
            {"workflows:get": "role:FAKE"}
        )
        resp = self.app.get(
            '/v2/workflows/123',
            expect_errors=True
        )

        self.assertEqual(403, resp.status_int)

    @mock.patch.object(db_api, "get_workflow_definition", MOCK_WF)
    def test_workflow_get_allowed(self):
        self.policy.change_policy_definition(
            {"workflows:get": "role:FAKE or rule:admin_or_owner"}
        )
        resp = self.app.get(
            '/v2/workflows/123',
            expect_errors=True
        )

        self.assertEqual(200, resp.status_int)

    def test_workflow_list_not_allowed(self):
        self.policy.change_policy_definition(
            {"workflows:list": "role:FAKE"}
        )
        resp = self.app.get(
            '/v2/workflows',
            expect_errors=True
        )

        self.assertEqual(403, resp.status_int)

    def test_workflow_list_allowed(self):
        self.policy.change_policy_definition(
            {"workflows:list": "role:FAKE or rule:admin_or_owner"}
        )
        resp = self.app.get(
            '/v2/workflows',
            expect_errors=True
        )

        self.assertEqual(200, resp.status_int)

    def test_workflow_list_all_not_allowed(self):
        self.policy.change_policy_definition({
            "workflows:list": "role:FAKE or rule:admin_or_owner",
            "workflows:list:all_projects": "role:FAKE"
        })
        resp = self.app.get(
            '/v2/workflows?all_projects=1',
            expect_errors=True
        )

        self.assertEqual(403, resp.status_int)

    def test_workflow_list_all_allowed(self):
        self.policy.change_policy_definition({
            "workflows:list": "role:FAKE or rule:admin_or_owner",
            "workflows:list:all_projects": "role:FAKE or rule:admin_or_owner"
        })
        resp = self.app.get(
            '/v2/workflows?all_projects=1',
            expect_errors=True
        )

        self.assertEqual(200, resp.status_int)

    @mock.patch.object(db_api, "update_workflow_definition")
    def test_workflow_update_not_allowed(self, mock_obj):
        self.policy.change_policy_definition(
            {"workflows:update": "role:FAKE"}
        )
        resp = self.app.put(
            '/v2/workflows',
            WF_DEFINITION,
            headers={'Content-Type': 'text/plain'},
            expect_errors=True
        )

        self.assertEqual(403, resp.status_int)

    @mock.patch.object(db_api, "update_workflow_definition")
    def test_workflow_update_allowed(self, mock_obj):
        self.policy.change_policy_definition(
            {"workflows:update": "role:FAKE or rule:admin_or_owner"}
        )
        resp = self.app.put(
            '/v2/workflows',
            WF_DEFINITION,
            headers={'Content-Type': 'text/plain'},
            expect_errors=True
        )

        self.assertEqual(200, resp.status_int)

    @mock.patch.object(db_api, "update_workflow_definition")
    def test_workflow_update_public_not_allowed(self, mock_obj):
        self.policy.change_policy_definition({
            "workflows:update": "role:FAKE or rule:admin_or_owner",
            "workflows:publicize": "role:FAKE"
        })
        resp = self.app.put(
            '/v2/workflows?scope=public',
            WF_DEFINITION,
            headers={'Content-Type': 'text/plain'},
            expect_errors=True
        )

        self.assertEqual(403, resp.status_int)

    @mock.patch.object(db_api, "update_workflow_definition")
    def test_workflow_update_public_allowed(self, mock_obj):
        self.policy.change_policy_definition({
            "workflows:update": "role:FAKE or rule:admin_or_owner",
            "workflows:publicize": "role:FAKE or rule:admin_or_owner"
        })
        resp = self.app.put(
            '/v2/workflows?scope=public',
            WF_DEFINITION,
            headers={'Content-Type': 'text/plain'},
            expect_errors=True
        )

        self.assertEqual(200, resp.status_int)
