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

from mistral.db import api as db_api
from mistral import engine
from mistral.tests.api import base

# TODO(everyone): later we need additional tests verifying all the errors etc.

TASKS = [
    {
        'id': "1",
        'workbook_name': "my_workbook",
        'execution_id': '123',
        'name': 'my_task',
        'description': 'My cool task',
        'state': 'RUNNING',
        'tags': ['deployment', 'demo'],
        'output': {
            'a': 'b'
        },
        'parameters': {
            'c': 'd'
        }
    }
]

UPDATED_TASK = TASKS[0].copy()
UPDATED_TASK['state'] = 'STOPPED'


def canonize(json_dict):
    if json_dict.get('output'):
        json_dict['output'] = json.loads(json_dict['output'])

    if json_dict.get('parameters'):
        json_dict['parameters'] = json.loads(json_dict['parameters'])

    return json_dict


class TestTasksController(base.FunctionalTest):
    @mock.patch.object(db_api, "task_get",
                       mock.MagicMock(return_value=TASKS[0]))
    def test_workbook_get(self):
        resp = self.app.get('/v1/workbooks/my_workbook/executions/123/tasks/1')

        self.assertEqual(resp.status_int, 200)
        self.assertDictEqual(TASKS[0], canonize(resp.json))

    @mock.patch.object(db_api, "task_get",
                       mock.MagicMock(return_value=TASKS[0]))
    def test_execution_get(self):
        resp = self.app.get('/v1/executions/123/tasks/1')

        self.assertEqual(resp.status_int, 200)
        self.assertDictEqual(TASKS[0], canonize(resp.json))

    @mock.patch.object(db_api, "task_get",
                       mock.MagicMock(return_value=TASKS[0]))
    def test_root_get(self):
        resp = self.app.get('/v1/tasks/1')

        self.assertEqual(resp.status_int, 200)
        self.assertDictEqual(TASKS[0], canonize(resp.json))

    @mock.patch.object(engine.EngineClient, "convey_task_result",
                       mock.MagicMock(return_value=UPDATED_TASK))
    @mock.patch.object(db_api, "task_get",
                       mock.MagicMock(return_value=TASKS[0]))
    def test_workbook_put(self):
        resp = self.app.put_json(
            '/v1/workbooks/my_workbook/executions/123/tasks/1',
            dict(state='STOPPED'))
        self.assertEqual(resp.status_int, 200)
        self.assertDictEqual(UPDATED_TASK, canonize(resp.json))

    @mock.patch.object(engine.EngineClient, "convey_task_result",
                       mock.MagicMock(return_value=UPDATED_TASK))
    @mock.patch.object(db_api, "task_get",
                       mock.MagicMock(return_value=TASKS[0]))
    def test_execution_put(self):
        resp = self.app.put_json(
            '/v1/executions/123/tasks/1',
            dict(state='STOPPED'))
        self.assertEqual(resp.status_int, 200)
        self.assertDictEqual(UPDATED_TASK, canonize(resp.json))

    @mock.patch.object(engine.EngineClient, "convey_task_result",
                       mock.MagicMock(return_value=UPDATED_TASK))
    @mock.patch.object(db_api, "task_get",
                       mock.MagicMock(return_value=TASKS[0]))
    def test_root_put(self):
        resp = self.app.put_json(
            '/v1/tasks/1',
            dict(state='STOPPED'))
        self.assertEqual(resp.status_int, 200)
        self.assertDictEqual(UPDATED_TASK, canonize(resp.json))

    @mock.patch.object(engine.EngineClient, "convey_task_result",
                       mock.MagicMock(return_value=UPDATED_TASK))
    def test_put_no_task(self):
        resp = self.app.put_json(
            '/v1/workbooks/my_workbook/executions/123/tasks/1',
            dict(state='STOPPED'), expect_errors=True)
        self.assertEqual(resp.status_int, 404)

    @mock.patch.object(db_api, "tasks_get",
                       mock.MagicMock(return_value=TASKS))
    @mock.patch.object(db_api, "ensure_execution_exists",
                       mock.MagicMock(return_value={'id': "abc123"}))
    def test_workbook_get_all(self):
        resp = self.app.get('/v1/workbooks/my_workbook/executions/123/tasks')

        self.assertEqual(resp.status_int, 200)

        self.assertEqual(len(resp.json), 1)
        self.assertDictEqual(TASKS[0], canonize(resp.json['tasks'][0]))

    @mock.patch.object(db_api, "tasks_get",
                       mock.MagicMock(return_value=TASKS))
    @mock.patch.object(db_api, "ensure_execution_exists",
                       mock.MagicMock(return_value={'id': "abc123"}))
    def test_execution_get_all(self):
        resp = self.app.get('/v1/executions/123/tasks')

        self.assertEqual(resp.status_int, 200)

        self.assertEqual(len(resp.json), 1)
        self.assertDictEqual(TASKS[0], canonize(resp.json['tasks'][0]))

    @mock.patch.object(db_api, "tasks_get",
                       mock.MagicMock(return_value=TASKS))
    @mock.patch.object(db_api, "ensure_execution_exists",
                       mock.MagicMock(return_value={'id': "abc123"}))
    def test_root_get_all(self):
        resp = self.app.get('/v1/tasks')

        self.assertEqual(resp.status_int, 200)

        self.assertEqual(len(resp.json), 1)
        self.assertDictEqual(TASKS[0], canonize(resp.json['tasks'][0]))

    @mock.patch.object(db_api, "tasks_get",
                       mock.MagicMock(return_value=TASKS))
    def test_get_all_nonexistent_execution(self):
        self.assertNotFound('/v1/workbooks/my_workbook/executions/123/tasks')
