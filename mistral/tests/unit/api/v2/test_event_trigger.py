# Copyright 2016 Catalyst IT Ltd
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

import copy
import json
from unittest import mock

import sqlalchemy as sa

from mistral.db.v2 import api as db_api
from mistral.db.v2.sqlalchemy import models
from mistral import exceptions as exc
from mistral.services import security
from mistral.services import triggers
from mistral.tests.unit.api import base
from mistral.tests.unit import base as unit_base

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
    'id': '09cc56a9-d15e-4494-a6e2-c4ec8bdaacae',
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
trigger_values['workflow_input'] = json.loads(
    trigger_values['workflow_input'])
trigger_values['workflow_params'] = json.loads(
    trigger_values['workflow_params'])

TRIGGER_DB = models.EventTrigger()
TRIGGER_DB.update(trigger_values)

MOCK_WF = mock.MagicMock(return_value=WF)
MOCK_TRIGGER = mock.MagicMock(return_value=TRIGGER_DB)
MOCK_TRIGGERS = mock.MagicMock(return_value=[TRIGGER_DB])
MOCK_NONE = mock.MagicMock(return_value=None)
MOCK_NOT_FOUND = mock.MagicMock(side_effect=exc.DBEntityNotFoundError())


class TestEventTriggerController(base.APITest):
    @mock.patch.object(db_api, "get_event_trigger", MOCK_TRIGGER)
    def test_get(self):
        resp = self.app.get(
            '/v2/event_triggers/09cc56a9-d15e-4494-a6e2-c4ec8bdaacae'
        )

        self.assertEqual(200, resp.status_int)
        self.assertDictEqual(TRIGGER, resp.json)

    @mock.patch('mistral.db.v2.api.get_event_trigger')
    def test_get_with_fields_filter(self, mocked_get):
        mocked_get.return_value = (TRIGGER['id'], TRIGGER['name'],)
        resp = self.app.get(
            '/v2/event_triggers/09cc56a9-d15e-4494-a6e2-c4ec8bdaacae'
            '?fields=name'
        )
        expected = {
            'id': TRIGGER['id'],
            'name': TRIGGER['name'],
        }

        self.assertEqual(200, resp.status_int)
        self.assertDictEqual(expected, resp.json)

    @mock.patch.object(db_api, 'get_event_trigger')
    def test_get_operational_error(self, mocked_get):
        mocked_get.side_effect = [
            # Emulating DB OperationalError
            sa.exc.OperationalError('Mock', 'mock', 'mock'),
            TRIGGER_DB  # Successful run
        ]

        resp = self.app.get(
            '/v2/event_triggers/09cc56a9-d15e-4494-a6e2-c4ec8bdaacae'
        )

        self.assertEqual(200, resp.status_int)
        self.assertDictEqual(TRIGGER, resp.json)

    @mock.patch.object(db_api, "get_event_trigger", MOCK_NOT_FOUND)
    def test_get_not_found(self):
        resp = self.app.get(
            '/v2/event_triggers/09cc56a9-d15e-4494-a6e2-c4ec8bdaacae',
            expect_errors=True
        )

        self.assertEqual(404, resp.status_int)

    @mock.patch.object(db_api, "get_workflow_definition_by_id", MOCK_WF)
    @mock.patch.object(db_api, "get_workflow_definition", MOCK_WF)
    @mock.patch.object(db_api, "create_event_trigger", MOCK_TRIGGER)
    @mock.patch.object(db_api, "get_event_triggers", MOCK_TRIGGERS)
    @mock.patch('mistral.rpc.clients.get_event_engine_client')
    def test_post(self, mock_rpc_client):
        client = mock.Mock()
        mock_rpc_client.return_value = client

        CREATE_TRIGGER = copy.deepcopy(TRIGGER)
        CREATE_TRIGGER.pop('id')

        resp = self.app.post_json('/v2/event_triggers', CREATE_TRIGGER)

        self.assertEqual(201, resp.status_int)
        self.assertEqual(1, client.create_event_trigger.call_count)

        trigger_db = TRIGGER_DB.to_dict()
        trigger_db['workflow_namespace'] = None

        self.assertDictEqual(
            trigger_db,
            client.create_event_trigger.call_args[0][0]
        )
        self.assertListEqual(
            ['compute.instance.create.start'],
            client.create_event_trigger.call_args[0][1]
        )

    @mock.patch.object(db_api, "get_workflow_definition_by_id", MOCK_WF)
    @mock.patch.object(db_api, "get_workflow_definition", MOCK_WF)
    @mock.patch.object(triggers, "create_event_trigger")
    def test_post_public(self, create_trigger):
        self.ctx = unit_base.get_context(default=False, admin=True)
        self.mock_ctx.return_value = self.ctx
        trigger = copy.deepcopy(TRIGGER)
        trigger['scope'] = 'public'
        trigger.pop('id')

        resp = self.app.post_json('/v2/event_triggers', trigger)

        self.assertEqual(201, resp.status_int)

        self.assertTrue(create_trigger.called)
        self.assertEqual('public', create_trigger.call_args[1]["scope"])

    def test_post_no_workflow_id(self):
        CREATE_TRIGGER = copy.deepcopy(TRIGGER)
        CREATE_TRIGGER.pop('id')
        CREATE_TRIGGER.pop('workflow_id')

        resp = self.app.post_json(
            '/v2/event_triggers',
            CREATE_TRIGGER,
            expect_errors=True
        )

        self.assertEqual(400, resp.status_int)

    @mock.patch.object(db_api, "get_workflow_definition_by_id", MOCK_NOT_FOUND)
    def test_post_workflow_not_found(self):
        CREATE_TRIGGER = copy.deepcopy(TRIGGER)
        CREATE_TRIGGER.pop('id')

        resp = self.app.post_json(
            '/v2/event_triggers',
            CREATE_TRIGGER,
            expect_errors=True
        )

        self.assertEqual(404, resp.status_int)

    @mock.patch.object(db_api, 'get_event_trigger', MOCK_NONE)
    @mock.patch('mistral.rpc.clients.get_event_engine_client')
    @mock.patch('mistral.db.v2.api.update_event_trigger')
    def test_put(self, mock_update, mock_rpc_client):
        client = mock.Mock()
        mock_rpc_client.return_value = client

        UPDATED_TRIGGER = models.EventTrigger()
        UPDATED_TRIGGER.update(trigger_values)
        UPDATED_TRIGGER.update({'name': 'new_name'})
        mock_update.return_value = UPDATED_TRIGGER

        resp = self.app.put_json(
            '/v2/event_triggers/09cc56a9-d15e-4494-a6e2-c4ec8bdaacae',
            {'name': 'new_name'}
        )

        self.assertEqual(200, resp.status_int)
        self.assertEqual(1, client.update_event_trigger.call_count)

        self.assertDictEqual(
            UPDATED_TRIGGER.to_dict(),
            client.update_event_trigger.call_args[0][0]
        )

    def test_put_field_not_allowed(self):
        resp = self.app.put_json(
            '/v2/event_triggers/09cc56a9-d15e-4494-a6e2-c4ec8bdaacae',
            {'exchange': 'new_exchange'},
            expect_errors=True
        )

        self.assertEqual(400, resp.status_int)

    @mock.patch('mistral.rpc.clients.get_event_engine_client')
    @mock.patch('mistral.db.v2.api.get_event_trigger')
    @mock.patch.object(db_api, "get_event_triggers",
                       mock.MagicMock(return_value=[]))
    @mock.patch.object(db_api, "delete_event_trigger", MOCK_NONE)
    @mock.patch.object(security, "delete_trust", MOCK_NONE)
    def test_delete(self, mock_delete, mock_rpc_client):
        client = mock.Mock()
        mock_rpc_client.return_value = client

        DELETE_TRIGGER = models.EventTrigger()
        DELETE_TRIGGER.update(trigger_values)
        DELETE_TRIGGER.update(
            {'trust_id': 'c30e50e8-ee7d-4f8a-9515-f0530d9dc54b'}
        )
        mock_delete.return_value = DELETE_TRIGGER

        resp = self.app.delete(
            '/v2/event_triggers/09cc56a9-d15e-4494-a6e2-c4ec8bdaacae'
        )

        self.assertEqual(204, resp.status_int)
        self.assertEqual(1, client.delete_event_trigger.call_count)

        self.assertDictEqual(
            DELETE_TRIGGER.to_dict(),
            client.delete_event_trigger.call_args[0][0]
        )
        self.assertListEqual(
            [],
            client.delete_event_trigger.call_args[0][1]
        )

    @mock.patch.object(db_api, "get_event_trigger", MOCK_NOT_FOUND)
    def test_delete_not_found(self):
        resp = self.app.delete(
            '/v2/event_triggers/09cc56a9-d15e-4494-a6e2-c4ec8bdaacae',
            expect_errors=True
        )

        self.assertEqual(404, resp.status_int)

    @mock.patch.object(db_api, "get_event_triggers", MOCK_TRIGGERS)
    def test_get_all(self):
        resp = self.app.get('/v2/event_triggers')

        self.assertEqual(200, resp.status_int)

        self.assertEqual(1, len(resp.json['event_triggers']))
        self.assertDictEqual(TRIGGER, resp.json['event_triggers'][0])

    @mock.patch.object(db_api, 'get_event_triggers')
    def test_get_all_operational_error(self, mocked_get_all):
        mocked_get_all.side_effect = [
            # Emulating DB OperationalError
            sa.exc.OperationalError('Mock', 'mock', 'mock'),
            [TRIGGER_DB]  # Successful run
        ]

        resp = self.app.get('/v2/event_triggers')

        self.assertEqual(200, resp.status_int)

        self.assertEqual(1, len(resp.json['event_triggers']))
        self.assertDictEqual(TRIGGER, resp.json['event_triggers'][0])

    @mock.patch('mistral.db.v2.api.get_event_triggers')
    @mock.patch('mistral.context.MistralContext.from_environ')
    def test_get_all_projects_admin(self, mock_context, mock_get_wf_defs):
        admin_ctx = unit_base.get_context(admin=True)
        mock_context.return_value = admin_ctx

        resp = self.app.get('/v2/event_triggers?all_projects=true')

        self.assertEqual(200, resp.status_int)

        self.assertTrue(mock_get_wf_defs.call_args[1].get('insecure', False))
