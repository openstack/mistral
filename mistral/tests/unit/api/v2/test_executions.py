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
from webtest import app as webtest_app

from mistral.api.controllers.v2 import execution
from mistral.db.v2 import api as db_api
from mistral.db.v2.sqlalchemy import models
from mistral.engine import rpc
from mistral import exceptions as exc
from mistral.tests.unit.api import base
from mistral.workflow import states

WF_EX = models.WorkflowExecution(
    id='123',
    workflow_name='some',
    spec={'name': 'some'},
    state=states.RUNNING,
    state_info=None,
    input={'foo': 'bar'},
    output={},
    params={'env': {'k1': 'abc'}},
    created_at=datetime.datetime(1970, 1, 1),
    updated_at=datetime.datetime(1970, 1, 1)
)

WF_EX_JSON = {
    'id': '123',
    'input': '{"foo": "bar"}',
    'output': '{}',
    'params': '{"env": {"k1": "abc"}}',
    'state': 'RUNNING',
    'state_info': None,
    'created_at': '1970-01-01 00:00:00',
    'updated_at': '1970-01-01 00:00:00',
    'workflow_name': 'some'
}

UPDATED_WF_EX = copy.copy(WF_EX)
UPDATED_WF_EX['state'] = states.PAUSED

UPDATED_WF_EX_JSON = copy.copy(WF_EX_JSON)
UPDATED_WF_EX_JSON['state'] = states.PAUSED

MOCK_WF_EX = mock.MagicMock(return_value=WF_EX)
MOCK_WF_EXECUTIONS = mock.MagicMock(return_value=[WF_EX])
MOCK_UPDATED_WF_EX = mock.MagicMock(return_value=UPDATED_WF_EX)
MOCK_DELETE = mock.MagicMock(return_value=None)
MOCK_EMPTY = mock.MagicMock(return_value=[])
MOCK_NOT_FOUND = mock.MagicMock(side_effect=exc.NotFoundException())
MOCK_ACTION_EXC = mock.MagicMock(side_effect=exc.ActionException())


class TestExecutionsController(base.FunctionalTest):
    @mock.patch.object(db_api, 'get_workflow_execution', MOCK_WF_EX)
    def test_get(self):
        resp = self.app.get('/v2/executions/123')

        self.maxDiff = None

        self.assertEqual(resp.status_int, 200)
        self.assertDictEqual(WF_EX_JSON, resp.json)

    @mock.patch.object(db_api, 'get_workflow_execution', MOCK_NOT_FOUND)
    def test_get_not_found(self):
        resp = self.app.get('/v2/executions/123', expect_errors=True)

        self.assertEqual(resp.status_int, 404)

    @mock.patch.object(
        db_api,
        'ensure_workflow_execution_exists',
        MOCK_WF_EX
    )
    @mock.patch.object(rpc.EngineClient, 'pause_workflow',
                       MOCK_UPDATED_WF_EX)
    def test_put(self):
        resp = self.app.put_json('/v2/executions/123', UPDATED_WF_EX_JSON)

        self.assertEqual(resp.status_int, 200)
        self.assertDictEqual(UPDATED_WF_EX_JSON, resp.json)

    @mock.patch.object(
        db_api,
        'ensure_workflow_execution_exists',
        MOCK_WF_EX
    )
    def test_put_stop(self):
        update_exec = copy.copy(WF_EX_JSON)
        update_exec['state'] = states.ERROR
        update_exec['state_info'] = "Force"

        with mock.patch.object(rpc.EngineClient, 'stop_workflow') as mock_pw:
            wf_ex = copy.copy(WF_EX)
            wf_ex['state'] = states.ERROR
            wf_ex['state_info'] = "Force"
            mock_pw.return_value = wf_ex

            resp = self.app.put_json('/v2/executions/123', update_exec)

            self.assertEqual(resp.status_int, 200)
            self.assertDictEqual(update_exec, resp.json)
            mock_pw.assert_called_once_with('123', 'ERROR', "Force")

    @mock.patch.object(db_api, 'update_workflow_execution', MOCK_NOT_FOUND)
    def test_put_not_found(self):
        resp = self.app.put_json(
            '/v2/executions/123',
            dict(state=states.PAUSED),
            expect_errors=True
        )

        self.assertEqual(resp.status_int, 404)

    @mock.patch.object(rpc.EngineClient, 'start_workflow')
    def test_post(self, f):
        f.return_value = WF_EX.to_dict()

        resp = self.app.post_json('/v2/executions', WF_EX_JSON)

        self.assertEqual(resp.status_int, 201)
        self.assertDictEqual(WF_EX_JSON, resp.json)

        exec_dict = execution.Execution(**WF_EX_JSON).to_dict()

        f.assert_called_once_with(
            exec_dict['workflow_name'],
            exec_dict['input'],
            **exec_dict['params']
        )

    @mock.patch.object(rpc.EngineClient, 'start_workflow', MOCK_ACTION_EXC)
    def test_post_throws_exception(self):
        context = self.assertRaises(webtest_app.AppError, self.app.post_json,
                                    '/v2/executions',
                                    WF_EX_JSON)
        self.assertIn('Bad response: 400', context.message)

    @mock.patch.object(db_api, 'delete_workflow_execution', MOCK_DELETE)
    def test_delete(self):
        resp = self.app.delete('/v2/executions/123')

        self.assertEqual(resp.status_int, 204)

    @mock.patch.object(db_api, 'delete_workflow_execution', MOCK_NOT_FOUND)
    def test_delete_not_found(self):
        resp = self.app.delete('/v2/executions/123', expect_errors=True)

        self.assertEqual(resp.status_int, 404)

    @mock.patch.object(db_api, 'get_workflow_executions', MOCK_WF_EXECUTIONS)
    def test_get_all(self):
        resp = self.app.get('/v2/executions')

        self.assertEqual(resp.status_int, 200)

        self.assertEqual(len(resp.json['executions']), 1)
        self.assertDictEqual(WF_EX_JSON, resp.json['executions'][0])

    @mock.patch.object(db_api, 'get_workflow_executions', MOCK_EMPTY)
    def test_get_all_empty(self):
        resp = self.app.get('/v2/executions')

        self.assertEqual(resp.status_int, 200)

        self.assertEqual(len(resp.json['executions']), 0)
