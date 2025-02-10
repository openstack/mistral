# Copyright 2015 - Mirantis, Inc.
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
from unittest import mock

from oslo_config import cfg
import oslo_messaging
from oslo_messaging import exceptions as oslo_exc
import sqlalchemy as sa

from mistral.api.controllers.v2 import action_execution
from mistral.api.controllers.v2 import resources
from mistral.db.v2 import api as db_api
from mistral.db.v2.sqlalchemy import models
from mistral import exceptions as exc
from mistral.rpc import clients as rpc_clients
from mistral.rpc.oslo import oslo_client
from mistral.tests.unit.api import base
from mistral.utils import rest_utils
from mistral.workflow import states
from mistral_lib import actions as ml_actions

# This line is needed for correct initialization of messaging config.
oslo_messaging.get_rpc_transport(cfg.CONF)


ACTION_EX_DB = models.ActionExecution(
    id='123',
    workflow_name='flow',
    task_execution=models.TaskExecution(name='task1'),
    task_execution_id='333',
    state=states.SUCCESS,
    state_info=states.SUCCESS,
    tags=['foo', 'fee'],
    name='std.echo',
    description='something',
    accepted=True,
    input={},
    output={},
    created_at=datetime.datetime(1970, 1, 1),
    updated_at=datetime.datetime(1970, 1, 1)
)

AD_HOC_ACTION_EX_DB = models.ActionExecution(
    id='123',
    state=states.SUCCESS,
    state_info=states.SUCCESS,
    tags=['foo', 'fee'],
    name='std.echo',
    description='something',
    accepted=True,
    input={},
    output={},
    created_at=datetime.datetime(1970, 1, 1),
    updated_at=datetime.datetime(1970, 1, 1)
)

AD_HOC_ACTION_EX_ERROR = models.ActionExecution(
    id='123',
    state=states.ERROR,
    state_info=states.ERROR,
    tags=['foo', 'fee'],
    name='std.echo',
    description='something',
    accepted=True,
    input={},
    output={},
    created_at=datetime.datetime(1970, 1, 1),
    updated_at=datetime.datetime(1970, 1, 1)
)

AD_HOC_ACTION_EX_CANCELLED = models.ActionExecution(
    id='123',
    state=states.CANCELLED,
    state_info=states.CANCELLED,
    tags=['foo', 'fee'],
    name='std.echo',
    description='something',
    accepted=True,
    input={},
    output={},
    created_at=datetime.datetime(1970, 1, 1),
    updated_at=datetime.datetime(1970, 1, 1)
)

ACTION_EX_DB_NOT_COMPLETE = models.ActionExecution(
    id='123',
    state=states.RUNNING,
    state_info=states.RUNNING,
    tags=['foo', 'fee'],
    name='std.echo',
    description='something',
    accepted=False,
    input={},
    output={},
    created_at=datetime.datetime(1970, 1, 1),
    updated_at=datetime.datetime(1970, 1, 1)
)

ACTION_EX = {
    'id': '123',
    'workflow_name': 'flow',
    'task_execution_id': '333',
    'task_name': 'task1',
    'state': 'SUCCESS',
    'state_info': 'SUCCESS',
    'tags': ['foo', 'fee'],
    'name': 'std.echo',
    'description': 'something',
    'accepted': True,
    'input': '{}',
    'output': '{}',
    'created_at': '1970-01-01 00:00:00',
    'updated_at': '1970-01-01 00:00:00'
}

UPDATED_ACTION_EX_DB = copy.copy(ACTION_EX_DB).to_dict()
UPDATED_ACTION_EX_DB['state'] = 'SUCCESS'
UPDATED_ACTION_EX_DB['task_name'] = 'task1'
UPDATED_ACTION = copy.deepcopy(ACTION_EX)
UPDATED_ACTION['state'] = 'SUCCESS'
UPDATED_ACTION_OUTPUT = UPDATED_ACTION['output']

CANCELLED_ACTION_EX_DB = copy.copy(ACTION_EX_DB).to_dict()
CANCELLED_ACTION_EX_DB['state'] = 'CANCELLED'
CANCELLED_ACTION_EX_DB['task_name'] = 'task1'
CANCELLED_ACTION = copy.deepcopy(ACTION_EX)
CANCELLED_ACTION['state'] = 'CANCELLED'

