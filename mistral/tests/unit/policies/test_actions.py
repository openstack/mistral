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


import mock

from mistral.db.v2 import api as db_api
from mistral.db.v2.sqlalchemy import models
from mistral.tests.unit.api import base
from mistral.tests.unit.mstrlfixtures import policy_fixtures

MOCK_DELETE = mock.MagicMock(return_value=None)

ACTION_DEFINITION = """
---
version: '2.0'

my_action:
  description: My super cool action.
  tags: ['test', 'v2']
  base: std.echo
  base-input:
    output: "{$.str1}{$.str2}"
"""
ACTION_DB = models.ActionDefinition(
    id='123e4567-e89b-12d3-a456-426655440000',
    name='my_action',
    is_system=False,
    description='My super cool action.',
    tags=['test', 'v2'],
    definition=ACTION_DEFINITION
)
MOCK_ACTION = mock.MagicMock(return_value=ACTION_DB)


class TestActionPolicy(base.APITest):
    """Test action related policies

    Policies to test:
    - actions:create
    - actions:delete
    - actions:get
    - actions:list
    - actions:publicize (on POST & PUT)
    - actions:update
    """

    def setUp(self):
        self.policy = self.useFixture(policy_fixtures.PolicyFixture())
        super(TestActionPolicy, self).setUp()

    @mock.patch.object(db_api, "create_action_definition")
    def test_action_create_not_allowed(self, mock_obj):
        self.policy.change_policy_definition(
            {"actions:create": "role:FAKE"}
        )
        resp = self.app.post(
            '/v2/actions',
            ACTION_DEFINITION,
            headers={'Content-Type': 'text/plain'},
            expect_errors=True
        )

        self.assertEqual(403, resp.status_int)

    @mock.patch.object(db_api, "create_action_definition")
    def test_action_create_allowed(self, mock_obj):
        self.policy.change_policy_definition(
            {"actions:create": "role:FAKE or rule:admin_or_owner"}
        )
        resp = self.app.post(
            '/v2/actions',
            ACTION_DEFINITION,
            headers={'Content-Type': 'text/plain'},
            expect_errors=True
        )

        self.assertEqual(201, resp.status_int)

    @mock.patch.object(db_api, "create_action_definition")
    def test_action_create_public_not_allowed(self, mock_obj):
        self.policy.change_policy_definition({
            "actions:create": "role:FAKE or rule:admin_or_owner",
            "actions:publicize": "role:FAKE"
        })
        resp = self.app.post(
            '/v2/actions?scope=public',
            ACTION_DEFINITION,
            headers={'Content-Type': 'text/plain'},
            expect_errors=True
        )

        self.assertEqual(403, resp.status_int)

    @mock.patch.object(db_api, "create_action_definition")
    def test_action_create_public_allowed(self, mock_obj):
        self.policy.change_policy_definition({
            "actions:create": "role:FAKE or rule:admin_or_owner",
            "actions:publicize": "role:FAKE or rule:admin_or_owner"
        })
        resp = self.app.post(
            '/v2/actions?scope=public',
            ACTION_DEFINITION,
            headers={'Content-Type': 'text/plain'},
            expect_errors=True
        )

        self.assertEqual(201, resp.status_int)

    @mock.patch.object(db_api, "delete_action_definition", MOCK_DELETE)
    @mock.patch.object(db_api, "get_action_definition", MOCK_ACTION)
    def test_action_delete_not_allowed(self):
        self.policy.change_policy_definition(
            {"actions:delete": "role:FAKE"}
        )
        resp = self.app.delete(
            '/v2/actions/123',
            expect_errors=True
        )

        self.assertEqual(403, resp.status_int)

    @mock.patch.object(db_api, "delete_action_definition", MOCK_DELETE)
    @mock.patch.object(db_api, "get_action_definition", MOCK_ACTION)
    def test_action_delete_allowed(self):
        self.policy.change_policy_definition(
            {"actions:delete": "role:FAKE or rule:admin_or_owner"}
        )
        resp = self.app.delete(
            '/v2/actions/123',
            expect_errors=True
        )

        self.assertEqual(204, resp.status_int)

    @mock.patch.object(db_api, "get_action_definition", MOCK_ACTION)
    def test_action_get_not_allowed(self):
        self.policy.change_policy_definition(
            {"actions:get": "role:FAKE"}
        )
        resp = self.app.get(
            '/v2/actions/123',
            expect_errors=True
        )

        self.assertEqual(403, resp.status_int)

    @mock.patch.object(db_api, "get_action_definition", MOCK_ACTION)
    def test_action_get_allowed(self):
        self.policy.change_policy_definition(
            {"actions:get": "role:FAKE or rule:admin_or_owner"}
        )
        resp = self.app.get(
            '/v2/actions/123',
            expect_errors=True
        )

        self.assertEqual(200, resp.status_int)

    def test_action_list_not_allowed(self):
        self.policy.change_policy_definition(
            {"actions:list": "role:FAKE"}
        )
        resp = self.app.get(
            '/v2/actions',
            expect_errors=True
        )

        self.assertEqual(403, resp.status_int)

    def test_action_list_allowed(self):
        self.policy.change_policy_definition(
            {"actions:list": "role:FAKE or rule:admin_or_owner"}
        )
        resp = self.app.get(
            '/v2/actions',
            expect_errors=True
        )

        self.assertEqual(200, resp.status_int)

    @mock.patch.object(db_api, "update_action_definition")
    def test_action_update_not_allowed(self, mock_obj):
        self.policy.change_policy_definition(
            {"actions:update": "role:FAKE"}
        )
        resp = self.app.put(
            '/v2/actions',
            ACTION_DEFINITION,
            headers={'Content-Type': 'text/plain'},
            expect_errors=True
        )

        self.assertEqual(403, resp.status_int)

    @mock.patch.object(db_api, "update_action_definition")
    def test_action_update_allowed(self, mock_obj):
        self.policy.change_policy_definition(
            {"actions:update": "role:FAKE or rule:admin_or_owner"}
        )
        resp = self.app.put(
            '/v2/actions',
            ACTION_DEFINITION,
            headers={'Content-Type': 'text/plain'},
            expect_errors=True
        )

        self.assertEqual(200, resp.status_int)

    @mock.patch.object(db_api, "update_action_definition")
    def test_action_update_public_not_allowed(self, mock_obj):
        self.policy.change_policy_definition({
            "actions:update": "role:FAKE or rule:admin_or_owner",
            "actions:publicize": "role:FAKE"
        })
        resp = self.app.put(
            '/v2/actions?scope=public',
            ACTION_DEFINITION,
            headers={'Content-Type': 'text/plain'},
            expect_errors=True
        )

        self.assertEqual(403, resp.status_int)

    @mock.patch.object(db_api, "update_action_definition")
    def test_action_update_public_allowed(self, mock_obj):
        self.policy.change_policy_definition({
            "actions:update": "role:FAKE or rule:admin_or_owner",
            "actions:publicize": "role:FAKE or rule:admin_or_owner"
        })
        resp = self.app.put(
            '/v2/actions?scope=public',
            ACTION_DEFINITION,
            headers={'Content-Type': 'text/plain'},
            expect_errors=True
        )

        self.assertEqual(200, resp.status_int)
