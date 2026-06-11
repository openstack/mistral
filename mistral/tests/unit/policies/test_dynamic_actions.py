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


from mistral.db.v2 import api as db_api
from mistral.tests.unit.api import base
from mistral.tests.unit.mstrlfixtures import policy_fixtures

TEST_MODULE_TEXT = """
from mistral_lib import actions

class DummyAction(actions.Action):
    def run(self, context):
        return "Hello from the dummy action 1!"

    def test(self, context):
        return None
"""


class TestDynamicActionPolicy(base.APITest):
    """Test dynamic action related policies

    Policies to test:
    - dynamic_actions:create
    - dynamic_actions:delete
    - dynamic_actions:get
    - dynamic_actions:list
    - dynamic_actions:update
    """

    def setUp(self):
        super(TestDynamicActionPolicy, self).setUp()

        self.policy = self.useFixture(policy_fixtures.PolicyFixture())

        # Create a code source as admin so dynamic action tests have
        # something to reference.
        self.ctx.is_admin = True

        resp = self.app.post(
            '/v2/code_sources?name=test_dummy_module',
            TEST_MODULE_TEXT,
            headers={'Content-Type': 'text/plain'}
        )

        self.code_source_id = resp.json['id']

        self.ctx.is_admin = False

        self.addCleanup(db_api.delete_code_sources)
        self.addCleanup(db_api.delete_dynamic_action_definitions)

    def _create_dynamic_action_as_admin(self):
        self.ctx.is_admin = True

        resp = self.app.post_json(
            '/v2/dynamic_actions',
            {
                'name': 'dummy_action',
                'class_name': 'DummyAction',
                'code_source_id': self.code_source_id
            }
        )

        self.ctx.is_admin = False

        return resp

    def test_dynamic_action_create_not_allowed(self):
        # Default policy requires admin_only for create.
        # A non-admin user should be denied.
        resp = self.app.post_json(
            '/v2/dynamic_actions',
            {
                'name': 'dummy_action',
                'class_name': 'DummyAction',
                'code_source_id': self.code_source_id
            },
            expect_errors=True
        )

        self.assertEqual(403, resp.status_int)

    def test_dynamic_action_create_allowed(self):
        # Default policy requires admin_only. An admin should be allowed.
        self.ctx.is_admin = True
        self.addCleanup(setattr, self.ctx, 'is_admin', False)

        resp = self.app.post_json(
            '/v2/dynamic_actions',
            {
                'name': 'dummy_action',
                'class_name': 'DummyAction',
                'code_source_id': self.code_source_id
            }
        )

        self.assertEqual(201, resp.status_int)

    def test_dynamic_action_get_not_allowed(self):
        # Create as admin first, then try to get as non-admin.
        self._create_dynamic_action_as_admin()

        resp = self.app.get(
            '/v2/dynamic_actions/dummy_action',
            expect_errors=True
        )

        self.assertEqual(403, resp.status_int)

    def test_dynamic_action_get_allowed(self):
        self._create_dynamic_action_as_admin()

        self.ctx.is_admin = True
        self.addCleanup(setattr, self.ctx, 'is_admin', False)

        resp = self.app.get('/v2/dynamic_actions/dummy_action')

        self.assertEqual(200, resp.status_int)

    def test_dynamic_action_list_not_allowed(self):
        resp = self.app.get(
            '/v2/dynamic_actions',
            expect_errors=True
        )

        self.assertEqual(403, resp.status_int)

    def test_dynamic_action_list_allowed(self):
        self.ctx.is_admin = True
        self.addCleanup(setattr, self.ctx, 'is_admin', False)

        resp = self.app.get('/v2/dynamic_actions')

        self.assertEqual(200, resp.status_int)

    def test_dynamic_action_update_not_allowed(self):
        self._create_dynamic_action_as_admin()

        resp = self.app.put_json(
            '/v2/dynamic_actions',
            {
                'name': 'dummy_action',
                'class_name': 'NewDummyAction'
            },
            expect_errors=True
        )

        self.assertEqual(403, resp.status_int)

    def test_dynamic_action_update_allowed(self):
        self._create_dynamic_action_as_admin()

        self.ctx.is_admin = True
        self.addCleanup(setattr, self.ctx, 'is_admin', False)

        resp = self.app.put_json(
            '/v2/dynamic_actions',
            {
                'name': 'dummy_action',
                'class_name': 'NewDummyAction'
            }
        )

        self.assertEqual(200, resp.status_int)

    def test_dynamic_action_delete_not_allowed(self):
        self._create_dynamic_action_as_admin()

        resp = self.app.delete(
            '/v2/dynamic_actions/dummy_action',
            expect_errors=True
        )

        self.assertEqual(403, resp.status_int)

    def test_dynamic_action_delete_allowed(self):
        self._create_dynamic_action_as_admin()

        self.ctx.is_admin = True
        self.addCleanup(setattr, self.ctx, 'is_admin', False)

        self.app.delete('/v2/dynamic_actions/dummy_action')

        resp = self.app.get(
            '/v2/dynamic_actions/dummy_action',
            expect_errors=True
        )

        self.assertEqual(404, resp.status_int)
