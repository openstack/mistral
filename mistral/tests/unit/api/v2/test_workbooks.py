# Copyright 2013 - Mirantis, Inc.
# Copyright 2015 - StackStorm, Inc.
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
import datetime
import mock

from mistral.db.v2 import api as db_api
from mistral.db.v2.sqlalchemy import models
from mistral import exceptions as exc
from mistral.services import workbooks
from mistral.tests.unit.api import base

WORKBOOK_DEF = """
---
version: 2.0
name: 'test'
"""

UPDATED_WORKBOOK_DEF = """
---
version: 2.0
name: 'book'
"""

WORKBOOK_DB = models.Workbook(
    id='123',
    name='book',
    definition=WORKBOOK_DEF,
    tags=['deployment', 'demo'],
    scope="public",
    created_at=datetime.datetime(1970, 1, 1),
    updated_at=datetime.datetime(1970, 1, 1)
)

WORKBOOK = {
    'id': '123',
    'name': 'book',
    'definition': WORKBOOK_DEF,
    'tags': ['deployment', 'demo'],
    'scope': 'public',
    'created_at': '1970-01-01 00:00:00',
    'updated_at': '1970-01-01 00:00:00'
}

UPDATED_WORKBOOK_DB = copy.copy(WORKBOOK_DB)
UPDATED_WORKBOOK_DB['definition'] = UPDATED_WORKBOOK_DEF
UPDATED_WORKBOOK = copy.deepcopy(WORKBOOK)
UPDATED_WORKBOOK['definition'] = UPDATED_WORKBOOK_DEF

WB_DEF_INVALID_MODEL_EXCEPTION = """
---
version: '2.0'
name: 'book'

workflows:
  flow:
    type: direct
    tasks:
      task1:
        action: std.echo output="Hi"
        workflow: wf1
"""

WB_DEF_DSL_PARSE_EXCEPTION = """
---
%
"""

WB_DEF_YAQL_PARSE_EXCEPTION = """
---
version: '2.0'
name: 'book'

workflows:
  flow:
    type: direct
    tasks:
      task1:
        action: std.echo output=<% * %>
"""

MOCK_WORKBOOK = mock.MagicMock(return_value=WORKBOOK_DB)
MOCK_WORKBOOKS = mock.MagicMock(return_value=[WORKBOOK_DB])
MOCK_UPDATED_WORKBOOK = mock.MagicMock(return_value=UPDATED_WORKBOOK_DB)
MOCK_DELETE = mock.MagicMock(return_value=None)
MOCK_EMPTY = mock.MagicMock(return_value=[])
MOCK_NOT_FOUND = mock.MagicMock(side_effect=exc.DBEntityNotFoundError())
MOCK_DUPLICATE = mock.MagicMock(side_effect=exc.DBDuplicateEntryError())


