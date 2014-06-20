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

import json
import mock
from webtest import app as webtest_app

from mistral.db import api as db_api
from mistral import engine
from mistral import exceptions as ex
from mistral.tests.api import base

# TODO(everyone): later we need additional tests verifying all the errors etc.


EXECS = [
    {
        'id': '123',
        'workbook_name': 'my_workbook',
        'task': 'my_task',
        'state': 'RUNNING',
        'context': {
            "person": {
                "first_name": "John",
                "last_name": "Doe"
            }
        }
    }
]


WORKBOOKS = [
    {
        'name': "my_workbook",
        'description': "My cool Mistral workbook",
        'tags': ['deployment', 'demo']
    }
]


UPDATED_EXEC = EXECS[0].copy()
UPDATED_EXEC['state'] = 'STOPPED'


def canonize(json_dict):
    if json_dict.get('context'):
        json_dict['context'] = json.loads(json_dict['context'])

    return json_dict


class TestExecutionsController(base.FunctionalTest):
    @mock.patch.object(db_api, 'execution_get',
                       mock.MagicMock(return_value=EXECS[0]))
    def test_workbook_get(self):
        resp = self.app.get('/v1/workbooks/my_workbook/executions/123')

        self.assertEqual(resp.status_int, 200)
        self.assertDictEqual(EXECS[0], canonize(resp.json))

    @mock.patch.object(db_api, 'execution_get',
                       mock.MagicMock(return_value=EXECS[0]))
    def test_root_get(self):
        resp = self.app.get('/v1/executions/123')

        self.assertEqual(resp.status_int, 200)
        self.assertDictEqual(EXECS[0], canonize(resp.json))

    @mock.patch.object(db_api, 'execution_get',
                       mock.MagicMock(side_effect=ex.NotFoundException()))
    def test_get_empty(self):
        resp = self.app.get('/v1/workbooks/my_workbook/executions/123',
                            expect_errors=True)
        self.assertEqual(resp.status_int, 404)

    @mock.patch.object(db_api, 'execution_update',
                       mock.MagicMock(return_value=UPDATED_EXEC))
    def test_workbook_put(self):
        resp = self.app.put_json('/v1/workbooks/my_workbook/executions/123',
                                 dict(state='STOPPED'))

        self.assertEqual(resp.status_int, 200)
        self.assertDictEqual(UPDATED_EXEC, canonize(resp.json))

    @mock.patch.object(db_api, 'execution_update',
                       mock.MagicMock(return_value=UPDATED_EXEC))
    def test_root_put(self):
        resp = self.app.put_json('/v1/executions/123',
                                 dict(state='STOPPED'))

        self.assertEqual(resp.status_int, 200)
        self.assertDictEqual(UPDATED_EXEC, canonize(resp.json))

    @mock.patch.object(db_api, 'execution_update',
                       mock.MagicMock(
                           side_effect=ex.NotFoundException()))
    def test_put_not_found(self):
        resp = self.app.put_json('/v1/workbooks/my_workbook/executions/123',
                                 dict(state='STOPPED'), expect_errors=True)

        self.assertEqual(resp.status_int, 404)

    @mock.patch.object(engine.EngineClient, 'start_workflow_execution',
                       mock.MagicMock(return_value=EXECS[0]))
    @mock.patch.object(db_api, 'workbook_definition_get',
                       mock.Mock(return_value="Workflow:"))
    def test_post(self):
        my_workbook = WORKBOOKS[0]
        self.app.post_json('/v1/workbooks',
                           my_workbook)

        new_exec = EXECS[0].copy()
        new_exec['context'] = json.dumps(new_exec['context'])

        resp = self.app.post_json('/v1/workbooks/my_workbook/executions',
                                  new_exec)
        self.assertEqual(resp.status_int, 201)
        self.assertDictEqual(EXECS[0], canonize(resp.json))

    @mock.patch.object(engine.EngineClient, 'start_workflow_execution',
                       mock.MagicMock(return_value=EXECS[0]))
    def test_post_definition_empty(self):
        my_workbook = WORKBOOKS[0]
        self.app.post_json('/v1/workbooks',
                           my_workbook)

        new_exec = EXECS[0].copy()
        new_exec['context'] = json.dumps(new_exec['context'])

        resp = self.app.post_json('/v1/workbooks/my_workbook/executions',
                                  new_exec, expect_errors=True)
        self.assertEqual(resp.status_int, 404)

    @mock.patch.object(engine.EngineClient, 'start_workflow_execution',
                       mock.MagicMock(side_effect=ex.MistralException))
    def test_post_throws_exception(self):
        context = self.assertRaises(webtest_app.AppError, self.app.post_json,
                                    '/v1/workbooks/my_workbook/executions',
                                    EXECS[0])
        self.assertIn('Bad response: 400', context.message)

    @mock.patch.object(db_api, 'execution_delete',
                       mock.MagicMock(return_value=None))
    def test_workbook_delete(self):
        resp = self.app.delete('/v1/workbooks/my_workbook/executions/123')

        self.assertEqual(resp.status_int, 204)

    @mock.patch.object(db_api, 'execution_delete',
                       mock.MagicMock(return_value=None))
    def test_root_delete(self):
        resp = self.app.delete('/v1/executions/123')

        self.assertEqual(resp.status_int, 204)

    @mock.patch.object(db_api, 'execution_delete',
                       mock.MagicMock(side_effect=ex.NotFoundException))
    def test_delete_not_found(self):
        resp = self.app.delete('/v1/workbooks/my_workbook/executions/123',
                               expect_errors=True)

        self.assertEqual(resp.status_int, 404)

    @mock.patch.object(db_api, 'executions_get',
                       mock.MagicMock(return_value=EXECS))
    @mock.patch.object(db_api, 'workbook_get',
                       mock.MagicMock(return_value={'name': 'my_workbook'}))
    def test_workbook_get_all(self):
        resp = self.app.get('/v1/workbooks/my_workbook/executions')

        self.assertEqual(resp.status_int, 200)

        self.assertEqual(len(resp.json), 1)
        self.assertDictEqual(EXECS[0], canonize(resp.json['executions'][0]))

    @mock.patch.object(db_api, 'executions_get',
                       mock.MagicMock(return_value=EXECS))
    @mock.patch.object(db_api, 'workbook_get',
                       mock.MagicMock(return_value={'name': 'my_workbook'}))
    def test_root_get_all(self):
        resp = self.app.get('/v1/executions')

        self.assertEqual(resp.status_int, 200)

        self.assertEqual(len(resp.json), 1)
        self.assertDictEqual(EXECS[0], canonize(resp.json['executions'][0]))

    @mock.patch.object(db_api, 'executions_get',
                       mock.MagicMock(return_value=EXECS))
    def test_get_all_no_workbook(self):
        resp = self.app.get('/v1/workbooks/my_workbook/executions',
                            expect_errors=True)

        self.assertEqual(resp.status_int, 404)