PAUSED_ACTION_EX_DB = copy.copy(ACTION_EX_DB).to_dict()
PAUSED_ACTION_EX_DB['state'] = 'PAUSED'
PAUSED_ACTION_EX_DB['task_name'] = 'task1'
PAUSED_ACTION = copy.deepcopy(ACTION_EX)
PAUSED_ACTION['state'] = 'PAUSED'

RUNNING_ACTION_EX_DB = copy.copy(ACTION_EX_DB).to_dict()
RUNNING_ACTION_EX_DB['state'] = 'RUNNING'
RUNNING_ACTION_EX_DB['task_name'] = 'task1'
RUNNING_ACTION = copy.deepcopy(ACTION_EX)
RUNNING_ACTION['state'] = 'RUNNING'

ERROR_ACTION_EX = copy.copy(ACTION_EX_DB).to_dict()
ERROR_ACTION_EX['state'] = 'ERROR'
ERROR_ACTION_EX['task_name'] = 'task1'
ERROR_ACTION = copy.deepcopy(ACTION_EX)
ERROR_ACTION['state'] = 'ERROR'
ERROR_ACTION_RES = ERROR_ACTION['output']

ERROR_OUTPUT = "Fake error, it is a test"
ERROR_ACTION_EX_WITH_OUTPUT = copy.copy(ACTION_EX_DB).to_dict()
ERROR_ACTION_EX_WITH_OUTPUT['state'] = 'ERROR'
ERROR_ACTION_EX_WITH_OUTPUT['task_name'] = 'task1'
ERROR_ACTION_EX_WITH_OUTPUT['output'] = {"output": ERROR_OUTPUT}
ERROR_ACTION_WITH_OUTPUT = copy.deepcopy(ACTION_EX)
ERROR_ACTION_WITH_OUTPUT['state'] = 'ERROR'
ERROR_ACTION_WITH_OUTPUT['output'] = (
    '{"output": "%s"}' % ERROR_OUTPUT
)
ERROR_ACTION_RES_WITH_OUTPUT = {"output": ERROR_OUTPUT}

DEFAULT_ERROR_OUTPUT = "Unknown error"
ERROR_ACTION_EX_FOR_EMPTY_OUTPUT = copy.copy(ACTION_EX_DB).to_dict()
ERROR_ACTION_EX_FOR_EMPTY_OUTPUT['state'] = 'ERROR'
ERROR_ACTION_EX_FOR_EMPTY_OUTPUT['task_name'] = 'task1'
ERROR_ACTION_EX_FOR_EMPTY_OUTPUT['output'] = {"output": DEFAULT_ERROR_OUTPUT}
ERROR_ACTION_FOR_EMPTY_OUTPUT = copy.deepcopy(ERROR_ACTION)
ERROR_ACTION_FOR_EMPTY_OUTPUT['output'] = (
    '{"output": "%s"}' % DEFAULT_ERROR_OUTPUT
)

ERROR_ACTION_WITH_NONE_OUTPUT = copy.deepcopy(ERROR_ACTION)
ERROR_ACTION_WITH_NONE_OUTPUT['output'] = None


BROKEN_ACTION = copy.deepcopy(ACTION_EX)
BROKEN_ACTION['output'] = 'string not escaped'

MOCK_ACTION = mock.MagicMock(return_value=ACTION_EX_DB)
MOCK_ACTION_NOT_COMPLETE = mock.MagicMock(
    return_value=ACTION_EX_DB_NOT_COMPLETE
)

MOCK_ACTION_COMPLETE_ERROR = mock.MagicMock(
    return_value=AD_HOC_ACTION_EX_ERROR
)
MOCK_ACTION_COMPLETE_CANCELLED = mock.MagicMock(
    return_value=AD_HOC_ACTION_EX_CANCELLED
)

MOCK_AD_HOC_ACTION = mock.MagicMock(return_value=AD_HOC_ACTION_EX_DB)
MOCK_ACTIONS = mock.MagicMock(return_value=[ACTION_EX_DB])
MOCK_EMPTY = mock.MagicMock(return_value=[])
MOCK_NOT_FOUND = mock.MagicMock(side_effect=exc.DBEntityNotFoundError())
MOCK_DELETE = mock.MagicMock(return_value=None)

