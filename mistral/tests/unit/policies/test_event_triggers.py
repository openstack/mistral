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


import copy
import json
from unittest import mock

from mistral.db.v2 import api as db_api
from mistral.db.v2.sqlalchemy import models
from mistral.tests.unit.api import base
from mistral.tests.unit.mstrlfixtures import policy_fixtures

TRIGGER_ID = '09cc56a9-d15e-4494-a6e2-c4ec8bdaacae'
TRUST_ID = 'b1a78338-285e-4303-96aa-addadc87f054'
TRIGGER = {
    'name': 'my_event_trigger',
    'workflow_id': '123e4567-e89b-12d3-a456-426655440000',
    'workflow_input': '{}',
    'workflow_params': '{}',
    'scope': 'private',
    'exchange': 'openstack',
    'topic': 'notification',
    'event': 'compute.instance.create.start'
}

trigger_values = copy.deepcopy(TRIGGER)
trigger_values['id'] = TRIGGER_ID
trigger_values['trust_id'] = TRUST_ID
trigger_values['workflow_input'] = json.loads(
    trigger_values['workflow_input'])
trigger_values['workflow_params'] = json.loads(
    trigger_values['workflow_params'])

TRIGGER_DB = models.EventTrigger()
TRIGGER_DB.update(trigger_values)

MOCK_TRIGGER = mock.MagicMock(return_value=TRIGGER_DB)
MOCK_TRIGGERS = mock.MagicMock(return_value=[TRIGGER_DB])
MOCK_NONE = mock.MagicMock(return_value=None)
MOCK_DELETE = mock.MagicMock(return_value=None)


