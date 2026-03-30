# Copyright 2026 - All rights reserved.
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
from unittest import mock

from mistral.db.v2 import api as db_api
from mistral.db.v2.sqlalchemy import models
from mistral.services import workbooks
from mistral.tests.unit.api import base
from mistral.tests.unit.mstrlfixtures import policy_fixtures

MOCK_DELETE = mock.MagicMock(return_value=None)

WB_DEFINITION = """
---
version: '2.0'
name: 'test'

workflows:
  flow:
    type: direct
    tasks:
      task1:
        action: std.echo output="Hi"
"""

WB_DB = models.Workbook(
    id='123e4567-e89b-12d3-a456-426655440000',
    name='test',
    definition=WB_DEFINITION,
    created_at=datetime.datetime(1970, 1, 1),
    updated_at=datetime.datetime(1970, 1, 1),
    spec={'name': 'test'}
)
MOCK_WB = mock.MagicMock(return_value=WB_DB)


class TestWorkbookPolicy(base.APITest):
    """Test workbook related policies

    Policies to test:
    - workbooks:create
    - workbooks:publicize (on POST & PUT)
    - workbooks:delete
    - workbooks:get
    - workbooks:list
    - workbooks:update
    """

    def setUp(self):
        self.policy = self.useFixture(policy_fixtures.PolicyFixture())
        super(TestWorkbookPolicy, self).setUp()

    @mock.patch.object(workbooks, "create_workbook_v2")
    def test_workbook_create_not_allowed(self, mock_obj):
        self.policy.change_policy_definition(
            {"workbooks:create": "role:FAKE"}
        )
        resp = self.app.post(
            '/v2/workbooks',
            WB_DEFINITION,
            headers={'Content-Type': 'text/plain'},
            expect_errors=True
        )

        self.assertEqual(403, resp.status_int)

    @mock.patch.object(workbooks, "create_workbook_v2")
    def test_workbook_create_allowed(self, mock_obj):
        mock_obj.return_value = WB_DB

        self.policy.change_policy_definition(
            {"workbooks:create": "role:FAKE or rule:admin_or_owner"}
        )
        resp = self.app.post(
            '/v2/workbooks',
            WB_DEFINITION,
            headers={'Content-Type': 'text/plain'}
        )

        self.assertEqual(201, resp.status_int)

    @mock.patch.object(workbooks, "create_workbook_v2")
    def test_workbook_create_public_not_allowed(self, mock_obj):
        # Default policy requires admin_only for publicize.
        # The default test context has is_admin=False, so a regular user
        # (project owner) should be denied.
        resp = self.app.post(
            '/v2/workbooks?scope=public',
            WB_DEFINITION,
            headers={'Content-Type': 'text/plain'},
            expect_errors=True
        )

        self.assertEqual(403, resp.status_int)

    @mock.patch.object(workbooks, "create_workbook_v2")
    def test_workbook_create_public_allowed(self, mock_obj):
        mock_obj.return_value = WB_DB

        # Default policy requires admin_only for publicize.
        # An admin user should be allowed.
        self.ctx.is_admin = True
        self.addCleanup(setattr, self.ctx, 'is_admin', False)

        resp = self.app.post(
            '/v2/workbooks?scope=public',
            WB_DEFINITION,
            headers={'Content-Type': 'text/plain'}
        )

        self.assertEqual(201, resp.status_int)

    @mock.patch.object(db_api, "delete_workbook", MOCK_DELETE)
    @mock.patch.object(db_api, "get_workbook", MOCK_WB)
    def test_workbook_delete_not_allowed(self):
        self.policy.change_policy_definition(
            {"workbooks:delete": "role:FAKE"}
        )
        resp = self.app.delete(
            '/v2/workbooks/test',
            expect_errors=True
        )

        self.assertEqual(403, resp.status_int)

    @mock.patch.object(db_api, "delete_workbook", MOCK_DELETE)
    @mock.patch.object(db_api, "get_workbook", MOCK_WB)
    def test_workbook_delete_allowed(self):
        self.policy.change_policy_definition(
            {"workbooks:delete": "role:FAKE or rule:admin_or_owner"}
        )
        resp = self.app.delete(
            '/v2/workbooks/test'
        )

        self.assertEqual(204, resp.status_int)

    @mock.patch.object(db_api, "get_workbook", MOCK_WB)
    def test_workbook_get_not_allowed(self):
        self.policy.change_policy_definition(
            {"workbooks:get": "role:FAKE"}
        )
        resp = self.app.get(
            '/v2/workbooks/test',
            expect_errors=True
        )

        self.assertEqual(403, resp.status_int)

    @mock.patch.object(db_api, "get_workbook", MOCK_WB)
    def test_workbook_get_allowed(self):
        self.policy.change_policy_definition(
            {"workbooks:get": "role:FAKE or rule:admin_or_owner"}
        )
        resp = self.app.get(
            '/v2/workbooks/test'
        )

        self.assertEqual(200, resp.status_int)

    def test_workbook_list_not_allowed(self):
        self.policy.change_policy_definition(
            {"workbooks:list": "role:FAKE"}
        )
        resp = self.app.get(
            '/v2/workbooks',
            expect_errors=True
        )

        self.assertEqual(403, resp.status_int)

    def test_workbook_list_allowed(self):
        self.policy.change_policy_definition(
            {"workbooks:list": "role:FAKE or rule:admin_or_owner"}
        )
        resp = self.app.get(
            '/v2/workbooks'
        )

        self.assertEqual(200, resp.status_int)

    @mock.patch.object(workbooks, "update_workbook_v2")
    def test_workbook_update_not_allowed(self, mock_obj):
        self.policy.change_policy_definition(
            {"workbooks:update": "role:FAKE"}
        )
        resp = self.app.put(
            '/v2/workbooks',
            WB_DEFINITION,
            headers={'Content-Type': 'text/plain'},
            expect_errors=True
        )

        self.assertEqual(403, resp.status_int)

    @mock.patch.object(workbooks, "update_workbook_v2")
    def test_workbook_update_allowed(self, mock_obj):
        mock_obj.return_value = WB_DB

        self.policy.change_policy_definition(
            {"workbooks:update": "role:FAKE or rule:admin_or_owner"}
        )
        resp = self.app.put(
            '/v2/workbooks',
            WB_DEFINITION,
            headers={'Content-Type': 'text/plain'}
        )

        self.assertEqual(200, resp.status_int)

    @mock.patch.object(workbooks, "update_workbook_v2")
    def test_workbook_update_public_not_allowed(self, mock_obj):
        # Default policy requires admin_only for publicize.
        # The default test context has is_admin=False, so a regular user
        # (project owner) should be denied.
        resp = self.app.put(
            '/v2/workbooks?scope=public',
            WB_DEFINITION,
            headers={'Content-Type': 'text/plain'},
            expect_errors=True
        )

        self.assertEqual(403, resp.status_int)

    @mock.patch.object(workbooks, "update_workbook_v2")
    def test_workbook_update_public_allowed(self, mock_obj):
        mock_obj.return_value = WB_DB

        # Default policy requires admin_only for publicize.
        # An admin user should be allowed.
        self.ctx.is_admin = True
        self.addCleanup(setattr, self.ctx, 'is_admin', False)

        resp = self.app.put(
            '/v2/workbooks?scope=public',
            WB_DEFINITION,
            headers={'Content-Type': 'text/plain'}
        )

        self.assertEqual(200, resp.status_int)