ACTION_EX_DB_WITH_PROJECT_ID = AD_HOC_ACTION_EX_DB.get_clone()
ACTION_EX_DB_WITH_PROJECT_ID.project_id = '<default-project>'


class TestActionExecutionsController(base.APITest):
    def setUp(self):
        super(TestActionExecutionsController, self).setUp()

        self.addCleanup(
            cfg.CONF.set_default,
            'allow_action_execution_deletion',
            False,
            group='api'
        )

    @mock.patch.object(db_api, 'get_action_execution', MOCK_ACTION)
    def test_get(self):
        resp = self.app.get('/v2/action_executions/123')
        action_exec = copy.deepcopy(ACTION_EX)
        del action_exec['task_name']
        self.assertEqual(200, resp.status_int)
        self.assertDictEqual(action_exec, resp.json)

    @mock.patch('mistral.db.v2.api.get_action_execution')
    def test_get_with_fields_filter(self, mocked_get):
        mocked_get.return_value = (ACTION_EX['id'], ACTION_EX['name'],)
        resp = self.app.get('/v2/action_executions/123?fields=name')
        expected = {
            'id': ACTION_EX['id'],
            'name': ACTION_EX['name'],
        }

        self.assertEqual(200, resp.status_int)
        self.assertDictEqual(expected, resp.json)

    @mock.patch.object(db_api, 'get_action_execution')
    def test_get_operational_error(self, mocked_get):
        mocked_get.side_effect = [
            # Emulating DB OperationalError
            sa.exc.OperationalError('Mock', 'mock', 'mock'),
            ACTION_EX_DB  # Successful run
        ]

        resp = self.app.get('/v2/action_executions/123')
        action_exec = copy.deepcopy(ACTION_EX)
        del action_exec['task_name']
        self.assertEqual(200, resp.status_int)
        self.assertDictEqual(action_exec, resp.json)

    def test_basic_get(self):
        resp = self.app.get('/v2/action_executions/')
        self.assertEqual(200, resp.status_int)

    @mock.patch.object(db_api, 'get_action_execution', MOCK_NOT_FOUND)
    def test_get_not_found(self):
        resp = self.app.get('/v2/action_executions/123', expect_errors=True)

        self.assertEqual(404, resp.status_int)

    @mock.patch.object(db_api, 'get_action_execution',
                       return_value=ACTION_EX_DB_WITH_PROJECT_ID)
    def test_get_within_project_id(self, mock_get):
        resp = self.app.get('/v2/action_executions/123')

        self.assertEqual(200, resp.status_int)
        self.assertIn('project_id', resp.json)

    @mock.patch.object(oslo_client.OsloRPCClient, 'sync_call',
                       mock.MagicMock(side_effect=oslo_exc.MessagingTimeout))
    def test_post_timeout(self):

        resp = self.app.post_json(
            '/v2/action_executions',
            {
                'name': 'std.sleep',
                'input': {'seconds': 80}
            },
            expect_errors=True
        )

        error_msg = resp.json['faultstring']
        self.assertEqual(error_msg,
                         'This rpc call "start_action" took longer than '
                         'configured 60 seconds.')

    @mock.patch.object(rpc_clients.EngineClient, 'start_action')
    def test_post(self, f):
        f.return_value = ACTION_EX_DB.to_dict()

        resp = self.app.post_json(
            '/v2/action_executions',
            {
                'name': 'std.echo',
                'input': "{}",
                'params': '{"save_result": true, "run_sync": true}'
            }
        )

        self.assertEqual(201, resp.status_int)

        action_exec = copy.deepcopy(ACTION_EX)
        del action_exec['task_name']

        self.assertDictEqual(action_exec, resp.json)

        f.assert_called_once_with(
            action_exec['name'],
            json.loads(action_exec['input']),
            description=None,
            save_result=True,
            run_sync=True,
            namespace=''
        )

    @mock.patch.object(rpc_clients.EngineClient, 'start_action')
    def test_post_with_timeout(self, f):
        f.return_value = ACTION_EX_DB.to_dict()

        resp = self.app.post_json(
            '/v2/action_executions',
            {
                'name': 'std.echo',
                'input': "{}",
                'params': '{"timeout": 2}'
            }
        )

        self.assertEqual(201, resp.status_int)

        action_exec = copy.deepcopy(ACTION_EX)
        del action_exec['task_name']

        self.assertDictEqual(action_exec, resp.json)

        f.assert_called_once_with(
            action_exec['name'],
            json.loads(action_exec['input']),
            description=None,
            timeout=2,
            namespace=''
        )

    @mock.patch.object(rpc_clients.EngineClient, 'start_action')
    def test_post_json(self, f):
        f.return_value = ACTION_EX_DB.to_dict()

        resp = self.app.post_json(
            '/v2/action_executions',
            {
                'name': 'std.echo',
                'input': {},
                'params': '{"save_result": true}'
            }
        )

        self.assertEqual(201, resp.status_int)

        action_exec = copy.deepcopy(ACTION_EX)
        del action_exec['task_name']

        self.assertDictEqual(action_exec, resp.json)

        f.assert_called_once_with(
            action_exec['name'],
            json.loads(action_exec['input']),
            description=None,
            save_result=True,
            namespace=''
        )

    @mock.patch.object(rpc_clients.EngineClient, 'start_action')
    def test_post_without_input(self, f):
        f.return_value = ACTION_EX_DB.to_dict()
        f.return_value['output'] = {'result': '123'}

        resp = self.app.post_json(
            '/v2/action_executions',
            {'name': 'nova.servers_list'}
        )

        self.assertEqual(201, resp.status_int)
        self.assertEqual('{"result": "123"}', resp.json['output'])

        f.assert_called_once_with('nova.servers_list', {},
                                  description=None,
                                  namespace='')

    def test_post_bad_result(self):
        resp = self.app.post_json(
            '/v2/action_executions',
            {'input': 'null'},
            expect_errors=True
        )

        self.assertEqual(400, resp.status_int)

    def test_post_bad_input(self):
        resp = self.app.post_json(
            '/v2/action_executions',
            {'input': None},
            expect_errors=True
        )

        self.assertEqual(400, resp.status_int)

    def test_post_bad_json_input(self):
        resp = self.app.post_json(
            '/v2/action_executions',
            {'input': 2},
            expect_errors=True
        )

        self.assertEqual(400, resp.status_int)

    @mock.patch.object(rpc_clients.EngineClient, 'on_action_complete')
    def test_put(self, f):
        f.return_value = UPDATED_ACTION_EX_DB

        resp = self.app.put_json('/v2/action_executions/123', UPDATED_ACTION)

        self.assertEqual(200, resp.status_int)
        self.assertDictEqual(UPDATED_ACTION, resp.json)

        f.assert_called_once_with(
            UPDATED_ACTION['id'],
            ml_actions.Result(data=ACTION_EX_DB.output)
        )

    @mock.patch.object(rpc_clients.EngineClient, 'on_action_complete')
    def test_put_error_with_output(self, f):
        f.return_value = ERROR_ACTION_EX_WITH_OUTPUT

        resp = self.app.put_json(
            '/v2/action_executions/123',
            ERROR_ACTION_WITH_OUTPUT
        )

        self.assertEqual(200, resp.status_int)
        self.assertDictEqual(ERROR_ACTION_WITH_OUTPUT, resp.json)

        f.assert_called_once_with(
            ERROR_ACTION_WITH_OUTPUT['id'],
            ml_actions.Result(error=ERROR_ACTION_RES_WITH_OUTPUT)
        )

    @mock.patch.object(rpc_clients.EngineClient, 'on_action_complete')
    def test_put_error_with_unknown_reason(self, f):
        f.return_value = ERROR_ACTION_EX_FOR_EMPTY_OUTPUT
        resp = self.app.put_json('/v2/action_executions/123', ERROR_ACTION)

        self.assertEqual(200, resp.status_int)
        self.assertDictEqual(ERROR_ACTION_FOR_EMPTY_OUTPUT, resp.json)

        f.assert_called_once_with(
            ERROR_ACTION_FOR_EMPTY_OUTPUT['id'],
            ml_actions.Result(error=DEFAULT_ERROR_OUTPUT)
        )

    @mock.patch.object(rpc_clients.EngineClient, 'on_action_complete')
    def test_put_error_with_unknown_reason_output_none(self, f):
        f.return_value = ERROR_ACTION_EX_FOR_EMPTY_OUTPUT
        resp = self.app.put_json(
            '/v2/action_executions/123',
            ERROR_ACTION_WITH_NONE_OUTPUT
        )

        self.assertEqual(200, resp.status_int)
        self.assertDictEqual(ERROR_ACTION_FOR_EMPTY_OUTPUT, resp.json)

        f.assert_called_once_with(
            ERROR_ACTION_FOR_EMPTY_OUTPUT['id'],
            ml_actions.Result(error=DEFAULT_ERROR_OUTPUT)
        )

    @mock.patch.object(rpc_clients.EngineClient, 'on_action_complete')
    def test_put_cancelled(self, on_action_complete_mock_func):
        on_action_complete_mock_func.return_value = CANCELLED_ACTION_EX_DB

        resp = self.app.put_json('/v2/action_executions/123', CANCELLED_ACTION)

        self.assertEqual(200, resp.status_int)
        self.assertDictEqual(CANCELLED_ACTION, resp.json)

        on_action_complete_mock_func.assert_called_once_with(
            CANCELLED_ACTION['id'],
            ml_actions.Result(cancel=True)
        )

    @mock.patch.object(rpc_clients.EngineClient, 'on_action_update')
    def test_put_paused(self, on_action_update_mock_func):
        on_action_update_mock_func.return_value = PAUSED_ACTION_EX_DB

        resp = self.app.put_json('/v2/action_executions/123', PAUSED_ACTION)

        self.assertEqual(200, resp.status_int)
        self.assertDictEqual(PAUSED_ACTION, resp.json)

        on_action_update_mock_func.assert_called_once_with(
            PAUSED_ACTION['id'],
            PAUSED_ACTION['state']
        )

    @mock.patch.object(rpc_clients.EngineClient, 'on_action_update')
    def test_put_resume(self, on_action_update_mock_func):
        on_action_update_mock_func.return_value = RUNNING_ACTION_EX_DB

        resp = self.app.put_json('/v2/action_executions/123', RUNNING_ACTION)

        self.assertEqual(200, resp.status_int)
        self.assertDictEqual(RUNNING_ACTION, resp.json)

        on_action_update_mock_func.assert_called_once_with(
            RUNNING_ACTION['id'],
            RUNNING_ACTION['state']
        )

    @mock.patch.object(
        rpc_clients.EngineClient,
        'on_action_complete',
        MOCK_NOT_FOUND
    )
    def test_put_no_action_ex(self):
        resp = self.app.put_json(
            '/v2/action_executions/123',
            UPDATED_ACTION,
            expect_errors=True
        )

        self.assertEqual(404, resp.status_int)

    def test_put_bad_state(self):
        action = copy.deepcopy(ACTION_EX)
        action['state'] = 'DELAYED'

        resp = self.app.put_json(
            '/v2/action_executions/123',
            action,
            expect_errors=True
        )

        self.assertEqual(400, resp.status_int)
        self.assertIn('Expected one of', resp.json['faultstring'])

    def test_put_bad_result(self):
        resp = self.app.put_json(
            '/v2/action_executions/123',
            BROKEN_ACTION,
            expect_errors=True
        )

        self.assertEqual(400, resp.status_int)

    @mock.patch.object(rpc_clients.EngineClient, 'on_action_complete')
    def test_put_without_result(self, f):
        action_ex = copy.deepcopy(UPDATED_ACTION)
        del action_ex['output']

        f.return_value = UPDATED_ACTION_EX_DB

        resp = self.app.put_json('/v2/action_executions/123', action_ex)

        self.assertEqual(200, resp.status_int)

    @mock.patch.object(db_api, 'get_action_executions', MOCK_ACTIONS)
    def test_get_all(self):
        resp = self.app.get('/v2/action_executions')
        action_exec = copy.deepcopy(ACTION_EX)
        del action_exec['task_name']
        self.assertEqual(200, resp.status_int)

        self.assertEqual(1, len(resp.json['action_executions']))
        self.assertDictEqual(action_exec, resp.json['action_executions'][0])

    @mock.patch.object(db_api, 'get_action_executions')
    def test_get_all_operational_error(self, mocked_get_all):
        mocked_get_all.side_effect = [
            # Emulating DB OperationalError
            sa.exc.OperationalError('Mock', 'mock', 'mock'),
            [ACTION_EX_DB]  # Successful run
        ]

        resp = self.app.get('/v2/action_executions')
        action_exec = copy.deepcopy(ACTION_EX)
        del action_exec['task_name']

        self.assertEqual(200, resp.status_int)

        self.assertEqual(1, len(resp.json['action_executions']))
        self.assertDictEqual(action_exec, resp.json['action_executions'][0])

    @mock.patch.object(rest_utils, 'get_all',
                       return_value=resources.ActionExecutions())
    def test_get_all_without_output(self, mock_get_all):
        resp = self.app.get('/v2/action_executions')

        args, kwargs = mock_get_all.call_args
        resource_function = kwargs['resource_function']

        self.assertEqual(200, resp.status_int)
        self.assertEqual(
            action_execution._get_action_execution_resource_for_list,
            resource_function
        )

    @mock.patch.object(rest_utils, 'get_all',
                       return_value=resources.ActionExecutions())
    def test_get_all_with_output(self, mock_get_all):
        resp = self.app.get('/v2/action_executions?include_output=true')

        args, kwargs = mock_get_all.call_args
        resource_function = kwargs['resource_function']

        self.assertEqual(200, resp.status_int)
        self.assertEqual(
            action_execution._get_action_execution_resource,
            resource_function
        )

    @mock.patch.object(db_api, 'get_action_executions', MOCK_EMPTY)
    def test_get_all_empty(self):
        resp = self.app.get('/v2/action_executions')

        self.assertEqual(200, resp.status_int)

        self.assertEqual(0, len(resp.json['action_executions']))

    @mock.patch.object(db_api, 'get_action_execution', MOCK_AD_HOC_ACTION)
    @mock.patch.object(db_api, 'delete_action_execution', MOCK_DELETE)
    def test_delete(self):
        cfg.CONF.set_default('allow_action_execution_deletion', True, 'api')

        resp = self.app.delete('/v2/action_executions/123')

        self.assertEqual(204, resp.status_int)

    @mock.patch.object(db_api, 'get_action_execution', MOCK_NOT_FOUND)
    def test_delete_not_found(self):
        cfg.CONF.set_default('allow_action_execution_deletion', True, 'api')

        resp = self.app.delete('/v2/action_executions/123', expect_errors=True)

        self.assertEqual(404, resp.status_int)

    def test_delete_not_allowed(self):
        resp = self.app.delete('/v2/action_executions/123', expect_errors=True)

        self.assertEqual(403, resp.status_int)
        self.assertIn(
            "Action execution deletion is not allowed",
            resp.body.decode()
        )

    @mock.patch.object(db_api, 'get_action_execution', MOCK_ACTION)
    def test_delete_action_execution_with_task(self):
        cfg.CONF.set_default('allow_action_execution_deletion', True, 'api')

        resp = self.app.delete('/v2/action_executions/123', expect_errors=True)

        self.assertEqual(403, resp.status_int)
        self.assertIn(
            "Only ad-hoc action execution can be deleted",
            resp.body.decode()
        )

    @mock.patch.object(
        db_api,
        'get_action_execution',
        MOCK_ACTION_NOT_COMPLETE
    )
    def test_delete_action_execution_not_complete(self):
        cfg.CONF.set_default('allow_action_execution_deletion', True, 'api')

        resp = self.app.delete('/v2/action_executions/123', expect_errors=True)

        self.assertEqual(403, resp.status_int)
        self.assertIn(
            "Only completed action execution can be deleted",
            resp.body.decode()
        )

    @mock.patch.object(
        db_api,
        'get_action_execution',
        MOCK_ACTION_COMPLETE_ERROR
    )
    @mock.patch.object(db_api, 'delete_action_execution', MOCK_DELETE)
    def test_delete_action_execution_complete_error(self):
        cfg.CONF.set_default('allow_action_execution_deletion', True, 'api')

        resp = self.app.delete('/v2/action_executions/123', expect_errors=True)

        self.assertEqual(204, resp.status_int)

    @mock.patch.object(
        db_api,
        'get_action_execution',
        MOCK_ACTION_COMPLETE_CANCELLED
    )
    @mock.patch.object(db_api, 'delete_action_execution', MOCK_DELETE)
    def test_delete_action_execution_complete_cancelled(self):
        cfg.CONF.set_default('allow_action_execution_deletion', True, 'api')

        resp = self.app.delete('/v2/action_executions/123', expect_errors=True)

        self.assertEqual(204, resp.status_int)
