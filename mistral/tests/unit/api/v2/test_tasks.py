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
import json
import mock

from mistral.db.v2 import api as db_api
from mistral.db.v2.sqlalchemy import models
from mistral.engine1 import rpc
from mistral import exceptions as exc
from mistral.tests.unit.api import base
from mistral.workflow import states
from mistral.workflow import utils as wf_utils

# TODO(everyone): later we need additional tests verifying all the errors etc.

TASK_DB = models.Task(
    id='123',
    name='task',
    wf_name='flow',
    spec={},
    action_spec={},
    state=states.RUNNING,
    tags=['a', 'b'],
    in_context={},
    input={},
    output={},
    runtime_context={},
    execution_id='123',
    created_at=datetime.datetime(1970, 1, 1),
    updated_at=datetime.datetime(1970, 1, 1)
)

TASK = {
    'id': '123',
    'name': 'task',
    'wf_name': 'flow',
    'state': 'RUNNING',
    'result': '{}',
    'input': '{}',
    'output': '{}',
    'execution_id': '123',
    'created_at': '1970-01-01 00:00:00',
    'updated_at': '1970-01-01 00:00:00'
}

UPDATED_TASK_DB = copy.copy(TASK_DB)
UPDATED_TASK_DB['state'] = 'SUCCESS'
UPDATED_TASK = copy.copy(TASK)
UPDATED_TASK['state'] = 'SUCCESS'
UPDATED_TASK_RES = wf_utils.TaskResult(json.loads(UPDATED_TASK['result']))

ERROR_TASK_DB = copy.copy(TASK_DB)
ERROR_TASK_DB['state'] = 'ERROR'
ERROR_TASK = copy.copy(TASK)
ERROR_TASK['state'] = 'ERROR'
ERROR_TASK_RES = wf_utils.TaskResult(None, json.loads(ERROR_TASK['result']))

BROKEN_TASK = copy.copy(TASK)
BROKEN_TASK['result'] = 'string not escaped'

MOCK_TASK = mock.MagicMock(return_value=TASK_DB)
MOCK_TASKS = mock.MagicMock(return_value=[TASK_DB])
MOCK_EMPTY = mock.MagicMock(return_value=[])
MOCK_NOT_FOUND = mock.MagicMock(side_effect=exc.NotFoundException())


class TestTasksController(base.FunctionalTest):
    @mock.patch.object(db_api, 'get_task', MOCK_TASK)
    def test_get(self):
        resp = self.app.get('/v2/tasks/123')

        self.assertEqual(resp.status_int, 200)
        self.assertDictEqual(TASK, resp.json)

    @mock.patch.object(db_api, 'get_task', MOCK_NOT_FOUND)
    def test_get_not_found(self):
        resp = self.app.get('/v2/tasks/123', expect_errors=True)

        self.assertEqual(resp.status_int, 404)

    @mock.patch.object(rpc.EngineClient, 'on_task_result')
    def test_put(self, f):
        f.return_value = UPDATED_TASK_DB.to_dict()

        resp = self.app.put_json('/v2/tasks/123', UPDATED_TASK)

        self.assertEqual(resp.status_int, 200)
        self.assertDictEqual(UPDATED_TASK, resp.json)

        f.assert_called_once_with(UPDATED_TASK['id'], UPDATED_TASK_RES)

    @mock.patch.object(rpc.EngineClient, 'on_task_result')
    def test_put_error(self, f):
        f.return_value = ERROR_TASK_DB.to_dict()

        resp = self.app.put_json('/v2/tasks/123', ERROR_TASK)

        self.assertEqual(resp.status_int, 200)
        self.assertDictEqual(ERROR_TASK, resp.json)

        f.assert_called_once_with(ERROR_TASK['id'], ERROR_TASK_RES)

    @mock.patch.object(rpc.EngineClient, 'on_task_result', MOCK_NOT_FOUND)
    def test_put_no_task(self):
        resp = self.app.put_json('/v2/tasks/123', UPDATED_TASK,
                                 expect_errors=True)

        self.assertEqual(resp.status_int, 404)

    @mock.patch.object(rpc.EngineClient, 'on_task_result')
    def test_put_bad_result(self, f):
        resp = self.app.put_json('/v2/tasks/123', BROKEN_TASK,
                                 expect_errors=True)

        self.assertEqual(resp.status_int, 400)

    @mock.patch.object(rpc.EngineClient, 'on_task_result')
    def test_put_without_result(self, f):
        task = copy.copy(UPDATED_TASK)
        del task['result']
        f.return_value = UPDATED_TASK_DB.to_dict()
        resp = self.app.put_json('/v2/tasks/123', task)

        self.assertEqual(resp.status_int, 200)

    @mock.patch.object(db_api, 'get_tasks', MOCK_TASKS)
    def test_get_all(self):
        resp = self.app.get('/v2/tasks')

        self.assertEqual(resp.status_int, 200)

        self.assertEqual(len(resp.json['tasks']), 1)
        self.assertDictEqual(TASK, resp.json['tasks'][0])

    @mock.patch.object(db_api, 'get_tasks', MOCK_EMPTY)
    def test_get_all_empty(self):
        resp = self.app.get('/v2/tasks')

        self.assertEqual(resp.status_int, 200)

        self.assertEqual(len(resp.json['tasks']), 0)
