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

WF = models.WorkflowDefinition(
    spec={
        'version': '2.0',
        'name': 'my_wf',
        'tasks': {
            'task1': {
                'action': 'std.noop'
            }
        }
    }
)
WF.update({'id': '123e4567-e89b-12d3-a456-426655440000', 'name': 'my_wf'})

TRIGGER = {
    'name': 'my_cron_trigger',
    'pattern': '* * * * *',
    'workflow_name': 'my_wf',
    'workflow_id': '123e4567-e89b-12d3-a456-426655440000',
    'workflow_input': '{}',
    'workflow_params': '{}',
    'scope': 'private',
    'remaining_executions': 42
}

TRIGGER_DB = models.CronTrigger()
TRIGGER_DB.update({
    'id': '02abb422-55ef-4bb2-8cb9-217a583a6a3f',
    'name': 'my_cron_trigger',
    'pattern': '* * * * *',
    'workflow_name': 'my_wf',
    'workflow_id': '123e4567-e89b-12d3-a456-426655440000',
    'workflow_input': {},
    'workflow_params': {},
    'scope': 'private',
    'remaining_executions': 42
})

MOCK_WF = mock.MagicMock(return_value=WF)
MOCK_TRIGGER = mock.MagicMock(return_value=TRIGGER_DB)
MOCK_TRIGGERS = mock.MagicMock(return_value=[TRIGGER_DB])
MOCK_DELETE = mock.MagicMock(return_value=1)


class TestCronTriggerPolicy(base.APITest):
    """Test cron trigger related policies

    Policies to test:
    - cron_triggers:create
    - cron_triggers:publicize (on POST)
    - cron_triggers:delete
    - cron_triggers:get
    - cron_triggers:list
    - cron_triggers:list:all_projects
    """

    def setUp(self):
        self.policy = self.useFixture(policy_fixtures.PolicyFixture())
        super(TestCronTriggerPolicy, self).setUp()

    @mock.patch.object(db_api, "get_workflow_definition", MOCK_WF)
    @mock.patch.object(db_api, "create_cron_trigger")
    def test_cron_trigger_create_not_allowed(self, mock_obj):
        self.policy.change_policy_definition(
            {"cron_triggers:create": "role:FAKE"}
        )
        resp = self.app.post_json(
            '/v2/cron_triggers',
            TRIGGER,
            expect_errors=True
        )

        self.assertEqual(403, resp.status_int)

    @mock.patch.object(db_api, "get_workflow_definition", MOCK_WF)
    @mock.patch.object(db_api, "create_cron_trigger")
    def test_cron_trigger_create_allowed(self, mock_obj):
        mock_obj.return_value = TRIGGER_DB

        self.policy.change_policy_definition(
            {"cron_triggers:create": "role:FAKE or rule:admin_or_owner"}
        )
        resp = self.app.post_json(
            '/v2/cron_triggers',
            TRIGGER
        )

        self.assertEqual(201, resp.status_int)

    @mock.patch.object(db_api, "get_workflow_definition", MOCK_WF)
    @mock.patch.object(db_api, "create_cron_trigger")
    def test_cron_trigger_create_public_not_allowed(self, mock_obj):
        # Default policy requires admin_only for publicize.
        # The default test context has is_admin=False, so a regular user
        # (project owner) should be denied.
        trigger = dict(TRIGGER, scope='public')

        resp = self.app.post_json(
            '/v2/cron_triggers',
            trigger,
            expect_errors=True
        )

        self.assertEqual(403, resp.status_int)

    @mock.patch.object(db_api, "get_workflow_definition", MOCK_WF)
    @mock.patch.object(db_api, "create_cron_trigger")
    def test_cron_trigger_create_public_allowed(self, mock_obj):
        mock_obj.return_value = TRIGGER_DB

        # Default policy requires admin_only for publicize.
        # An admin user should be allowed.
        self.ctx.is_admin = True
        self.addCleanup(setattr, self.ctx, 'is_admin', False)

        trigger = dict(TRIGGER, scope='public')

        resp = self.app.post_json(
            '/v2/cron_triggers',
            trigger
        )

        self.assertEqual(201, resp.status_int)

    @mock.patch.object(db_api, "delete_cron_trigger", MOCK_DELETE)
    @mock.patch.object(db_api, "get_cron_trigger", MOCK_TRIGGER)
    def test_cron_trigger_delete_not_allowed(self):
        self.policy.change_policy_definition(
            {"cron_triggers:delete": "role:FAKE"}
        )
        resp = self.app.delete(
            '/v2/cron_triggers/my_cron_trigger',
            expect_errors=True
        )

        self.assertEqual(403, resp.status_int)

    @mock.patch.object(db_api, "delete_cron_trigger", MOCK_DELETE)
    @mock.patch.object(db_api, "get_cron_trigger", MOCK_TRIGGER)
    def test_cron_trigger_delete_allowed(self):
        self.policy.change_policy_definition(
            {"cron_triggers:delete": "role:FAKE or rule:admin_or_owner"}
        )
        resp = self.app.delete(
            '/v2/cron_triggers/my_cron_trigger'
        )

        self.assertEqual(204, resp.status_int)

    @mock.patch.object(db_api, "get_cron_trigger", MOCK_TRIGGER)
    def test_cron_trigger_get_not_allowed(self):
        self.policy.change_policy_definition(
            {"cron_triggers:get": "role:FAKE"}
        )
        resp = self.app.get(
            '/v2/cron_triggers/my_cron_trigger',
            expect_errors=True
        )

        self.assertEqual(403, resp.status_int)

    @mock.patch.object(db_api, "get_cron_trigger", MOCK_TRIGGER)
    def test_cron_trigger_get_allowed(self):
        self.policy.change_policy_definition(
            {"cron_triggers:get": "role:FAKE or rule:admin_or_owner"}
        )
        resp = self.app.get(
            '/v2/cron_triggers/my_cron_trigger'
        )

        self.assertEqual(200, resp.status_int)

    def test_cron_trigger_list_not_allowed(self):
        self.policy.change_policy_definition(
            {"cron_triggers:list": "role:FAKE"}
        )
        resp = self.app.get(
            '/v2/cron_triggers',
            expect_errors=True
        )

        self.assertEqual(403, resp.status_int)

    def test_cron_trigger_list_allowed(self):
        self.policy.change_policy_definition(
            {"cron_triggers:list": "role:FAKE or rule:admin_or_owner"}
        )
        resp = self.app.get(
            '/v2/cron_triggers'
        )

        self.assertEqual(200, resp.status_int)

    def test_cron_trigger_list_all_not_allowed(self):
        self.policy.change_policy_definition({
            "cron_triggers:list": "role:FAKE or rule:admin_or_owner",
            "cron_triggers:list:all_projects": "role:FAKE"
        })
        resp = self.app.get(
            '/v2/cron_triggers?all_projects=1',
            expect_errors=True
        )

        self.assertEqual(403, resp.status_int)

    def test_cron_trigger_list_all_allowed(self):
        self.policy.change_policy_definition({
            "cron_triggers:list": "role:FAKE or rule:admin_or_owner",
            "cron_triggers:list:all_projects":
                "role:FAKE or rule:admin_or_owner"
        })
        resp = self.app.get(
            '/v2/cron_triggers?all_projects=1'
        )

        self.assertEqual(200, resp.status_int)
