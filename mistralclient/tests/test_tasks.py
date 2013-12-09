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

from mistralclient.tests import base

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


class TestTasks(base.BaseClientTest):
    def test_update(self):
        self.mock_http_put(json=TASKS[0])

        task = self.tasks.update(TASKS[0]['workbook_name'],
                                 TASKS[0]['execution_id'],
                                 TASKS[0]['id'],
                                 TASKS[0]['state'])

        self.assertIsNotNone(task)
        self.assertEqual(TASKS[0]['id'], task.id)
        self.assertEqual(TASKS[0]['workbook_name'], task.workbook_name)
        self.assertEqual(TASKS[0]['execution_id'], task.execution_id)
        self.assertEqual(TASKS[0]['description'], task.description)
        self.assertEqual(TASKS[0]['action'], task.action)
        self.assertEqual(TASKS[0]['state'], task.state)
        self.assertEqual(TASKS[0]['tags'], task.tags)

    def test_list(self):
        self.mock_http_get(json={'tasks': TASKS})

        tasks = self.tasks.list(TASKS[0]['workbook_name'],
                                TASKS[0]['execution_id'])

        self.assertEqual(1, len(tasks))

        task = tasks[0]

        self.assertEqual(TASKS[0]['id'], task.id)
        self.assertEqual(TASKS[0]['workbook_name'], task.workbook_name)
        self.assertEqual(TASKS[0]['execution_id'], task.execution_id)
        self.assertEqual(TASKS[0]['description'], task.description)
        self.assertEqual(TASKS[0]['action'], task.action)
        self.assertEqual(TASKS[0]['state'], task.state)
        self.assertEqual(TASKS[0]['tags'], task.tags)

    def test_get(self):
        self.mock_http_get(json=TASKS[0])

        task = self.tasks.get(TASKS[0]['workbook_name'],
                              TASKS[0]['execution_id'],
                              TASKS[0]['id'])

        self.assertEqual(TASKS[0]['id'], task.id)
        self.assertEqual(TASKS[0]['workbook_name'], task.workbook_name)
        self.assertEqual(TASKS[0]['execution_id'], task.execution_id)
        self.assertEqual(TASKS[0]['description'], task.description)
        self.assertEqual(TASKS[0]['action'], task.action)
        self.assertEqual(TASKS[0]['state'], task.state)
        self.assertEqual(TASKS[0]['tags'], task.tags)
