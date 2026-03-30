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

FILE_CONTENT = "test file"
MODULE_NAME = 'test_module'
NAMESPACE = 'NS'


class TestCodeSourcePolicy(base.APITest):
    """Test code source related policies

    Policies to test:
    - code_sources:create
    - code_sources:publicize (on POST & PUT)
    - code_sources:delete
    - code_sources:get
    - code_sources:list
    - code_sources:update
    """

    def setUp(self):
        super(TestCodeSourcePolicy, self).setUp()

        self.policy = self.useFixture(policy_fixtures.PolicyFixture())
        self.addCleanup(db_api.delete_code_sources)

    def test_code_source_create_not_allowed(self):
        # Default policy requires admin_only for create.
        # A non-admin user should be denied.
        resp = self.app.post(
            '/v2/code_sources?name=%s&namespace=%s' %
            (MODULE_NAME, NAMESPACE),
            FILE_CONTENT,
            headers={'Content-Type': 'text/plain'},
            expect_errors=True
        )

        self.assertEqual(403, resp.status_int)

    def test_code_source_create_allowed(self):
        # Default policy requires admin_only. An admin should be allowed.
        self.ctx.is_admin = True
        self.addCleanup(setattr, self.ctx, 'is_admin', False)

        resp = self.app.post(
            '/v2/code_sources?name=%s&namespace=%s' %
            (MODULE_NAME, NAMESPACE),
            FILE_CONTENT,
            headers={'Content-Type': 'text/plain'}
        )

        self.assertEqual(201, resp.status_int)

    def test_code_source_create_public_not_allowed(self):
        # Default policy requires admin_only for publicize.
        # The default test context has is_admin=False, so a regular user
        # (project owner) should be denied.
        resp = self.app.post(
            '/v2/code_sources?name=%s&namespace=%s&scope=public' %
            (MODULE_NAME, NAMESPACE),
            FILE_CONTENT,
            headers={'Content-Type': 'text/plain'},
            expect_errors=True
        )

        self.assertEqual(403, resp.status_int)

    def test_code_source_create_public_allowed(self):
        # Default policy requires admin_only for publicize.
        # An admin user should be allowed.
        self.ctx.is_admin = True
        self.addCleanup(setattr, self.ctx, 'is_admin', False)

        resp = self.app.post(
            '/v2/code_sources?name=%s&namespace=%s&scope=public' %
            (MODULE_NAME, NAMESPACE),
            FILE_CONTENT,
            headers={'Content-Type': 'text/plain'}
        )

        self.assertEqual(201, resp.status_int)

    def test_code_source_update_public_not_allowed(self):
        # First create a private code source as admin (to have something
        # to update).
        self.ctx.is_admin = True

        self.app.post(
            '/v2/code_sources?name=%s&namespace=%s' %
            (MODULE_NAME, NAMESPACE),
            FILE_CONTENT,
            headers={'Content-Type': 'text/plain'}
        )

        # Now switch back to non-admin and try to update to public.
        self.ctx.is_admin = False

        resp = self.app.put(
            '/v2/code_sources?identifier=%s&namespace=%s&scope=public' %
            (MODULE_NAME, NAMESPACE),
            FILE_CONTENT,
            headers={'Content-Type': 'text/plain'},
            expect_errors=True
        )

        self.assertEqual(403, resp.status_int)

    def test_code_source_update_public_allowed(self):
        # Create a private code source as admin first.
        self.ctx.is_admin = True
        self.addCleanup(setattr, self.ctx, 'is_admin', False)

        self.app.post(
            '/v2/code_sources?name=%s&namespace=%s' %
            (MODULE_NAME, NAMESPACE),
            FILE_CONTENT,
            headers={'Content-Type': 'text/plain'}
        )

        # Update to public as admin.
        resp = self.app.put(
            '/v2/code_sources?identifier=%s&namespace=%s&scope=public' %
            (MODULE_NAME, NAMESPACE),
            FILE_CONTENT,
            headers={'Content-Type': 'text/plain'}
        )

        self.assertEqual(200, resp.status_int)
