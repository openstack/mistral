# -*- coding: utf-8 -*-
#
# Copyright 2013 - Mirantis, Inc.
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

WORKBOOK_DEF = '---'

UPDATED_WORKBOOK_DEF = '---\nVersion: 2.0'

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
UPDATED_WORKBOOK = copy.copy(WORKBOOK)
UPDATED_WORKBOOK['definition'] = UPDATED_WORKBOOK_DEF

MOCK_WORKBOOK = mock.MagicMock(return_value=WORKBOOK_DB)
MOCK_WORKBOOKS = mock.MagicMock(return_value=[WORKBOOK_DB])
MOCK_UPDATED_WORKBOOK = mock.MagicMock(return_value=UPDATED_WORKBOOK_DB)
MOCK_DELETE = mock.MagicMock(return_value=None)
MOCK_EMPTY = mock.MagicMock(return_value=[])
MOCK_NOT_FOUND = mock.MagicMock(side_effect=exc.NotFoundException())
MOCK_DUPLICATE = mock.MagicMock(side_effect=exc.DBDuplicateEntry())


class TestWorkbooksController(base.FunctionalTest):
    @mock.patch.object(db_api, "get_workbook", MOCK_WORKBOOK)
    def test_get(self):
        resp = self.app.get('/v2/workbooks/123')

        self.assertEqual(resp.status_int, 200)
        self.assertDictEqual(WORKBOOK, resp.json)

    @mock.patch.object(db_api, "get_workbook", MOCK_NOT_FOUND)
    def test_get_not_found(self):
        resp = self.app.get('/v2/workbooks/123', expect_errors=True)

        self.assertEqual(resp.status_int, 404)

    @mock.patch.object(workbooks, "update_workbook_v2", MOCK_UPDATED_WORKBOOK)
    def test_put(self):
        resp = self.app.put(
            '/v2/workbooks',
            UPDATED_WORKBOOK_DEF,
            headers={'Content-Type': 'text/plain'}
        )

        self.assertEqual(resp.status_int, 200)
        self.assertEqual(UPDATED_WORKBOOK, resp.json)

    @mock.patch.object(workbooks, "update_workbook_v2", MOCK_NOT_FOUND)
    def test_put_not_found(self):
        resp = self.app.put_json(
            '/v2/workbooks',
            UPDATED_WORKBOOK_DEF,
            headers={'Content-Type': 'text/plain'},
            expect_errors=True
        )

        self.assertEqual(resp.status_int, 404)

    @mock.patch.object(workbooks, "create_workbook_v2", MOCK_WORKBOOK)
    def test_post(self):
        resp = self.app.post(
            '/v2/workbooks',
            WORKBOOK_DEF,
            headers={'Content-Type': 'text/plain'}
        )

        self.assertEqual(resp.status_int, 201)
        self.assertEqual(WORKBOOK, resp.json)

    @mock.patch.object(workbooks, "create_workbook_v2", MOCK_DUPLICATE)
    def test_post_dup(self):
        resp = self.app.post(
            '/v2/workbooks',
            WORKBOOK_DEF,
            headers={'Content-Type': 'text/plain'},
            expect_errors=True
        )

        self.assertEqual(resp.status_int, 409)

    @mock.patch.object(db_api, "delete_workbook", MOCK_DELETE)
    def test_delete(self):
        resp = self.app.delete('/v2/workbooks/123')

        self.assertEqual(resp.status_int, 204)

    @mock.patch.object(db_api, "delete_workbook", MOCK_NOT_FOUND)
    def test_delete_not_found(self):
        resp = self.app.delete('/v2/workbooks/123', expect_errors=True)

        self.assertEqual(resp.status_int, 404)

    @mock.patch.object(db_api, "get_workbooks", MOCK_WORKBOOKS)
    def test_get_all(self):
        resp = self.app.get('/v2/workbooks')

        self.assertEqual(resp.status_int, 200)

        self.assertEqual(len(resp.json['workbooks']), 1)
        self.assertDictEqual(WORKBOOK, resp.json['workbooks'][0])

    @mock.patch.object(db_api, "get_workbooks", MOCK_EMPTY)
    def test_get_all_empty(self):
        resp = self.app.get('/v2/workbooks')

        self.assertEqual(resp.status_int, 200)

        self.assertEqual(len(resp.json['workbooks']), 0)
