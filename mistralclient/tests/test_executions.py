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

# TODO: Later we need additional tests verifying all the errors etc.

EXECS = [
    {
        'id': "123",
        'workbook_name': "my_workbook",
        'target_task': 'my_task',
        'state': 'RUNNING',
        'context': """
            {
                "person": {
                    "first_name": "John",
                    "last_name": "Doe"
                }
            }
        """
    }
]


class TestExecutions(base.BaseClientTest):

    def test_create(self):
        self.mock_http_post(json=EXECS[0])

        ex = self.executions.create(EXECS[0]['workbook_name'],
                                    EXECS[0]['target_task'])

        self.assertIsNotNone(ex)
        self.assertEqual(EXECS[0]['id'], ex.id)
        self.assertEqual(EXECS[0]['workbook_name'], ex.workbook_name)
        self.assertEqual(EXECS[0]['target_task'], ex.target_task)
        self.assertEqual(EXECS[0]['state'], ex.state)
        self.assertEqual(EXECS[0]['context'], ex.context)

    def test_update(self):
        self.mock_http_put(json=EXECS[0])

        ex = self.executions.update(EXECS[0]['workbook_name'],
                                    EXECS[0]['id'],
                                    EXECS[0]['state'])

        self.assertIsNotNone(ex)
        self.assertEqual(EXECS[0]['id'], ex.id)
        self.assertEqual(EXECS[0]['workbook_name'], ex.workbook_name)
        self.assertEqual(EXECS[0]['target_task'], ex.target_task)
        self.assertEqual(EXECS[0]['state'], ex.state)
        self.assertEqual(EXECS[0]['context'], ex.context)

    def test_list(self):
        self.mock_http_get(json={'executions': EXECS})

        executions = self.executions.list(EXECS[0]['workbook_name'])

        self.assertEqual(1, len(executions))

        ex = executions[0]

        self.assertEqual(EXECS[0]['id'], ex.id)
        self.assertEqual(EXECS[0]['workbook_name'], ex.workbook_name)
        self.assertEqual(EXECS[0]['target_task'], ex.target_task)
        self.assertEqual(EXECS[0]['state'], ex.state)
        self.assertEqual(EXECS[0]['context'], ex.context)

    def test_get(self):
        self.mock_http_get(json=EXECS[0])

        ex = self.executions.get(EXECS[0]['workbook_name'], EXECS[0]['id'])

        self.assertEqual(EXECS[0]['id'], ex.id)
        self.assertEqual(EXECS[0]['workbook_name'], ex.workbook_name)
        self.assertEqual(EXECS[0]['target_task'], ex.target_task)
        self.assertEqual(EXECS[0]['state'], ex.state)
        self.assertEqual(EXECS[0]['context'], ex.context)

    def test_delete(self):
        self.mock_http_delete(status_code=204)

        # Just make sure it doesn't throw any exceptions.
        self.executions.delete(EXECS[0]['workbook_name'], EXECS[0]['id'])
