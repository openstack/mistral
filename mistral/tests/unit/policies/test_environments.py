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


from unittest import mock

from mistral.db.v2 import api as db_api
from mistral.db.v2.sqlalchemy import models
from mistral.tests.unit.api import base
from mistral.tests.unit.mstrlfixtures import policy_fixtures

ENVIRONMENT = {
    'name': 'test',
    'description': 'my test settings',
    'variables': {
        'server': 'localhost',
        'database': 'test',
        'timeout': 600,
        'verbose': True
    }
}

ENVIRONMENT_DB = models.Environment(
    id='123e4567-e89b-12d3-a456-426655440000',
    name='test',
    description='my test settings',
    variables={
        'server': 'localhost',
        'database': 'test',
        'timeout': 600,
        'verbose': True
    },
    scope='private'
)

MOCK_ENVIRONMENT = mock.MagicMock(return_value=ENVIRONMENT_DB)
MOCK_ENVIRONMENTS = mock.MagicMock(return_value=[ENVIRONMENT_DB])
MOCK_DELETE = mock.MagicMock(return_value=None)


class TestEnvironmentPolicy(base.APITest):
    """Test environment related policies

    Policies to test:
    - environments:create
    - environments:publicize (on POST & PUT)
    - environments:delete
    - environments:get
    - environments:list
    - environments:update
    """

    def setUp(self):
        self.policy = self.useFixture(policy_fixtures.PolicyFixture())
        super(TestEnvironmentPolicy, self).setUp()

    @mock.patch.object(db_api, "create_environment")
    def test_environment_create_not_allowed(self, mock_obj):
        self.policy.change_policy_definition(
            {"environments:create": "role:FAKE"}
        )
        resp = self.app.post_json(
            '/v2/environments',
            ENVIRONMENT,
            expect_errors=True
        )

        self.assertEqual(403, resp.status_int)

    @mock.patch.object(db_api, "create_environment")
    def test_environment_create_allowed(self, mock_obj):
        mock_obj.return_value = ENVIRONMENT_DB

        self.policy.change_policy_definition(
            {"environments:create": "role:FAKE or rule:admin_or_owner"}
        )
        resp = self.app.post_json(
            '/v2/environments',
            ENVIRONMENT
        )

        self.assertEqual(201, resp.status_int)

    @mock.patch.object(db_api, "create_environment")
    def test_environment_create_public_not_allowed(self, mock_obj):
        # Default policy requires admin_only for publicize.
        # The default test context has is_admin=False, so a regular user
        # (project owner) should be denied.
        env = dict(ENVIRONMENT, scope='public')

        resp = self.app.post_json(
            '/v2/environments',
            env,
            expect_errors=True
        )

        self.assertEqual(403, resp.status_int)

    @mock.patch.object(db_api, "create_environment")
    def test_environment_create_public_allowed(self, mock_obj):
        mock_obj.return_value = ENVIRONMENT_DB

        # Default policy requires admin_only for publicize.
        # An admin user should be allowed.
        self.ctx.is_admin = True
        self.addCleanup(setattr, self.ctx, 'is_admin', False)

        env = dict(ENVIRONMENT, scope='public')

        resp = self.app.post_json(
            '/v2/environments',
            env
        )

        self.assertEqual(201, resp.status_int)

    @mock.patch.object(db_api, "delete_environment", MOCK_DELETE)
    def test_environment_delete_not_allowed(self):
        self.policy.change_policy_definition(
            {"environments:delete": "role:FAKE"}
        )
        resp = self.app.delete(
            '/v2/environments/test',
            expect_errors=True
        )

        self.assertEqual(403, resp.status_int)

    @mock.patch.object(db_api, "delete_environment", MOCK_DELETE)
    def test_environment_delete_allowed(self):
        self.policy.change_policy_definition(
            {"environments:delete": "role:FAKE or rule:admin_or_owner"}
        )
        resp = self.app.delete(
            '/v2/environments/test'
        )

        self.assertEqual(204, resp.status_int)

    @mock.patch.object(db_api, "get_environment", MOCK_ENVIRONMENT)
    def test_environment_get_not_allowed(self):
        self.policy.change_policy_definition(
            {"environments:get": "role:FAKE"}
        )
        resp = self.app.get(
            '/v2/environments/test',
            expect_errors=True
        )

        self.assertEqual(403, resp.status_int)

    @mock.patch.object(db_api, "get_environment", MOCK_ENVIRONMENT)
    def test_environment_get_allowed(self):
        self.policy.change_policy_definition(
            {"environments:get": "role:FAKE or rule:admin_or_owner"}
        )
        resp = self.app.get(
            '/v2/environments/test'
        )

        self.assertEqual(200, resp.status_int)

    def test_environment_list_not_allowed(self):
        self.policy.change_policy_definition(
            {"environments:list": "role:FAKE"}
        )
        resp = self.app.get(
            '/v2/environments',
            expect_errors=True
        )

        self.assertEqual(403, resp.status_int)

    def test_environment_list_allowed(self):
        self.policy.change_policy_definition(
            {"environments:list": "role:FAKE or rule:admin_or_owner"}
        )
        resp = self.app.get(
            '/v2/environments'
        )

        self.assertEqual(200, resp.status_int)

    @mock.patch.object(db_api, "update_environment")
    def test_environment_update_not_allowed(self, mock_obj):
        self.policy.change_policy_definition(
            {"environments:update": "role:FAKE"}
        )
        resp = self.app.put_json(
            '/v2/environments',
            ENVIRONMENT,
            expect_errors=True
        )

        self.assertEqual(403, resp.status_int)

    @mock.patch.object(db_api, "update_environment")
    def test_environment_update_allowed(self, mock_obj):
        mock_obj.return_value = ENVIRONMENT_DB

        self.policy.change_policy_definition(
            {"environments:update": "role:FAKE or rule:admin_or_owner"}
        )
        resp = self.app.put_json(
            '/v2/environments',
            ENVIRONMENT
        )

        self.assertEqual(200, resp.status_int)

    @mock.patch.object(db_api, "update_environment")
    def test_environment_update_public_not_allowed(self, mock_obj):
        # Default policy requires admin_only for publicize.
        # The default test context has is_admin=False, so a regular user
        # (project owner) should be denied.
        env = dict(ENVIRONMENT, scope='public')

        resp = self.app.put_json(
            '/v2/environments',
            env,
            expect_errors=True
        )

        self.assertEqual(403, resp.status_int)

    @mock.patch.object(db_api, "update_environment")
    def test_environment_update_public_allowed(self, mock_obj):
        mock_obj.return_value = ENVIRONMENT_DB

        # Default policy requires admin_only for publicize.
        # An admin user should be allowed.
        self.ctx.is_admin = True
        self.addCleanup(setattr, self.ctx, 'is_admin', False)

        env = dict(ENVIRONMENT, scope='public')

        resp = self.app.put_json(
            '/v2/environments',
            env
        )

        self.assertEqual(200, resp.status_int)
