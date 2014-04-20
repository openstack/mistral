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

import mock

from mistral.tests.api import base
from mistral.db import api as db_api
from mistral.engine import client

# TODO: later we need additional tests verifying all the errors etc.

TASKS = [
    {
        'id': "1",
        'workbook_name': "my_workbook",
        'execution_id': '123',
        'name': 'my_task',
        'description': 'My cool task',
        'action': 'my_action',
        'state': 'RUNNING',
        'tags': ['deployment', 'demo']
    }
]

UPDATED_TASK = TASKS[0].copy()
UPDATED_TASK['state'] = 'STOPPED'


class TestTasksController(base.FunctionalTest):
    @mock.patch.object(db_api, "task_get",
                       mock.MagicMock(return_value=TASKS[0]))
    def test_get(self):
        resp = self.app.get('/v1/workbooks/my_workbook/executions/123/tasks/1')

        self.assertEqual(resp.status_int, 200)
        self.assertDictEqual(TASKS[0], resp.json)

    @mock.patch.object(client.EngineClient, "convey_task_result",
                       mock.MagicMock(return_value=UPDATED_TASK))
    def test_put(self):
        resp = self.app.put_json(
            '/v1/workbooks/my_workbook/executions/123/tasks/1',
            dict(state='STOPPED'))

        self.assertEqual(resp.status_int, 200)
        self.assertDictEqual(UPDATED_TASK, resp.json)

    @mock.patch.object(db_api, "tasks_get",
                       mock.MagicMock(return_value=TASKS))
    def test_get_all(self):
        resp = self.app.get('/v1/workbooks/my_workbook/executions/123/tasks')

        self.assertEqual(resp.status_int, 200)

        self.assertEqual(len(resp.json), 1)
        self.assertDictEqual(TASKS[0], resp.json['tasks'][0])