class TestWorkbooksController(base.APITest):
    @mock.patch.object(db_api, "get_workbook", MOCK_WORKBOOK)
    def test_get(self):
        resp = self.app.get('/v2/workbooks/123')

        self.assertEqual(200, resp.status_int)
        self.assertDictEqual(WORKBOOK, resp.json)

    @mock.patch.object(db_api, "get_workbook", MOCK_NOT_FOUND)
    def test_get_not_found(self):
        resp = self.app.get('/v2/workbooks/123', expect_errors=True)

        self.assertEqual(404, resp.status_int)

    @mock.patch.object(workbooks, "update_workbook_v2", MOCK_UPDATED_WORKBOOK)
    def test_put(self):
        resp = self.app.put(
            '/v2/workbooks',
            UPDATED_WORKBOOK_DEF,
            headers={'Content-Type': 'text/plain'}
        )

        self.assertEqual(200, resp.status_int)
        self.assertEqual(UPDATED_WORKBOOK, resp.json)

    @mock.patch.object(workbooks, "update_workbook_v2", MOCK_NOT_FOUND)
    def test_put_not_found(self):
        resp = self.app.put_json(
            '/v2/workbooks',
            UPDATED_WORKBOOK_DEF,
            headers={'Content-Type': 'text/plain'},
            expect_errors=True
        )

        self.assertEqual(404, resp.status_int)

    def test_put_invalid(self):
        resp = self.app.put(
            '/v2/workbooks',
            WB_DEF_INVALID_MODEL_EXCEPTION,
            headers={'Content-Type': 'text/plain'},
            expect_errors=True
        )

        self.assertEqual(400, resp.status_int)
        self.assertIn("Invalid DSL", resp.body.decode())

    @mock.patch.object(workbooks, "create_workbook_v2", MOCK_WORKBOOK)
    def test_post(self):
        resp = self.app.post(
            '/v2/workbooks',
            WORKBOOK_DEF,
            headers={'Content-Type': 'text/plain'}
        )

        self.assertEqual(201, resp.status_int)
        self.assertEqual(WORKBOOK, resp.json)

    @mock.patch.object(workbooks, "create_workbook_v2", MOCK_DUPLICATE)
    def test_post_dup(self):
        resp = self.app.post(
            '/v2/workbooks',
            WORKBOOK_DEF,
            headers={'Content-Type': 'text/plain'},
            expect_errors=True
        )

        self.assertEqual(409, resp.status_int)

    def test_post_invalid(self):
        resp = self.app.post(
            '/v2/workbooks',
            WB_DEF_INVALID_MODEL_EXCEPTION,
            headers={'Content-Type': 'text/plain'},
            expect_errors=True
        )

        self.assertEqual(400, resp.status_int)
        self.assertIn("Invalid DSL", resp.body.decode())

    @mock.patch.object(db_api, "delete_workbook", MOCK_DELETE)
    def test_delete(self):
        resp = self.app.delete('/v2/workbooks/123')

        self.assertEqual(204, resp.status_int)

    @mock.patch.object(db_api, "delete_workbook", MOCK_NOT_FOUND)
    def test_delete_not_found(self):
        resp = self.app.delete('/v2/workbooks/123', expect_errors=True)

        self.assertEqual(404, resp.status_int)

    @mock.patch.object(db_api, "get_workbooks", MOCK_WORKBOOKS)
    def test_get_all(self):
        resp = self.app.get('/v2/workbooks')

        self.assertEqual(200, resp.status_int)

        self.assertEqual(1, len(resp.json['workbooks']))
        self.assertDictEqual(WORKBOOK, resp.json['workbooks'][0])

    @mock.patch.object(db_api, "get_workbooks", MOCK_EMPTY)
    def test_get_all_empty(self):
        resp = self.app.get('/v2/workbooks')

        self.assertEqual(200, resp.status_int)

        self.assertEqual(0, len(resp.json['workbooks']))

    def test_validate(self):
        resp = self.app.post(
            '/v2/workbooks/validate',
            WORKBOOK_DEF,
            headers={'Content-Type': 'text/plain'}
        )

        self.assertEqual(200, resp.status_int)
        self.assertTrue(resp.json['valid'])

    def test_validate_invalid_model_exception(self):
        resp = self.app.post(
            '/v2/workbooks/validate',
            WB_DEF_INVALID_MODEL_EXCEPTION,
            headers={'Content-Type': 'text/plain'},
            expect_errors=True
        )

        self.assertEqual(200, resp.status_int)
        self.assertFalse(resp.json['valid'])
        self.assertIn("Invalid DSL", resp.json['error'])

    def test_validate_dsl_parse_exception(self):
        resp = self.app.post(
            '/v2/workbooks/validate',
            WB_DEF_DSL_PARSE_EXCEPTION,
            headers={'Content-Type': 'text/plain'},
            expect_errors=True
        )

        self.assertEqual(200, resp.status_int)
        self.assertFalse(resp.json['valid'])
        self.assertIn("Definition could not be parsed", resp.json['error'])

    def test_validate_yaql_parse_exception(self):
        resp = self.app.post(
            '/v2/workbooks/validate',
            WB_DEF_YAQL_PARSE_EXCEPTION,
            headers={'Content-Type': 'text/plain'},
            expect_errors=True
        )

        self.assertEqual(200, resp.status_int)
        self.assertFalse(resp.json['valid'])
        self.assertIn("unexpected '*' at position 1",
                      resp.json['error'])

    def test_validate_empty(self):
        resp = self.app.post(
            '/v2/workbooks/validate',
            '',
            headers={'Content-Type': 'text/plain'},
            expect_errors=True
        )

        self.assertEqual(200, resp.status_int)
        self.assertFalse(resp.json['valid'])
        self.assertIn("Invalid DSL", resp.json['error'])
