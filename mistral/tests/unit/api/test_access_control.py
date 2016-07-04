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

from mistral.api import access_control as acl
from mistral import exceptions as exc
from mistral.tests.unit import base
from mistral.tests.unit.mstrlfixtures import policy_fixtures


class PolicyTestCase(base.BaseTest):
    """Tests whether the configuration of the policy engine is corect."""
    def setUp(self):
        super(PolicyTestCase, self).setUp()

        self.policy = self.useFixture(policy_fixtures.PolicyFixture())

        rules = {
            "admin_only": "is_admin:True",
            "admin_or_owner": "is_admin:True or project_id:%(project_id)s",

            "example:admin": "rule:admin_only",
            "example:admin_or_owner": "rule:admin_or_owner"
        }

        self.policy.set_rules(rules)

    def test_admin_api_allowed(self):
        auth_ctx = base.get_context(default=True, admin=True)

        self.assertTrue(
            acl.enforce('example:admin', auth_ctx, auth_ctx.to_dict())
        )

    def test_admin_api_disallowed(self):
        auth_ctx = base.get_context(default=True)

        self.assertRaises(
            exc.NotAllowedException,
            acl.enforce,
            'example:admin',
            auth_ctx,
            auth_ctx.to_dict()
        )

    def test_admin_or_owner_api_allowed(self):
        auth_ctx = base.get_context(default=True)

        self.assertTrue(
            acl.enforce('example:admin_or_owner', auth_ctx, auth_ctx.to_dict())
        )

    def test_admin_or_owner_api_disallowed(self):
        auth_ctx = base.get_context(default=True)
        target = {'project_id': 'another'}

        self.assertRaises(
            exc.NotAllowedException,
            acl.enforce,
            'example:admin_or_owner',
            auth_ctx,
            target
        )
