# Copyright 2013 - Mirantis, Inc.
# Copyright 2015 - StackStorm, Inc.
# Copyright 2015 Huawei Technologies Co., Ltd.
# Copyright 2016 - Brocade Communications Systems, Inc.
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
import json

import mock
from oslo_config import cfg
import oslo_messaging
import uuid
from webtest import app as webtest_app

from mistral.api.controllers.v2 import execution
from mistral.db.v2 import api as db_api
from mistral.db.v2.sqlalchemy import api as sql_db_api
from mistral.db.v2.sqlalchemy import models
from mistral.engine.rpc_backend import rpc
from mistral import exceptions as exc
from mistral.tests.unit.api import base
from mistral import utils
from mistral.utils import rest_utils
from mistral.workflow import states

# This line is needed for correct initialization of messaging config.
oslo_messaging.get_transport(cfg.CONF)


WF_EX = models.WorkflowExecution(
    id='123e4567-e89b-12d3-a456-426655440000',
    workflow_name='some',
    workflow_id='123e4567-e89b-12d3-a456-426655441111',
    description='execution description.',
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
    'id': '123e4567-e89b-12d3-a456-426655440000',
    'input': '{"foo": "bar"}',
    'output': '{}',
    'params': '{"env": {"k1": "abc"}}',
    'state': 'RUNNING',
    'state_info': None,
    'created_at': '1970-01-01 00:00:00',
    'updated_at': '1970-01-01 00:00:00',
    'workflow_name': 'some',
    'workflow_id': '123e4567-e89b-12d3-a456-426655441111'
}

SUB_WF_EX = models.WorkflowExecution(
    id=str(uuid.uuid4()),
    workflow_name='some',
    workflow_id='123e4567-e89b-12d3-a456-426655441111',
    description='foobar',
    spec={'name': 'some'},
    state=states.RUNNING,
    state_info=None,
    input={'foo': 'bar'},
    output={},
    params={'env': {'k1': 'abc'}},
    created_at=datetime.datetime(1970, 1, 1),
    updated_at=datetime.datetime(1970, 1, 1),
    task_execution_id=str(uuid.uuid4())
)

SUB_WF_EX_JSON = {
    'id': SUB_WF_EX.id,
    'workflow_name': 'some',
    'workflow_id': '123e4567-e89b-12d3-a456-426655441111',
    'input': '{"foo": "bar"}',
    'output': '{}',
    'params': '{"env": {"k1": "abc"}}',
    'state': 'RUNNING',
    'state_info': None,
    'created_at': '1970-01-01 00:00:00',
    'updated_at': '1970-01-01 00:00:00',
    'task_execution_id': SUB_WF_EX.task_execution_id
}

MOCK_SUB_WF_EXECUTIONS = mock.MagicMock(return_value=[SUB_WF_EX])

SUB_WF_EX_JSON_WITH_DESC = copy.deepcopy(SUB_WF_EX_JSON)
SUB_WF_EX_JSON_WITH_DESC['description'] = SUB_WF_EX.description


UPDATED_WF_EX = copy.deepcopy(WF_EX)
UPDATED_WF_EX['state'] = states.PAUSED

UPDATED_WF_EX_JSON = copy.deepcopy(WF_EX_JSON)
UPDATED_WF_EX_JSON['state'] = states.PAUSED

UPDATED_WF_EX_ENV = copy.deepcopy(UPDATED_WF_EX)
UPDATED_WF_EX_ENV['params'] = {'env': {'k1': 'def'}}

UPDATED_WF_EX_ENV_DESC = copy.deepcopy(UPDATED_WF_EX)
UPDATED_WF_EX_ENV_DESC['description'] = 'foobar'
UPDATED_WF_EX_ENV_DESC['params'] = {'env': {'k1': 'def'}}

WF_EX_JSON_WITH_DESC = copy.deepcopy(WF_EX_JSON)
WF_EX_JSON_WITH_DESC['description'] = WF_EX.description

