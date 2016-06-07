# -*- coding: utf-8 -*-
#
# Copyright 2014 - Mirantis, Inc.
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
import mock

from mistral.db.v2 import api as db_api
from mistral.db.v2.sqlalchemy import models
from mistral import exceptions as exc
from mistral.tests.unit.api import base

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
    'id': '123',
    'name': 'my_cron_trigger',
    'pattern': '* * * * *',
    'workflow_name': WF.name,
    'workflow_id': '123e4567-e89b-12d3-a456-426655440000',
    'workflow_input': '{}',
    'workflow_params': '{}',
    'scope': 'private',
    'remaining_executions': 42
}

trigger_values = copy.deepcopy(TRIGGER)
trigger_values['workflow_input'] = json.loads(
    trigger_values['workflow_input'])

trigger_values['workflow_params'] = json.loads(
    trigger_values['workflow_params'])

TRIGGER_DB = models.CronTrigger()
TRIGGER_DB.update(trigger_values)

MOCK_WF = mock.MagicMock(return_value=WF)
MOCK_TRIGGER = mock.MagicMock(return_value=TRIGGER_DB)
MOCK_TRIGGERS = mock.MagicMock(return_value=[TRIGGER_DB])
MOCK_DELETE = mock.MagicMock(return_value=None)
MOCK_EMPTY = mock.MagicMock(return_value=[])
MOCK_NOT_FOUND = mock.MagicMock(side_effect=exc.DBEntityNotFoundError())
MOCK_DUPLICATE = mock.MagicMock(side_effect=exc.DBDuplicateEntryError())


class TestCronTriggerController(base.APITest):
    @mock.patch.object(db_api, "get_cron_trigger", MOCK_TRIGGER)
    def test_get(self):
        resp = self.app.get('/v2/cron_triggers/my_cron_trigger')

        self.assertEqual(200, resp.status_int)
        self.assertDictEqual(TRIGGER, resp.json)

    @mock.patch.object(db_api, "get_cron_trigger", MOCK_NOT_FOUND)
    def test_get_not_found(self):
        resp = self.app.get(
            '/v2/cron_triggers/my_cron_trigger',
            expect_errors=True
        )

        self.assertEqual(404, resp.status_int)

    @mock.patch.object(db_api, "get_workflow_definition", MOCK_WF)
    @mock.patch.object(db_api, "create_cron_trigger")
    def test_post(self, mock_mtd):
        mock_mtd.return_value = TRIGGER_DB

        resp = self.app.post_json('/v2/cron_triggers', TRIGGER)

        self.assertEqual(201, resp.status_int)
        self.assertDictEqual(TRIGGER, resp.json)

        self.assertEqual(1, mock_mtd.call_count)

        values = mock_mtd.call_args[0][0]

        self.assertEqual('* * * * *', values['pattern'])
        self.assertEqual(42, values['remaining_executions'])

    @mock.patch.object(db_api, "get_workflow_definition", MOCK_WF)
    @mock.patch.object(db_api, "create_cron_trigger", MOCK_DUPLICATE)
    def test_post_dup(self):
        resp = self.app.post_json(
            '/v2/cron_triggers', TRIGGER, expect_errors=True
        )

        self.assertEqual(409, resp.status_int)

    @mock.patch.object(db_api, "get_workflow_definition", MOCK_WF)
    @mock.patch.object(db_api, "create_cron_trigger", MOCK_DUPLICATE)
    def test_post_same_wf_and_input(self):
        trig = TRIGGER.copy()
        trig['name'] = 'some_trigger_name'

        resp = self.app.post_json(
            '/v2/cron_triggers', trig, expect_errors=True
        )

        self.assertEqual(409, resp.status_int)

    @mock.patch.object(db_api, "get_cron_trigger", MOCK_TRIGGER)
    @mock.patch.object(db_api, "delete_cron_trigger", MOCK_DELETE)
    def test_delete(self):
        resp = self.app.delete('/v2/cron_triggers/my_cron_trigger')

        self.assertEqual(204, resp.status_int)

    @mock.patch.object(db_api, "delete_cron_trigger", MOCK_NOT_FOUND)
    def test_delete_not_found(self):
        resp = self.app.delete(
            '/v2/cron_triggers/my_cron_trigger',
            expect_errors=True
        )

        self.assertEqual(404, resp.status_int)

    @mock.patch.object(db_api, "get_cron_triggers", MOCK_TRIGGERS)
    def test_get_all(self):
        resp = self.app.get('/v2/cron_triggers')

        self.assertEqual(200, resp.status_int)

        self.assertEqual(1, len(resp.json['cron_triggers']))
        self.assertDictEqual(TRIGGER, resp.json['cron_triggers'][0])

    @mock.patch.object(db_api, "get_cron_triggers", MOCK_EMPTY)
    def test_get_all_empty(self):
        resp = self.app.get('/v2/cron_triggers')

        self.assertEqual(200, resp.status_int)

        self.assertEqual(0, len(resp.json['cron_triggers']))
