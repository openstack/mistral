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
from mistral import utils


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

ACTION_DEFINITION_INVALID_NO_BASE = """
---
version: '2.0'

my_action:
  description: My super cool action.
  tags: ['test', 'v2']

  base-input:
    output: "{$.str1}{$.str2}"
"""

ACTION_DEFINITION_INVALID_YAQL = """
---
version: '2.0'

my_action:
  description: My super cool action.
  tags: ['test', 'v2']
  base: std.echo
  base-input:
    output: <% $. %>
"""

ACTION_DSL_PARSE_EXCEPTION = """
---
%
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
    'id': '123e4567-e89b-12d3-a456-426655440000',
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
UPDATED_ACTION = copy.deepcopy(ACTION)
UPDATED_ACTION['definition'] = UPDATED_ACTION_DEFINITION

MOCK_ACTION = mock.MagicMock(return_value=ACTION_DB)
MOCK_SYSTEM_ACTION = mock.MagicMock(return_value=SYSTEM_ACTION_DB)
MOCK_ACTIONS = mock.MagicMock(return_value=[ACTION_DB])
MOCK_UPDATED_ACTION = mock.MagicMock(return_value=UPDATED_ACTION_DB)
MOCK_DELETE = mock.MagicMock(return_value=None)
MOCK_EMPTY = mock.MagicMock(return_value=[])
MOCK_NOT_FOUND = mock.MagicMock(side_effect=exc.DBEntityNotFoundError())
MOCK_DUPLICATE = mock.MagicMock(side_effect=exc.DBDuplicateEntryError())


class TestActionsController(base.APITest):
    @mock.patch.object(
        db_api, "get_action_definition", MOCK_ACTION)
    def test_get(self):
        resp = self.app.get('/v2/actions/my_action')

        self.assertEqual(200, resp.status_int)
        self.assertDictEqual(ACTION, resp.json)

    @mock.patch.object(
        db_api, "get_action_definition", MOCK_NOT_FOUND)
    def test_get_not_found(self):
        resp = self.app.get('/v2/actions/my_action', expect_errors=True)

        self.assertEqual(404, resp.status_int)

    @mock.patch.object(db_api, "update_action_definition", MOCK_UPDATED_ACTION)
    @mock.patch.object(
        db_api, "get_action_definition", MOCK_ACTION)
    def test_get_by_id(self):
        url = '/v2/actions/{0}'.format(ACTION['id'])
        resp = self.app.get(url)

        self.assertEqual(200, resp.status_int)
        self.assertEqual(ACTION['id'], resp.json['id'])

    @mock.patch.object(
        db_api, "get_action_definition", MOCK_NOT_FOUND)
    def test_get_by_id_not_found(self):
        url = '/v2/actions/1234'
        resp = self.app.get(url, expect_errors=True)

        self.assertEqual(404, resp.status_int)

    @mock.patch.object(
        db_api, "get_action_definition", MOCK_ACTION)
    @mock.patch.object(
        db_api, "update_action_definition", MOCK_UPDATED_ACTION
    )
    def test_put(self):
        resp = self.app.put(
            '/v2/actions',
            UPDATED_ACTION_DEFINITION,
            headers={'Content-Type': 'text/plain'}
        )

        self.assertEqual(200, resp.status_int)

        self.assertEqual({"actions": [UPDATED_ACTION]}, resp.json)

    @mock.patch.object(db_api, "load_action_definition", MOCK_ACTION)
    @mock.patch.object(db_api, "update_action_definition")
    def test_put_public(self, mock_mtd):
        mock_mtd.return_value = UPDATED_ACTION_DB

        resp = self.app.put(
            '/v2/actions?scope=public',
            UPDATED_ACTION_DEFINITION,
            headers={'Content-Type': 'text/plain'}
        )

        self.assertEqual(200, resp.status_int)

        self.assertEqual({"actions": [UPDATED_ACTION]}, resp.json)

        self.assertEqual("public", mock_mtd.call_args[0][1]['scope'])

    @mock.patch.object(db_api, "update_action_definition", MOCK_NOT_FOUND)
    def test_put_not_found(self):
        resp = self.app.put(
            '/v2/actions',
            UPDATED_ACTION_DEFINITION,
            headers={'Content-Type': 'text/plain'},
            expect_errors=True
        )

        self.assertEqual(404, resp.status_int)

    @mock.patch.object(
        db_api, "get_action_definition", MOCK_SYSTEM_ACTION)
    def test_put_system(self):
        resp = self.app.put(
            '/v2/actions',
            SYSTEM_ACTION_DEFINITION,
            headers={'Content-Type': 'text/plain'},
            expect_errors=True
        )

        self.assertEqual(400, resp.status_int)
        self.assertIn(
            'Attempt to modify a system action: std.echo',
            resp.body.decode()
        )

    @mock.patch.object(db_api, "create_action_definition")
    def test_post(self, mock_mtd):
        mock_mtd.return_value = ACTION_DB

        resp = self.app.post(
            '/v2/actions',
            ACTION_DEFINITION,
            headers={'Content-Type': 'text/plain'}
        )

        self.assertEqual(201, resp.status_int)
        self.assertEqual({"actions": [ACTION]}, resp.json)

        self.assertEqual(1, mock_mtd.call_count)

        values = mock_mtd.call_args[0][0]

        self.assertEqual('My super cool action.', values['description'])

        spec = values['spec']

        self.assertIsNotNone(spec)
        self.assertEqual(ACTION_DB.name, spec['name'])

    @mock.patch.object(db_api, "create_action_definition")
    def test_post_public(self, mock_mtd):
        mock_mtd.return_value = ACTION_DB

        resp = self.app.post(
            '/v2/actions?scope=public',
            ACTION_DEFINITION,
            headers={'Content-Type': 'text/plain'}
        )

        self.assertEqual(201, resp.status_int)
        self.assertEqual({"actions": [ACTION]}, resp.json)

        self.assertEqual("public", mock_mtd.call_args[0][0]['scope'])

    @mock.patch.object(db_api, "create_action_definition")
    def test_post_wrong_scope(self, mock_mtd):
        mock_mtd.return_value = ACTION_DB

        resp = self.app.post(
            '/v2/actions?scope=unique',
            ACTION_DEFINITION,
            headers={'Content-Type': 'text/plain'},
            expect_errors=True
        )

        self.assertEqual(400, resp.status_int)
        self.assertIn("Scope must be one of the following", resp.body.decode())

    @mock.patch.object(db_api, "create_action_definition", MOCK_DUPLICATE)
    def test_post_dup(self):
        resp = self.app.post(
            '/v2/actions',
            ACTION_DEFINITION,
            headers={'Content-Type': 'text/plain'},
            expect_errors=True
        )

        self.assertEqual(409, resp.status_int)

    @mock.patch.object(
        db_api, "get_action_definition", MOCK_ACTION)
    @mock.patch.object(db_api, "delete_action_definition", MOCK_DELETE)
    def test_delete(self):
        resp = self.app.delete('/v2/actions/my_action')

        self.assertEqual(204, resp.status_int)

    @mock.patch.object(db_api, "delete_action_definition", MOCK_NOT_FOUND)
    def test_delete_not_found(self):
        resp = self.app.delete('/v2/actions/my_action', expect_errors=True)

        self.assertEqual(404, resp.status_int)

    @mock.patch.object(
        db_api, "get_action_definition", MOCK_SYSTEM_ACTION)
    def test_delete_system(self):
        resp = self.app.delete('/v2/actions/std.echo', expect_errors=True)

        self.assertEqual(400, resp.status_int)
        self.assertIn('Attempt to delete a system action: std.echo',
                      resp.json['faultstring'])

    @mock.patch.object(
        db_api, "get_action_definitions", MOCK_ACTIONS)
    def test_get_all(self):
        resp = self.app.get('/v2/actions')

        self.assertEqual(200, resp.status_int)

        self.assertEqual(1, len(resp.json['actions']))
        self.assertDictEqual(ACTION, resp.json['actions'][0])

    @mock.patch.object(
        db_api, "get_action_definitions", MOCK_EMPTY)
    def test_get_all_empty(self):
        resp = self.app.get('/v2/actions')

        self.assertEqual(200, resp.status_int)

        self.assertEqual(0, len(resp.json['actions']))

    @mock.patch.object(
        db_api, "get_action_definitions", MOCK_ACTIONS)
    def test_get_all_pagination(self):
        resp = self.app.get(
            '/v2/actions?limit=1&sort_keys=id,name')

        self.assertEqual(200, resp.status_int)
        self.assertIn('next', resp.json)
        self.assertEqual(1, len(resp.json['actions']))
        self.assertDictEqual(ACTION, resp.json['actions'][0])

        param_dict = utils.get_dict_from_string(
            resp.json['next'].split('?')[1],
            delimiter='&'
        )

        expected_dict = {
            'marker': '123e4567-e89b-12d3-a456-426655440000',
            'limit': 1,
            'sort_keys': 'id,name',
            'sort_dirs': 'asc,asc'
        }

        self.assertTrue(
            set(expected_dict.items()).issubset(set(param_dict.items()))
        )

    def test_get_all_pagination_limit_negative(self):
        resp = self.app.get(
            '/v2/actions?limit=-1&sort_keys=id,name&sort_dirs=asc,asc',
            expect_errors=True
        )

        self.assertEqual(400, resp.status_int)

        self.assertIn("Limit must be positive", resp.body.decode())

    def test_get_all_pagination_limit_not_integer(self):
        resp = self.app.get(
            '/v2/actions?limit=1.1&sort_keys=id,name&sort_dirs=asc,asc',
            expect_errors=True
        )

        self.assertEqual(400, resp.status_int)

        self.assertIn("unable to convert to int", resp.body.decode())

    def test_get_all_pagination_invalid_sort_dirs_length(self):
        resp = self.app.get(
            '/v2/actions?limit=1&sort_keys=id,name&sort_dirs=asc,asc,asc',
            expect_errors=True
        )

        self.assertEqual(400, resp.status_int)

        self.assertIn(
            "Length of sort_keys must be equal or greater than sort_dirs",
            resp.body.decode()
        )

    def test_get_all_pagination_unknown_direction(self):
        resp = self.app.get(
            '/v2/actions?limit=1&sort_keys=id&sort_dirs=nonexist',
            expect_errors=True
        )

        self.assertEqual(400, resp.status_int)

        self.assertIn("Unknown sort direction", resp.body.decode())

    def test_validate(self):
        resp = self.app.post(
            '/v2/actions/validate',
            ACTION_DEFINITION,
            headers={'Content-Type': 'text/plain'}
        )

        self.assertEqual(200, resp.status_int)
        self.assertTrue(resp.json['valid'])

    def test_validate_invalid_model_exception(self):
        resp = self.app.post(
            '/v2/actions/validate',
            ACTION_DEFINITION_INVALID_NO_BASE,
            headers={'Content-Type': 'text/plain'},
            expect_errors=True
        )

        self.assertEqual(200, resp.status_int)
        self.assertFalse(resp.json['valid'])
        self.assertIn("Invalid DSL", resp.json['error'])

    def test_validate_dsl_parse_exception(self):
        resp = self.app.post(
            '/v2/actions/validate',
            ACTION_DSL_PARSE_EXCEPTION,
            headers={'Content-Type': 'text/plain'},
            expect_errors=True
        )

        self.assertEqual(200, resp.status_int)
        self.assertFalse(resp.json['valid'])
        self.assertIn("Definition could not be parsed", resp.json['error'])

    def test_validate_yaql_parse_exception(self):
        resp = self.app.post(
            '/v2/actions/validate',
            ACTION_DEFINITION_INVALID_YAQL,
            headers={'Content-Type': 'text/plain'},
            expect_errors=True
        )

        self.assertEqual(200, resp.status_int)
        self.assertFalse(resp.json['valid'])
        self.assertIn("unexpected end of statement",
                      resp.json['error'])

    def test_validate_empty(self):
        resp = self.app.post(
            '/v2/actions/validate',
            '',
            headers={'Content-Type': 'text/plain'},
            expect_errors=True
        )

        self.assertEqual(200, resp.status_int)
        self.assertFalse(resp.json['valid'])
        self.assertIn("Invalid DSL", resp.json['error'])
