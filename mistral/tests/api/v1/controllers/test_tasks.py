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


class TestTasksController(base.FunctionalTest):
    def setUp(self):
        super(TestTasksController, self).setUp()
        self.task_get = db_api.task_get
        self.task_update = db_api.task_update
        self.tasks_get = db_api.tasks_get

    def tearDown(self):
        super(TestTasksController, self).tearDown()
        db_api.task_get = self.task_get
        db_api.task_update = self.task_update
        db_api.tasks_get = self.tasks_get

    def test_get(self):
        db_api.task_get = mock.MagicMock(return_value=TASKS[0])

        resp = self.app.get('/v1/workbooks/my_workbook/executions/123/tasks/1')

        self.assertEqual(resp.status_int, 200)
        self.assertDictEqual(TASKS[0], resp.json)

    def test_put(self):
        updated_task = TASKS[0].copy()
        updated_task['state'] = 'STOPPED'

        db_api.task_update = mock.MagicMock(return_value=updated_task)

        resp = self.app.put_json(
            '/v1/workbooks/my_workbook/executions/123/tasks/1',
            dict(state='STOPPED'))

        self.assertEqual(resp.status_int, 200)
        self.assertDictEqual(updated_task, resp.json)

    def test_get_all(self):
        db_api.tasks_get = mock.MagicMock(return_value=TASKS)

        resp = self.app.get('/v1/workbooks/my_workbook/executions/123/tasks')

        self.assertEqual(resp.status_int, 200)

        self.assertEqual(len(resp.json), 1)
        self.assertDictEqual(TASKS[0], resp.json['tasks'][0])
