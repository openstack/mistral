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
from mistral import exceptions as exc
from mistral.tests.unit.api import base
from mistral.workflow import data_flow
from mistral.workflow import states

# TODO(everyone): later we need additional tests verifying all the errors etc.

RESULT = {"some": "result"}
PUBLISHED = {"var": "val"}
task_ex = models.TaskExecution(
    id='123',
    name='task',
    workflow_name='flow',
    spec={},
    action_spec={},
    state=states.RUNNING,
    tags=['a', 'b'],
    in_context={},
    runtime_context={},
    workflow_execution_id='123',
    created_at=datetime.datetime(1970, 1, 1),
    updated_at=datetime.datetime(1970, 1, 1),
    published=PUBLISHED
)

TASK = {
    'id': '123',
    'name': 'task',
    'workflow_name': 'flow',
    'state': 'RUNNING',
    'workflow_execution_id': '123',
    'created_at': '1970-01-01 00:00:00',
    'updated_at': '1970-01-01 00:00:00',
    'result': json.dumps(RESULT),
    'published': json.dumps(PUBLISHED)
}

UPDATED_task_ex = copy.copy(task_ex)
UPDATED_task_ex['state'] = 'SUCCESS'
UPDATED_TASK = copy.copy(TASK)
UPDATED_TASK['state'] = 'SUCCESS'

ERROR_task_ex = copy.copy(task_ex)
ERROR_task_ex['state'] = 'ERROR'
ERROR_TASK = copy.copy(TASK)
ERROR_TASK['state'] = 'ERROR'

BROKEN_TASK = copy.copy(TASK)

MOCK_TASK = mock.MagicMock(return_value=task_ex)
MOCK_TASKS = mock.MagicMock(return_value=[task_ex])
MOCK_EMPTY = mock.MagicMock(return_value=[])
MOCK_NOT_FOUND = mock.MagicMock(side_effect=exc.NotFoundException())


@mock.patch.object(
    data_flow,
    'get_task_execution_result', mock.Mock(return_value=RESULT)
)
class TestTasksController(base.FunctionalTest):
    @mock.patch.object(db_api, 'get_task_execution', MOCK_TASK)
    def test_get(self):
        resp = self.app.get('/v2/tasks/123')

        self.assertEqual(resp.status_int, 200)
        self.assertDictEqual(TASK, resp.json)

    @mock.patch.object(db_api, 'get_task_execution', MOCK_NOT_FOUND)
    def test_get_not_found(self):
        resp = self.app.get('/v2/tasks/123', expect_errors=True)

        self.assertEqual(resp.status_int, 404)

    @mock.patch.object(db_api, 'get_task_executions', MOCK_TASKS)
    def test_get_all(self):
        resp = self.app.get('/v2/tasks')

        self.assertEqual(resp.status_int, 200)

        self.assertEqual(len(resp.json['tasks']), 1)
        self.assertDictEqual(TASK, resp.json['tasks'][0])

    @mock.patch.object(db_api, 'get_task_executions', MOCK_EMPTY)
    def test_get_all_empty(self):
        resp = self.app.get('/v2/tasks')

        self.assertEqual(resp.status_int, 200)

        self.assertEqual(len(resp.json['tasks']), 0)
