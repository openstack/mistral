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
import mock

from mistral.db.v2 import api as db_api
from mistral.db.v2.sqlalchemy import models
from mistral import exceptions as exc
from mistral.tests.unit.api import base


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

SYSTEM_ACTION_DEFINITION = """
---
version: '2.0'

std.echo:
  base: std.http
  base-input:
    url: "some.url"
"""

ACTION = {
    'id': '123',
    'name': 'my_action',
    'is_system': False,
    'description': 'My super cool action.',
    'tags': ['test', 'v2'],
    'definition': ACTION_DEFINITION
}

SYSTEM_ACTION = {
    'id': '1234',
    'name': 'std.echo',
    'is_system': True,
    'definition': SYSTEM_ACTION_DEFINITION
}

ACTION_DB = models.ActionDefinition()
ACTION_DB.update(ACTION)

SYSTEM_ACTION_DB = models.ActionDefinition()
SYSTEM_ACTION_DB.update(SYSTEM_ACTION)

UPDATED_ACTION_DEFINITION = """
---
version: '2.0'

my_action:
  description: My super cool action.
  base: std.echo
  base-input:
    output: "{$.str1}{$.str2}{$.str3}"
"""

UPDATED_ACTION_DB = copy.copy(ACTION_DB)
UPDATED_ACTION_DB['definition'] = UPDATED_ACTION_DEFINITION
UPDATED_ACTION = copy.copy(ACTION)
UPDATED_ACTION['definition'] = UPDATED_ACTION_DEFINITION

MOCK_ACTION = mock.MagicMock(return_value=ACTION_DB)
MOCK_SYSTEM_ACTION = mock.MagicMock(return_value=SYSTEM_ACTION_DB)
MOCK_ACTIONS = mock.MagicMock(return_value=[ACTION_DB])
MOCK_UPDATED_ACTION = mock.MagicMock(return_value=UPDATED_ACTION_DB)
MOCK_DELETE = mock.MagicMock(return_value=None)
MOCK_EMPTY = mock.MagicMock(return_value=[])
MOCK_NOT_FOUND = mock.MagicMock(side_effect=exc.NotFoundException())
MOCK_DUPLICATE = mock.MagicMock(side_effect=exc.DBDuplicateEntry())


class TestActionsController(base.FunctionalTest):
    @mock.patch.object(db_api, "get_action_definition", MOCK_ACTION)
    def test_get(self):
        resp = self.app.get('/v2/actions/my_action')

        self.assertEqual(resp.status_int, 200)
        self.assertDictEqual(ACTION, resp.json)

    @mock.patch.object(db_api, "get_action_definition", MOCK_NOT_FOUND)
    def test_get_not_found(self):
        resp = self.app.get('/v2/actions/my_action', expect_errors=True)

        self.assertEqual(resp.status_int, 404)

    @mock.patch.object(db_api, "get_action_definition", MOCK_ACTION)
    @mock.patch.object(
        db_api, "create_or_update_action_definition", MOCK_UPDATED_ACTION
    )
    def test_put(self):
        resp = self.app.put(
            '/v2/actions',
            UPDATED_ACTION_DEFINITION,
            headers={'Content-Type': 'text/plain'}
        )

        self.assertEqual(resp.status_int, 200)

        self.assertEqual({"actions": [UPDATED_ACTION]}, resp.json)

    @mock.patch.object(
        db_api, "create_or_update_action_definition", MOCK_NOT_FOUND
    )
    def test_put_not_found(self):
        resp = self.app.put(
            '/v2/actions',
            UPDATED_ACTION_DEFINITION,
            headers={'Content-Type': 'text/plain'},
            expect_errors=True
        )

        self.assertEqual(404, resp.status_int)

    @mock.patch.object(db_api, "get_action_definition", MOCK_SYSTEM_ACTION)
    def test_put_system(self):
        resp = self.app.put(
            '/v2/actions',
            SYSTEM_ACTION_DEFINITION,
            headers={'Content-Type': 'text/plain'},
            expect_errors=True
        )

        self.assertEqual(resp.status_int, 400)
        self.assertIn('Attempt to modify a system action: std.echo',
                      resp.text)

    @mock.patch.object(db_api, "create_action_definition")
    def test_post(self, mock_mtd):
        mock_mtd.return_value = ACTION_DB

        resp = self.app.post(
            '/v2/actions',
            ACTION_DEFINITION,
            headers={'Content-Type': 'text/plain'}
        )

        self.assertEqual(resp.status_int, 201)
        self.assertEqual({"actions": [ACTION]}, resp.json)

        mock_mtd.assert_called_once()

        values = mock_mtd.call_args[0][0]

        self.assertEqual('My super cool action.', values['description'])

        spec = values['spec']

        self.assertIsNotNone(spec)
        self.assertEqual(ACTION_DB.name, spec['name'])

    @mock.patch.object(db_api, "create_action_definition", MOCK_DUPLICATE)
    def test_post_dup(self):
        resp = self.app.post(
            '/v2/actions',
            ACTION_DEFINITION,
            headers={'Content-Type': 'text/plain'},
            expect_errors=True
        )

        self.assertEqual(resp.status_int, 409)

    @mock.patch.object(db_api, "get_action_definition", MOCK_ACTION)
    @mock.patch.object(db_api, "delete_action_definition", MOCK_DELETE)
    def test_delete(self):
        resp = self.app.delete('/v2/actions/my_action')

        self.assertEqual(resp.status_int, 204)

    @mock.patch.object(db_api, "delete_action_definition", MOCK_NOT_FOUND)
    def test_delete_not_found(self):
        resp = self.app.delete('/v2/actions/my_action', expect_errors=True)

        self.assertEqual(resp.status_int, 404)

    @mock.patch.object(db_api, "get_action_definition", MOCK_SYSTEM_ACTION)
    def test_delete_system(self):
        resp = self.app.delete('/v2/actions/std.echo', expect_errors=True)

        self.assertEqual(resp.status_int, 400)
        self.assertIn('Attempt to delete a system action: std.echo',
                      resp.json['faultstring'])

    @mock.patch.object(db_api, "get_action_definitions", MOCK_ACTIONS)
    def test_get_all(self):
        resp = self.app.get('/v2/actions')

        self.assertEqual(resp.status_int, 200)

        self.assertEqual(len(resp.json['actions']), 1)
        self.assertDictEqual(ACTION, resp.json['actions'][0])

    @mock.patch.object(db_api, "get_action_definitions", MOCK_EMPTY)
    def test_get_all_empty(self):
        resp = self.app.get('/v2/actions')

        self.assertEqual(resp.status_int, 200)

        self.assertEqual(len(resp.json['actions']), 0)