MOCK_WF_EX = mock.MagicMock(return_value=WF_EX)
MOCK_SUB_WF_EX = mock.MagicMock(return_value=SUB_WF_EX)
MOCK_WF_EXECUTIONS = mock.MagicMock(return_value=[WF_EX])
MOCK_UPDATED_WF_EX = mock.MagicMock(return_value=UPDATED_WF_EX)
MOCK_DELETE = mock.MagicMock(return_value=None)
MOCK_EMPTY = mock.MagicMock(return_value=[])
MOCK_NOT_FOUND = mock.MagicMock(side_effect=exc.DBEntityNotFoundError())
MOCK_ACTION_EXC = mock.MagicMock(side_effect=exc.ActionException())


@mock.patch.object(rpc, '_IMPL_CLIENT', mock.Mock())
class TestExecutionsController(base.APITest):
    @mock.patch.object(db_api, 'get_workflow_execution', MOCK_WF_EX)
    def test_get(self):
        resp = self.app.get('/v2/executions/123')

        self.assertEqual(200, resp.status_int)
        self.assertDictEqual(WF_EX_JSON_WITH_DESC, resp.json)

    @mock.patch.object(db_api, 'get_workflow_execution', MOCK_SUB_WF_EX)
    def test_get_sub_wf_ex(self):
        resp = self.app.get('/v2/executions/123')

        self.assertEqual(200, resp.status_int)
        self.assertDictEqual(SUB_WF_EX_JSON_WITH_DESC, resp.json)

    @mock.patch.object(db_api, 'get_workflow_execution', MOCK_NOT_FOUND)
    def test_get_not_found(self):
        resp = self.app.get('/v2/executions/123', expect_errors=True)

        self.assertEqual(404, resp.status_int)

    @mock.patch.object(
        db_api,
        'ensure_workflow_execution_exists',
        mock.MagicMock(return_value=None)
    )
    @mock.patch.object(
        rpc.EngineClient,
        'pause_workflow',
        MOCK_UPDATED_WF_EX
    )
    def test_put_state_paused(self):
        update_exec = {
            'id': WF_EX['id'],
            'state': states.PAUSED
        }

        resp = self.app.put_json('/v2/executions/123', update_exec)

        expected_exec = copy.deepcopy(WF_EX_JSON_WITH_DESC)
        expected_exec['state'] = states.PAUSED

        self.assertEqual(200, resp.status_int)
        self.assertDictEqual(expected_exec, resp.json)

    @mock.patch.object(
        db_api,
        'ensure_workflow_execution_exists',
        mock.MagicMock(return_value=None)
    )
    @mock.patch.object(rpc.EngineClient, 'stop_workflow')
    def test_put_state_error(self, mock_stop_wf):
        update_exec = {
            'id': WF_EX['id'],
            'state': states.ERROR,
            'state_info': 'Force'
        }

        wf_ex = copy.deepcopy(WF_EX)
        wf_ex['state'] = states.ERROR
        wf_ex['state_info'] = 'Force'
        mock_stop_wf.return_value = wf_ex

        resp = self.app.put_json('/v2/executions/123', update_exec)

        expected_exec = copy.deepcopy(WF_EX_JSON_WITH_DESC)
        expected_exec['state'] = states.ERROR
        expected_exec['state_info'] = 'Force'

        self.assertEqual(200, resp.status_int)
        self.assertDictEqual(expected_exec, resp.json)
        mock_stop_wf.assert_called_once_with('123', 'ERROR', 'Force')

    @mock.patch.object(
        db_api,
        'ensure_workflow_execution_exists',
        mock.MagicMock(return_value=None)
    )
    @mock.patch.object(rpc.EngineClient, 'stop_workflow')
    def test_put_state_cancelled(self, mock_stop_wf):
        update_exec = {
            'id': WF_EX['id'],
            'state': states.CANCELLED,
            'state_info': 'Cancelled by user.'
        }

        wf_ex = copy.deepcopy(WF_EX)
        wf_ex['state'] = states.CANCELLED
        wf_ex['state_info'] = 'Cancelled by user.'
        mock_stop_wf.return_value = wf_ex

        resp = self.app.put_json('/v2/executions/123', update_exec)

        expected_exec = copy.deepcopy(WF_EX_JSON_WITH_DESC)
        expected_exec['state'] = states.CANCELLED
        expected_exec['state_info'] = 'Cancelled by user.'

        self.assertEqual(200, resp.status_int)
        self.assertDictEqual(expected_exec, resp.json)

        mock_stop_wf.assert_called_once_with(
            '123',
            'CANCELLED',
            'Cancelled by user.'
        )

    @mock.patch.object(
        db_api,
        'ensure_workflow_execution_exists',
        mock.MagicMock(return_value=None)
    )
    @mock.patch.object(rpc.EngineClient, 'resume_workflow')
    def test_put_state_resume(self, mock_resume_wf):
        update_exec = {
            'id': WF_EX['id'],
            'state': states.RUNNING
        }

        wf_ex = copy.deepcopy(WF_EX)
        wf_ex['state'] = states.RUNNING
        wf_ex['state_info'] = None
        mock_resume_wf.return_value = wf_ex

        resp = self.app.put_json('/v2/executions/123', update_exec)

        expected_exec = copy.deepcopy(WF_EX_JSON_WITH_DESC)
        expected_exec['state'] = states.RUNNING
        expected_exec['state_info'] = None

        self.assertEqual(200, resp.status_int)
        self.assertDictEqual(expected_exec, resp.json)
        mock_resume_wf.assert_called_once_with('123', env=None)

    @mock.patch.object(
        db_api,
        'ensure_workflow_execution_exists',
        mock.MagicMock(return_value=None)
    )
    def test_put_invalid_state(self):
        invalid_states = [states.IDLE, states.WAITING, states.RUNNING_DELAYED]

        for state in invalid_states:
            update_exec = {
                'id': WF_EX['id'],
                'state': state
            }

            resp = self.app.put_json(
                '/v2/executions/123',
                update_exec,
                expect_errors=True
            )

            self.assertEqual(400, resp.status_int)

            self.assertIn(
                'Cannot change state to %s.' % state,
                resp.json['faultstring']
            )

    @mock.patch.object(
        db_api,
        'ensure_workflow_execution_exists',
        mock.MagicMock(return_value=None)
    )
    @mock.patch.object(rpc.EngineClient, 'stop_workflow')
    def test_put_state_info_unset(self, mock_stop_wf):
        update_exec = {
            'id': WF_EX['id'],
            'state': states.ERROR,
        }

        wf_ex = copy.deepcopy(WF_EX)
        wf_ex['state'] = states.ERROR
        del wf_ex.state_info
        mock_stop_wf.return_value = wf_ex

        resp = self.app.put_json('/v2/executions/123', update_exec)

        expected_exec = copy.deepcopy(WF_EX_JSON_WITH_DESC)
        expected_exec['state'] = states.ERROR
        expected_exec['state_info'] = None

        self.assertEqual(200, resp.status_int)
        self.assertDictEqual(expected_exec, resp.json)
        mock_stop_wf.assert_called_once_with('123', 'ERROR', None)

    @mock.patch('mistral.db.v2.api.ensure_workflow_execution_exists')
    @mock.patch(
        'mistral.db.v2.api.update_workflow_execution',
        return_value=WF_EX
    )
    def test_put_description(self, mock_update, mock_ensure):
        update_params = {'description': 'execution description.'}

        resp = self.app.put_json('/v2/executions/123', update_params)

        self.assertEqual(200, resp.status_int)
        mock_ensure.assert_called_once_with('123')
        mock_update.assert_called_once_with('123', update_params)

    @mock.patch.object(
        sql_db_api,
        'get_workflow_execution',
        mock.MagicMock(return_value=copy.deepcopy(UPDATED_WF_EX))
    )
    @mock.patch(
        'mistral.services.workflows.update_workflow_execution_env',
        return_value=copy.deepcopy(UPDATED_WF_EX_ENV)
    )
    def test_put_env(self, mock_update_env):
        update_exec = {'params': '{"env": {"k1": "def"}}'}

        resp = self.app.put_json('/v2/executions/123', update_exec)

        self.assertEqual(200, resp.status_int)
        self.assertEqual(update_exec['params'], resp.json['params'])

        mock_update_env.assert_called_once_with(UPDATED_WF_EX, {'k1': 'def'})

    @mock.patch.object(db_api, 'update_workflow_execution', MOCK_NOT_FOUND)
    def test_put_not_found(self):
        resp = self.app.put_json(
            '/v2/executions/123',
            dict(state=states.PAUSED),
            expect_errors=True
        )

        self.assertEqual(404, resp.status_int)

    @mock.patch.object(
        db_api,
        'ensure_workflow_execution_exists',
        mock.MagicMock(return_value=None)
    )
    def test_put_empty(self):
        resp = self.app.put_json('/v2/executions/123', {}, expect_errors=True)

        self.assertEqual(400, resp.status_int)
        self.assertIn(
            'state, description, or env is not provided for update',
            resp.json['faultstring']
        )

    @mock.patch.object(
        db_api,
        'ensure_workflow_execution_exists',
        mock.MagicMock(return_value=None)
    )
    def test_put_state_and_description(self):
        resp = self.app.put_json(
            '/v2/executions/123',
            {'description': 'foobar', 'state': states.ERROR},
            expect_errors=True
        )

        self.assertEqual(400, resp.status_int)
        self.assertIn(
            'description must be updated separately from state',
            resp.json['faultstring']
        )

    @mock.patch.object(
        db_api,
        'ensure_workflow_execution_exists',
        mock.MagicMock(return_value=None)
    )
    @mock.patch.object(
        sql_db_api,
        'get_workflow_execution',
        mock.MagicMock(return_value=copy.deepcopy(UPDATED_WF_EX))
    )
    @mock.patch(
        'mistral.db.v2.api.update_workflow_execution',
        return_value=WF_EX
    )
    @mock.patch(
        'mistral.services.workflows.update_workflow_execution_env',
        return_value=copy.deepcopy(UPDATED_WF_EX_ENV_DESC)
    )
    def test_put_env_and_description(self, mock_update_env, mock_update):
        update_exec = {
            'description': 'foobar',
            'params': '{"env": {"k1": "def"}}'
        }

        resp = self.app.put_json('/v2/executions/123', update_exec)

        self.assertEqual(200, resp.status_int)
        self.assertEqual(update_exec['description'], resp.json['description'])
        self.assertEqual(update_exec['params'], resp.json['params'])

        mock_update.assert_called_once_with('123', {'description': 'foobar'})
        mock_update_env.assert_called_once_with(UPDATED_WF_EX, {'k1': 'def'})

    @mock.patch.object(
        db_api,
        'ensure_workflow_execution_exists',
        mock.MagicMock(return_value=None)
    )
    def test_put_env_wrong_state(self):
        update_exec = {
            'id': WF_EX['id'],
            'state': states.SUCCESS,
            'params': '{"env": {"k1": "def"}}'
        }

        resp = self.app.put_json(
            '/v2/executions/123',
            update_exec,
            expect_errors=True
        )

        self.assertEqual(400, resp.status_int)

        expected_fault = (
            'env can only be updated when workflow execution '
            'is not running or on resume from pause'
        )

        self.assertIn(expected_fault, resp.json['faultstring'])

    @mock.patch.object(rpc.EngineClient, 'start_workflow')
    def test_post(self, f):
        f.return_value = WF_EX.to_dict()

        resp = self.app.post_json('/v2/executions', WF_EX_JSON_WITH_DESC)

        self.assertEqual(201, resp.status_int)
        self.assertDictEqual(WF_EX_JSON_WITH_DESC, resp.json)

        exec_dict = WF_EX_JSON_WITH_DESC

        f.assert_called_once_with(
            exec_dict['workflow_id'],
            json.loads(exec_dict['input']),
            exec_dict['description'],
            **json.loads(exec_dict['params'])
        )

    @mock.patch.object(rpc.EngineClient, 'start_workflow', MOCK_ACTION_EXC)
    def test_post_throws_exception(self):
        context = self.assertRaises(
            webtest_app.AppError,
            self.app.post_json,
            '/v2/executions',
            WF_EX_JSON
        )

        self.assertIn('Bad response: 400', context.args[0])

    def test_post_without_workflow_id_and_name(self):
        context = self.assertRaises(
            webtest_app.AppError,
            self.app.post_json,
            '/v2/executions',
            {'description': 'some description here.'}
        )

        self.assertIn('Bad response: 400', context.args[0])

    @mock.patch.object(db_api, 'delete_workflow_execution', MOCK_DELETE)
    def test_delete(self):
        resp = self.app.delete('/v2/executions/123')

        self.assertEqual(204, resp.status_int)

    @mock.patch.object(db_api, 'delete_workflow_execution', MOCK_NOT_FOUND)
    def test_delete_not_found(self):
        resp = self.app.delete('/v2/executions/123', expect_errors=True)

        self.assertEqual(404, resp.status_int)

    @mock.patch.object(db_api, 'get_workflow_executions', MOCK_WF_EXECUTIONS)
    def test_get_all(self):
        resp = self.app.get('/v2/executions')

        self.assertEqual(200, resp.status_int)

        self.assertEqual(1, len(resp.json['executions']))
        self.assertDictEqual(WF_EX_JSON_WITH_DESC, resp.json['executions'][0])

    @mock.patch.object(db_api, 'get_workflow_executions', MOCK_EMPTY)
    def test_get_all_empty(self):
        resp = self.app.get('/v2/executions')

        self.assertEqual(200, resp.status_int)

        self.assertEqual(0, len(resp.json['executions']))

    @mock.patch.object(db_api, "get_workflow_executions", MOCK_WF_EXECUTIONS)
    def test_get_all_pagination(self):
        resp = self.app.get(
            '/v2/executions?limit=1&sort_keys=id,workflow_name'
            '&sort_dirs=asc,desc')

        self.assertEqual(200, resp.status_int)
        self.assertIn('next', resp.json)
        self.assertEqual(1, len(resp.json['executions']))
        self.assertDictEqual(WF_EX_JSON_WITH_DESC, resp.json['executions'][0])

        param_dict = utils.get_dict_from_string(
            resp.json['next'].split('?')[1],
            delimiter='&'
        )

        expected_dict = {
            'marker': '123e4567-e89b-12d3-a456-426655440000',
            'limit': 1,
            'sort_keys': 'id,workflow_name',
            'sort_dirs': 'asc,desc'
        }

        self.assertDictEqual(expected_dict, param_dict)

    def test_get_all_pagination_limit_negative(self):
        resp = self.app.get(
            '/v2/executions?limit=-1&sort_keys=id&sort_dirs=asc',
            expect_errors=True
        )

        self.assertEqual(400, resp.status_int)

        self.assertIn("Limit must be positive", resp.body.decode())

    def test_get_all_pagination_limit_not_integer(self):
        resp = self.app.get(
            '/v2/executions?limit=1.1&sort_keys=id&sort_dirs=asc',
            expect_errors=True
        )

        self.assertEqual(400, resp.status_int)

        self.assertIn("unable to convert to int", resp.body.decode())

    def test_get_all_pagination_invalid_sort_dirs_length(self):
        resp = self.app.get(
            '/v2/executions?limit=1&sort_keys=id&sort_dirs=asc,asc',
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

    @mock.patch.object(
        db_api,
        'get_workflow_executions',
        MOCK_SUB_WF_EXECUTIONS
    )
    def test_get_task_workflow_executions(self):
        resp = self.app.get(
            '/v2/tasks/%s/workflow_executions' % SUB_WF_EX.task_execution_id
        )

        self.assertEqual(200, resp.status_int)

        self.assertEqual(1, len(resp.json['executions']))
        self.assertDictEqual(
            SUB_WF_EX_JSON_WITH_DESC,
            resp.json['executions'][0]
        )

    @mock.patch.object(db_api, 'get_workflow_executions', MOCK_WF_EXECUTIONS)
    @mock.patch.object(rest_utils, 'get_all')
    def test_get_all_executions_with_output(self, mock_get_all):
        resp = self.app.get('/v2/executions?include_output=true')

        self.assertEqual(200, resp.status_int)

        args, kwargs = mock_get_all.call_args
        resource_function = kwargs['resource_function']

        self.assertEqual(execution._get_execution_resource, resource_function)

    @mock.patch.object(db_api, 'get_workflow_executions', MOCK_WF_EXECUTIONS)
    @mock.patch.object(rest_utils, 'get_all')
    def test_get_all_executions_without_output(self, mock_get_all):
        resp = self.app.get('/v2/executions')

        self.assertEqual(200, resp.status_int)

        args, kwargs = mock_get_all.call_args
        resource_function = kwargs['resource_function']

        self.assertEqual(None, resource_function)
