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
import json
import mock

from mistral.db.v2 import api as db_api
from mistral.db.v2.sqlalchemy import models
from mistral.engine.rpc_backend import rpc
from mistral import exceptions as exc
from mistral.tests.unit.api import base
from mistral.workflow import data_flow
from mistral.workflow import states

# TODO(everyone): later we need additional tests verifying all the errors etc.

RESULT = {"some": "result"}
PUBLISHED = {"var": "val"}

WF_EX = models.WorkflowExecution(
    id='abc',
    workflow_name='some',
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

TASK_EX = models.TaskExecution(
    id='123',
    name='task',
    workflow_name='flow',
    workflow_id='123e4567-e89b-12d3-a456-426655441111',
    spec={
        'type': 'direct',
        'version': '2.0',
        'name': 'task'
    },
    action_spec={},
    state=states.RUNNING,
    tags=['a', 'b'],
    in_context={},
    runtime_context={},
    workflow_execution_id=WF_EX.id,
    created_at=datetime.datetime(1970, 1, 1),
    updated_at=datetime.datetime(1970, 1, 1),
    published=PUBLISHED,
    processed=True
)

WITH_ITEMS_TASK_EX = models.TaskExecution(
    id='123',
    name='task',
    workflow_name='flow',
    workflow_id='123e4567-e89b-12d3-a456-426655441111',
    spec={
        'type': 'direct',
        'version': '2.0',
        'name': 'task',
        'with-items': 'var in [1, 2, 3]'
    },
    action_spec={},
    state=states.RUNNING,
    tags=['a', 'b'],
    in_context={},
    runtime_context={},
    workflow_execution_id=WF_EX.id,
    created_at=datetime.datetime(1970, 1, 1),
    updated_at=datetime.datetime(1970, 1, 1),
    published=PUBLISHED,
    processed=True
)

TASK = {
    'id': '123',
    'name': 'task',
    'workflow_name': 'flow',
    'workflow_id': '123e4567-e89b-12d3-a456-426655441111',
    'state': 'RUNNING',
    'workflow_execution_id': WF_EX.id,
    'created_at': '1970-01-01 00:00:00',
    'updated_at': '1970-01-01 00:00:00',
    'result': json.dumps(RESULT),
    'published': json.dumps(PUBLISHED),
    'processed': True
}

TASK_WITHOUT_RESULT = copy.deepcopy(TASK)
del TASK_WITHOUT_RESULT['result']

UPDATED_TASK_EX = copy.deepcopy(TASK_EX)
UPDATED_TASK_EX['state'] = 'SUCCESS'
UPDATED_TASK = copy.deepcopy(TASK)
UPDATED_TASK['state'] = 'SUCCESS'

ERROR_TASK_EX = copy.deepcopy(TASK_EX)
ERROR_TASK_EX['state'] = 'ERROR'
ERROR_ITEMS_TASK_EX = copy.deepcopy(WITH_ITEMS_TASK_EX)
ERROR_ITEMS_TASK_EX['state'] = 'ERROR'
ERROR_TASK = copy.deepcopy(TASK)
ERROR_TASK['state'] = 'ERROR'

BROKEN_TASK = copy.deepcopy(TASK)

RERUN_TASK = {
    'id': '123',
    'state': 'RUNNING'
}

MOCK_WF_EX = mock.MagicMock(return_value=WF_EX)
MOCK_TASK = mock.MagicMock(return_value=TASK_EX)
MOCK_TASKS = mock.MagicMock(return_value=[TASK_EX])
MOCK_EMPTY = mock.MagicMock(return_value=[])
MOCK_NOT_FOUND = mock.MagicMock(side_effect=exc.DBEntityNotFoundError())
MOCK_ERROR_TASK = mock.MagicMock(return_value=ERROR_TASK_EX)
MOCK_ERROR_ITEMS_TASK = mock.MagicMock(return_value=ERROR_ITEMS_TASK_EX)


@mock.patch.object(
    data_flow,
    'get_task_execution_result', mock.Mock(return_value=RESULT)
)
class TestTasksController(base.APITest):
    @mock.patch.object(db_api, 'get_task_execution', MOCK_TASK)
    def test_get(self):
        resp = self.app.get('/v2/tasks/123')

        self.assertEqual(200, resp.status_int)
        self.assertDictEqual(TASK, resp.json)

    @mock.patch.object(db_api, 'get_task_execution', MOCK_NOT_FOUND)
    def test_get_not_found(self):
        resp = self.app.get('/v2/tasks/123', expect_errors=True)

        self.assertEqual(404, resp.status_int)

    @mock.patch.object(db_api, 'get_task_executions', MOCK_TASKS)
    def test_get_all(self):
        resp = self.app.get('/v2/tasks')

        self.assertEqual(200, resp.status_int)

        self.assertEqual(1, len(resp.json['tasks']))
        self.assertDictEqual(TASK_WITHOUT_RESULT, resp.json['tasks'][0])

    @mock.patch.object(db_api, 'get_task_executions', MOCK_EMPTY)
    def test_get_all_empty(self):
        resp = self.app.get('/v2/tasks')

        self.assertEqual(200, resp.status_int)

        self.assertEqual(0, len(resp.json['tasks']))

    @mock.patch.object(db_api, 'get_workflow_execution', MOCK_WF_EX)
    @mock.patch.object(
        db_api,
        'get_task_execution',
        mock.MagicMock(side_effect=[ERROR_TASK_EX, TASK_EX])
    )
    @mock.patch.object(rpc.EngineClient, 'rerun_workflow', MOCK_WF_EX)
    def test_put(self):
        params = copy.deepcopy(RERUN_TASK)
        params['reset'] = True

        resp = self.app.put_json('/v2/tasks/123', params=params)

        self.assertEqual(200, resp.status_int)
        self.assertDictEqual(TASK, resp.json)

        rpc.EngineClient.rerun_workflow.assert_called_with(
            TASK_EX.id,
            reset=params['reset'],
            env=None
        )

    @mock.patch.object(db_api, 'get_workflow_execution', MOCK_WF_EX)
    @mock.patch.object(
        db_api,
        'get_task_execution',
        mock.MagicMock(side_effect=[ERROR_TASK_EX, TASK_EX])
    )
    @mock.patch.object(rpc.EngineClient, 'rerun_workflow', MOCK_WF_EX)
    def test_put_missing_reset(self):
        params = copy.deepcopy(RERUN_TASK)

        resp = self.app.put_json(
            '/v2/tasks/123',
            params=params,
            expect_errors=True)

        self.assertEqual(400, resp.status_int)
        self.assertIn('faultstring', resp.json)
        self.assertIn('Mandatory field missing', resp.json['faultstring'])

    @mock.patch.object(db_api, 'get_workflow_execution', MOCK_WF_EX)
    @mock.patch.object(
        db_api,
        'get_task_execution',
        mock.MagicMock(side_effect=[ERROR_ITEMS_TASK_EX, WITH_ITEMS_TASK_EX])
    )
    @mock.patch.object(rpc.EngineClient, 'rerun_workflow', MOCK_WF_EX)
    def test_put_with_items(self):
        params = copy.deepcopy(RERUN_TASK)
        params['reset'] = False

        resp = self.app.put_json('/v2/tasks/123', params=params)

        self.assertEqual(200, resp.status_int)
        self.assertDictEqual(TASK, resp.json)

    @mock.patch.object(db_api, 'get_workflow_execution', MOCK_WF_EX)
    @mock.patch.object(
        db_api,
        'get_task_execution',
        mock.MagicMock(side_effect=[ERROR_TASK_EX, TASK_EX])
    )
    @mock.patch.object(rpc.EngineClient, 'rerun_workflow', MOCK_WF_EX)
    def test_put_env(self):
        params = copy.deepcopy(RERUN_TASK)
        params['reset'] = True
        params['env'] = '{"k1": "def"}'

        resp = self.app.put_json('/v2/tasks/123', params=params)

        self.assertEqual(200, resp.status_int)
        self.assertDictEqual(TASK, resp.json)

        rpc.EngineClient.rerun_workflow.assert_called_with(
            TASK_EX.id,
            reset=params['reset'],
            env=json.loads(params['env'])
        )

    @mock.patch.object(db_api, 'get_workflow_execution', MOCK_WF_EX)
    @mock.patch.object(db_api, 'get_task_execution', MOCK_TASK)
    def test_put_current_task_not_in_error(self):
        params = copy.deepcopy(RERUN_TASK)
        params['reset'] = True

        resp = self.app.put_json(
            '/v2/tasks/123',
            params=params,
            expect_errors=True
        )

        self.assertEqual(400, resp.status_int)
        self.assertIn('faultstring', resp.json)
        self.assertIn('execution must be in ERROR', resp.json['faultstring'])

    @mock.patch.object(db_api, 'get_workflow_execution', MOCK_WF_EX)
    @mock.patch.object(db_api, 'get_task_execution', MOCK_ERROR_TASK)
    def test_put_invalid_state(self):
        params = copy.deepcopy(RERUN_TASK)
        params['state'] = states.IDLE
        params['reset'] = True

        resp = self.app.put_json(
            '/v2/tasks/123',
            params=params,
            expect_errors=True
        )

        self.assertEqual(400, resp.status_int)
        self.assertIn('faultstring', resp.json)
        self.assertIn('Invalid task state', resp.json['faultstring'])

    @mock.patch.object(db_api, 'get_workflow_execution', MOCK_WF_EX)
    @mock.patch.object(db_api, 'get_task_execution', MOCK_ERROR_TASK)
    def test_put_invalid_reset(self):
        params = copy.deepcopy(RERUN_TASK)
        params['reset'] = False

        resp = self.app.put_json(
            '/v2/tasks/123',
            params=params,
            expect_errors=True
        )

        self.assertEqual(400, resp.status_int)
        self.assertIn('faultstring', resp.json)
        self.assertIn('Only with-items task', resp.json['faultstring'])

    @mock.patch.object(db_api, 'get_workflow_execution', MOCK_WF_EX)
    @mock.patch.object(db_api, 'get_task_execution', MOCK_ERROR_TASK)
    def test_put_mismatch_task_name(self):
        params = copy.deepcopy(RERUN_TASK)
        params['name'] = 'abc'
        params['reset'] = True

        resp = self.app.put_json(
            '/v2/tasks/123',
            params=params,
            expect_errors=True
        )

        self.assertEqual(400, resp.status_int)
        self.assertIn('faultstring', resp.json)
        self.assertIn('Task name does not match', resp.json['faultstring'])

    @mock.patch.object(db_api, 'get_workflow_execution', MOCK_WF_EX)
    @mock.patch.object(db_api, 'get_task_execution', MOCK_ERROR_TASK)
    def test_put_mismatch_workflow_name(self):
        params = copy.deepcopy(RERUN_TASK)
        params['workflow_name'] = 'xyz'
        params['reset'] = True

        resp = self.app.put_json(
            '/v2/tasks/123',
            params=params,
            expect_errors=True
        )

        self.assertEqual(400, resp.status_int)
        self.assertIn('faultstring', resp.json)
        self.assertIn('Workflow name does not match', resp.json['faultstring'])
