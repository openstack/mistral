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
from mistral.engine import engine

# TODO: later we need additional tests verifying all the errors etc.

EXECS = [
    {
        'id': "123",
        'workbook_name': "my_workbook",
        'target_task': 'my_task',
        'state': 'RUNNING'
    }
]


class TestExecutionsController(base.FunctionalTest):
    def setUp(self):
        super(TestExecutionsController, self).setUp()
        self.execution_get = db_api.execution_get
        self.executions_get = db_api.executions_get
        self.execution_update = db_api.execution_update
        self.execution_create = db_api.execution_create
        self.execution_delete = db_api.execution_delete

    def tearDown(self):
        super(TestExecutionsController, self).tearDown()
        db_api.execution_get = self.execution_get
        db_api.executions_get = self.executions_get
        db_api.execution_update = self.execution_update
        db_api.execution_create = self.execution_create
        db_api.execution_delete = self.execution_delete

    def test_get(self):
        db_api.execution_get = mock.MagicMock(return_value=EXECS[0])

        resp = self.app.get('/v1/workbooks/my_workbook/executions/123')

        self.assertEqual(resp.status_int, 200)
        self.assertDictEqual(EXECS[0], resp.json)

    def test_put(self):
        updated_exec = EXECS[0].copy()
        updated_exec['state'] = 'STOPPED'

        db_api.execution_update = mock.MagicMock(return_value=updated_exec)

        resp = self.app.put_json('/v1/workbooks/my_workbook/executions/123',
                                 dict(state='STOPPED'))

        self.assertEqual(resp.status_int, 200)
        self.assertDictEqual(updated_exec, resp.json)

    def test_post(self):
        engine.start_workflow_execution = mock.MagicMock(return_value=EXECS[0])

        resp = self.app.post_json('/v1/workbooks/my_workbook/executions',
                                  EXECS[0])

        self.assertEqual(resp.status_int, 201)
        self.assertDictEqual(EXECS[0], resp.json)

    def test_delete(self):
        db_api.execution_delete = mock.MagicMock(return_value=None)
        resp = self.app.delete('/v1/workbooks/my_workbook/executions/123')

        self.assertEqual(resp.status_int, 204)

    def test_get_all(self):
        db_api.executions_get = mock.MagicMock(return_value=EXECS)

        resp = self.app.get('/v1/workbooks/my_workbook/executions')

        self.assertEqual(resp.status_int, 200)

        self.assertEqual(len(resp.json), 1)
        self.assertDictEqual(EXECS[0], resp.json['executions'][0])
