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
from mistral.tests.api import base

WORKFLOW_DB = models.Workflow(id='123',
                              name='flow',
                              definition='---',
                              tags=['deployment', 'demo'],
                              scope="public",
                              created_at=datetime.datetime(1970, 1, 1),
                              updated_at=datetime.datetime(1970, 1, 1))

WORKFLOW = {
    'id': '123',
    'name': 'flow',
    'definition': '---',
    'tags': ['deployment', 'demo'],
    'scope': 'public',
    'created_at': '1970-01-01 00:00:00',
    'updated_at': '1970-01-01 00:00:00'
}

UPDATED_WORKFLOW_DB = copy.copy(WORKFLOW_DB)
UPDATED_WORKFLOW_DB['definition'] = '---\nVersion: 2.0'
UPDATED_WORKFLOW = copy.copy(WORKFLOW)
UPDATED_WORKFLOW['definition'] = '---\nVersion: 2.0'

MOCK_WORKFLOW = mock.MagicMock(return_value=WORKFLOW_DB)
MOCK_WORKFLOWS = mock.MagicMock(return_value=[WORKFLOW_DB])
MOCK_UPDATED_WORKFLOW = mock.MagicMock(return_value=UPDATED_WORKFLOW_DB)
MOCK_DELETE = mock.MagicMock(return_value=None)
MOCK_EMPTY = mock.MagicMock(return_value=[])
MOCK_NOT_FOUND = mock.MagicMock(side_effect=exc.NotFoundException())
MOCK_DUPLICATE = mock.MagicMock(side_effect=exc.DBDuplicateEntry())


class TestWorkflowsController(base.FunctionalTest):
    @mock.patch.object(db_api, "get_workflow", MOCK_WORKFLOW)
    def test_get(self):
        resp = self.app.get('/v2/workflows/123')

        self.assertEqual(resp.status_int, 200)
        self.assertDictEqual(WORKFLOW, resp.json)

    @mock.patch.object(db_api, "get_workflow", MOCK_NOT_FOUND)
    def test_get_not_found(self):
        resp = self.app.get('/v2/workflows/123', expect_errors=True)

        self.assertEqual(resp.status_int, 404)

    @mock.patch.object(db_api, "update_workflow", MOCK_UPDATED_WORKFLOW)
    def test_put(self):
        resp = self.app.put_json('/v2/workflows/123', UPDATED_WORKFLOW)

        self.assertEqual(resp.status_int, 200)
        self.assertDictEqual(UPDATED_WORKFLOW, resp.json)

    @mock.patch.object(db_api, "update_workflow", MOCK_NOT_FOUND)
    def test_put_not_found(self):
        resp = self.app.put_json('/v2/workflows/123', UPDATED_WORKFLOW,
                                 expect_errors=True)

        self.assertEqual(resp.status_int, 404)

    @mock.patch.object(db_api, "create_workflow", MOCK_WORKFLOW)
    def test_post(self):
        resp = self.app.post_json('/v2/workflows', WORKFLOW)

        self.assertEqual(resp.status_int, 201)
        self.assertDictEqual(WORKFLOW, resp.json)

    @mock.patch.object(db_api, "create_workflow", MOCK_DUPLICATE)
    def test_post_dup(self):
        resp = self.app.post_json('/v2/workflows', WORKFLOW,
                                  expect_errors=True)

        self.assertEqual(resp.status_int, 409)

    @mock.patch.object(db_api, "delete_workflow", MOCK_DELETE)
    def test_delete(self):
        resp = self.app.delete('/v2/workflows/123')

        self.assertEqual(resp.status_int, 204)

    @mock.patch.object(db_api, "delete_workflow", MOCK_NOT_FOUND)
    def test_delete_not_found(self):
        resp = self.app.delete('/v2/workflows/123', expect_errors=True)

        self.assertEqual(resp.status_int, 404)

    @mock.patch.object(db_api, "get_workflows", MOCK_WORKFLOWS)
    def test_get_all(self):
        resp = self.app.get('/v2/workflows')

        self.assertEqual(resp.status_int, 200)

        self.assertEqual(len(resp.json['workflows']), 1)
        self.assertDictEqual(WORKFLOW, resp.json['workflows'][0])

    @mock.patch.object(db_api, "get_workflows", MOCK_EMPTY)
    def test_get_all_empty(self):
        resp = self.app.get('/v2/workflows')

        self.assertEqual(resp.status_int, 200)

        self.assertEqual(len(resp.json['workflows']), 0)
