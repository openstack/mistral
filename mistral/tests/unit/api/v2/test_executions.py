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
from webtest import app as webtest_app

from mistral.api.controllers.v2 import execution
from mistral.db.v2 import api as db_api
from mistral.db.v2.sqlalchemy import models
from mistral.engine1 import rpc
from mistral import exceptions as exc
from mistral.tests.unit.api import base
from mistral.workflow import states

EXEC_DB = models.Execution(
    id='123',
    wf_name='some',
    wf_spec={'name': 'some'},
    state=states.RUNNING,
    input={'foo': 'bar'},
    output={},
    created_at=datetime.datetime(1970, 1, 1),
    updated_at=datetime.datetime(1970, 1, 1)
)

EXEC = {
    'id': '123',
    'input': '{"foo": "bar"}',
    'output': '{}',
    'state': 'RUNNING',
    'created_at': '1970-01-01 00:00:00',
    'updated_at': '1970-01-01 00:00:00',
    'workflow_name': 'some'
}

UPDATED_EXEC_DB = copy.copy(EXEC_DB)
UPDATED_EXEC_DB['state'] = 'STOPPED'

UPDATED_EXEC = copy.copy(EXEC)
UPDATED_EXEC['state'] = 'STOPPED'

MOCK_EXECUTION = mock.MagicMock(return_value=EXEC_DB)
MOCK_EXECUTIONS = mock.MagicMock(return_value=[EXEC_DB])
MOCK_UPDATED_EXECUTION = mock.MagicMock(return_value=UPDATED_EXEC_DB)
MOCK_DELETE = mock.MagicMock(return_value=None)
MOCK_EMPTY = mock.MagicMock(return_value=[])
MOCK_NOT_FOUND = mock.MagicMock(side_effect=exc.NotFoundException())
MOCK_ACTION_EXC = mock.MagicMock(side_effect=exc.ActionException())


class TestExecutionsController(base.FunctionalTest):
    @mock.patch.object(db_api, 'get_execution', MOCK_EXECUTION)
    def test_get(self):
        resp = self.app.get('/v2/executions/123')

        self.assertEqual(resp.status_int, 200)
        self.assertDictEqual(EXEC, resp.json)

    @mock.patch.object(db_api, 'get_execution', MOCK_NOT_FOUND)
    def test_get_not_found(self):
        resp = self.app.get('/v2/executions/123', expect_errors=True)

        self.assertEqual(resp.status_int, 404)

    @mock.patch.object(db_api, 'update_execution', MOCK_UPDATED_EXECUTION)
    def test_put(self):
        resp = self.app.put_json('/v2/executions/123', UPDATED_EXEC)

        self.assertEqual(resp.status_int, 200)
        self.assertDictEqual(UPDATED_EXEC, resp.json)

    @mock.patch.object(db_api, 'update_execution', MOCK_NOT_FOUND)
    def test_put_not_found(self):
        resp = self.app.put_json('/v2/executions/123', dict(state='STOPPED'),
                                 expect_errors=True)

        self.assertEqual(resp.status_int, 404)

    @mock.patch.object(rpc.EngineClient, 'start_workflow')
    def test_post(self, f):
        f.return_value = EXEC_DB.to_dict()

        resp = self.app.post_json('/v2/executions', EXEC)

        self.assertEqual(resp.status_int, 201)
        self.assertDictEqual(EXEC, resp.json)

        exec_dict = execution.Execution(**EXEC).to_dict()

        f.assert_called_once_with(
            exec_dict['workflow_name'],
            exec_dict['input']
        )

    @mock.patch.object(rpc.EngineClient, 'start_workflow', MOCK_ACTION_EXC)
    def test_post_throws_exception(self):
        context = self.assertRaises(webtest_app.AppError, self.app.post_json,
                                    '/v2/executions',
                                    EXEC)
        self.assertIn('Bad response: 400', context.message)

    @mock.patch.object(db_api, 'delete_execution', MOCK_DELETE)
    def test_delete(self):
        resp = self.app.delete('/v2/executions/123')

        self.assertEqual(resp.status_int, 204)

    @mock.patch.object(db_api, 'delete_execution', MOCK_NOT_FOUND)
    def test_delete_not_found(self):
        resp = self.app.delete('/v2/executions/123', expect_errors=True)

        self.assertEqual(resp.status_int, 404)

    @mock.patch.object(db_api, 'get_executions', MOCK_EXECUTIONS)
    def test_get_all(self):
        resp = self.app.get('/v2/executions')

        self.assertEqual(resp.status_int, 200)

        self.assertEqual(len(resp.json['executions']), 1)
        self.assertDictEqual(EXEC, resp.json['executions'][0])

    @mock.patch.object(db_api, 'get_executions', MOCK_EMPTY)
    def test_get_all_empty(self):
        resp = self.app.get('/v2/executions')

        self.assertEqual(resp.status_int, 200)

        self.assertEqual(len(resp.json['executions']), 0)