class TestEventTriggerPolicy(base.APITest):
    """Test event trigger related policies

    Policies to test:
    - event_triggers:create
    - event_triggers:publicize (on POST & PUT)
    - event_triggers:delete
    - event_triggers:get
    - event_triggers:list
    - event_triggers:list:all_projects
    - event_triggers:update
    """

    def setUp(self):
        super(TestEventTriggerPolicy, self).setUp()

        self.policy = self.useFixture(policy_fixtures.PolicyFixture())

    @mock.patch.object(db_api, "get_event_trigger", MOCK_TRIGGER)
    def test_event_trigger_get_not_allowed(self):
        self.policy.change_policy_definition(
            {"event_triggers:get": "role:FAKE"}
        )

        resp = self.app.get(
            '/v2/event_triggers/09cc56a9-d15e-4494-a6e2-c4ec8bdaacae',
            expect_errors=True
        )

        self.assertEqual(403, resp.status_int)

    @mock.patch.object(db_api, "get_event_trigger", MOCK_TRIGGER)
    def test_event_trigger_get_allowed(self):
        self.policy.change_policy_definition(
            {"event_triggers:get": "role:FAKE or rule:admin_or_owner"}
        )

        resp = self.app.get(
            '/v2/event_triggers/09cc56a9-d15e-4494-a6e2-c4ec8bdaacae'
        )

        self.assertEqual(200, resp.status_int)

    def test_event_trigger_list_not_allowed(self):
        self.policy.change_policy_definition(
            {"event_triggers:list": "role:FAKE"}
        )

        resp = self.app.get(
            '/v2/event_triggers',
            expect_errors=True
        )

        self.assertEqual(403, resp.status_int)

    def test_event_trigger_list_allowed(self):
        self.policy.change_policy_definition(
            {"event_triggers:list": "role:FAKE or rule:admin_or_owner"}
        )

        resp = self.app.get(
            '/v2/event_triggers'
        )

        self.assertEqual(200, resp.status_int)

    def test_event_trigger_list_all_not_allowed(self):
        self.policy.change_policy_definition({
            "event_triggers:list": "role:FAKE or rule:admin_or_owner",
            "event_triggers:list:all_projects": "role:FAKE"
        })

        resp = self.app.get(
            '/v2/event_triggers?all_projects=1',
            expect_errors=True
        )

        self.assertEqual(403, resp.status_int)

    def test_event_trigger_list_all_allowed(self):
        self.policy.change_policy_definition({
            "event_triggers:list": "role:FAKE or rule:admin_or_owner",
            "event_triggers:list:all_projects":
                "role:FAKE or rule:admin_or_owner"
        })

        resp = self.app.get(
            '/v2/event_triggers?all_projects=1'
        )

        self.assertEqual(200, resp.status_int)

    def test_event_trigger_create_not_allowed(self):
        self.policy.change_policy_definition(
            {"event_triggers:create": "role:FAKE"}
        )

        resp = self.app.post_json(
            '/v2/event_triggers',
            TRIGGER,
            expect_errors=True
        )

        self.assertEqual(403, resp.status_int)

    @mock.patch('mistral.services.triggers.create_event_trigger',
                return_value=TRIGGER_DB)
    def test_event_trigger_create_allowed(self, mock_obj):
        self.policy.change_policy_definition(
            {"event_triggers:create": "role:FAKE or rule:admin_or_owner"}
        )

        resp = self.app.post_json(
            '/v2/event_triggers',
            TRIGGER
        )

        self.assertEqual(201, resp.status_int)

    def test_event_trigger_create_public_not_allowed(self):
        # Default policy requires admin_only for event_triggers:publicize.
        # The default test context has is_admin=False, so a regular user
        # (project owner) should be denied.
        trigger = copy.deepcopy(TRIGGER)
        trigger['scope'] = 'public'

        resp = self.app.post_json(
            '/v2/event_triggers',
            trigger,
            expect_errors=True
        )

        self.assertEqual(403, resp.status_int)

    @mock.patch('mistral.services.triggers.create_event_trigger',
                return_value=TRIGGER_DB)
    def test_event_trigger_create_public_allowed(self, mock_obj):
        # Default policy requires admin_only for event_triggers:publicize.
        # An admin user should be allowed.
        self.ctx.is_admin = True
        self.addCleanup(setattr, self.ctx, 'is_admin', False)

        trigger = copy.deepcopy(TRIGGER)
        trigger['scope'] = 'public'

        resp = self.app.post_json(
            '/v2/event_triggers',
            trigger
        )

        self.assertEqual(201, resp.status_int)

    @mock.patch.object(db_api, 'get_event_trigger', MOCK_NONE)
    @mock.patch('mistral.rpc.clients.get_event_engine_client')
    @mock.patch('mistral.db.v2.api.update_event_trigger')
    def test_event_trigger_update_not_allowed(self, mock_update,
                                              mock_rpc_client):
        self.policy.change_policy_definition(
            {"event_triggers:update": "role:FAKE"}
        )

        resp = self.app.put_json(
            '/v2/event_triggers/09cc56a9-d15e-4494-a6e2-c4ec8bdaacae',
            {'name': 'new_name'},
            expect_errors=True
        )

        self.assertEqual(403, resp.status_int)

    @mock.patch.object(db_api, 'get_event_trigger', MOCK_NONE)
    @mock.patch('mistral.rpc.clients.get_event_engine_client')
    @mock.patch('mistral.db.v2.api.update_event_trigger')
    def test_event_trigger_update_allowed(self, mock_update,
                                          mock_rpc_client):
        client = mock.Mock()
        mock_rpc_client.return_value = client

        UPDATED_TRIGGER = models.EventTrigger()
        UPDATED_TRIGGER.update(trigger_values)
        UPDATED_TRIGGER.update({'name': 'new_name'})
        mock_update.return_value = UPDATED_TRIGGER

        self.policy.change_policy_definition(
            {"event_triggers:update": "role:FAKE or rule:admin_or_owner"}
        )

        resp = self.app.put_json(
            '/v2/event_triggers/09cc56a9-d15e-4494-a6e2-c4ec8bdaacae',
            {'name': 'new_name'}
        )

        self.assertEqual(200, resp.status_int)

    @mock.patch.object(db_api, 'get_event_trigger', MOCK_NONE)
    @mock.patch('mistral.rpc.clients.get_event_engine_client')
    @mock.patch('mistral.db.v2.api.update_event_trigger')
    def test_event_trigger_update_public_not_allowed(self, mock_update,
                                                     mock_rpc_client):
        # Default policy requires admin_only for event_triggers:publicize.
        # The default test context has is_admin=False, so a regular user
        # (project owner) should be denied.
        resp = self.app.put_json(
            '/v2/event_triggers/09cc56a9-d15e-4494-a6e2-c4ec8bdaacae',
            {'scope': 'public'},
            expect_errors=True
        )

        self.assertEqual(403, resp.status_int)

    @mock.patch.object(db_api, 'get_event_trigger', MOCK_NONE)
    @mock.patch('mistral.rpc.clients.get_event_engine_client')
    @mock.patch('mistral.db.v2.api.update_event_trigger')
    def test_event_trigger_update_public_allowed(self, mock_update,
                                                 mock_rpc_client):
        # Default policy requires admin_only for event_triggers:publicize.
        # An admin user should be allowed.
        self.ctx.is_admin = True
        self.addCleanup(setattr, self.ctx, 'is_admin', False)

        client = mock.Mock()
        mock_rpc_client.return_value = client

        UPDATED_TRIGGER = models.EventTrigger()
        UPDATED_TRIGGER.update(trigger_values)
        UPDATED_TRIGGER.update({'scope': 'public'})
        mock_update.return_value = UPDATED_TRIGGER

        resp = self.app.put_json(
            '/v2/event_triggers/09cc56a9-d15e-4494-a6e2-c4ec8bdaacae',
            {'scope': 'public'}
        )

        self.assertEqual(200, resp.status_int)

    @mock.patch.object(db_api, "get_event_trigger", MOCK_TRIGGER)
    @mock.patch.object(db_api, "delete_event_trigger", MOCK_DELETE)
    @mock.patch('mistral.services.security.delete_trust', MOCK_NONE)
    @mock.patch('mistral.rpc.clients.get_event_engine_client')
    def test_event_trigger_delete_not_allowed(self, mock_rpc_client):
        self.policy.change_policy_definition(
            {"event_triggers:delete": "role:FAKE"}
        )

        resp = self.app.delete(
            '/v2/event_triggers/09cc56a9-d15e-4494-a6e2-c4ec8bdaacae',
            expect_errors=True
        )

        self.assertEqual(403, resp.status_int)

    @mock.patch.object(db_api, "get_event_trigger", MOCK_TRIGGER)
    @mock.patch.object(db_api, "delete_event_trigger", MOCK_DELETE)
    @mock.patch('mistral.services.security.delete_trust', MOCK_NONE)
    @mock.patch('mistral.rpc.clients.get_event_engine_client')
    def test_event_trigger_delete_allowed(self, mock_rpc_client):
        client = mock.Mock()
        mock_rpc_client.return_value = client

        self.policy.change_policy_definition(
            {"event_triggers:delete": "role:FAKE or rule:admin_or_owner"}
        )

        resp = self.app.delete(
            '/v2/event_triggers/09cc56a9-d15e-4494-a6e2-c4ec8bdaacae'
        )

        self.assertEqual(204, resp.status_int)
