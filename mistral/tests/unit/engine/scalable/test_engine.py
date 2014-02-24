# Copyright (c) 2013 Mirantis Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import mock

from mistral.db import api as db_api
from mistral.engine.actions import actions
from mistral.engine.scalable import engine
from mistral.engine import states
from mistral.tests import base


ENGINE = engine.get_engine()

WB_NAME = "my_workbook"
CONTEXT = None  # TODO(rakhmerov): Use a meaningful value.


#TODO(rakhmerov): add more tests for errors, execution stop etc.


class TestScalableEngine(base.DbTestCase):
    @mock.patch.object(engine.ScalableEngine, "_notify_task_executors",
                       mock.MagicMock(return_value=""))
    @mock.patch.object(db_api, "workbook_get",
                       mock.MagicMock(return_value={
                           'definition': base.get_resource("test_rest.yaml")
                       }))
    @mock.patch.object(actions.RestAction, "run",
                       mock.MagicMock(return_value="result"))
    def test_engine_one_task(self):
        execution = ENGINE.start_workflow_execution(WB_NAME, "create-vms",
                                                    CONTEXT)

        task = db_api.tasks_get(WB_NAME, execution['id'])[0]

        ENGINE.convey_task_result(WB_NAME, execution['id'], task['id'],
                                  states.SUCCESS, None)

        task = db_api.tasks_get(WB_NAME, execution['id'])[0]
        execution = db_api.execution_get(WB_NAME, execution['id'])

        self.assertEqual(execution['state'], states.SUCCESS)
        self.assertEqual(task['state'], states.SUCCESS)

    @mock.patch.object(engine.ScalableEngine, "_notify_task_executors",
                       mock.MagicMock(return_value=""))
    @mock.patch.object(db_api, "workbook_get",
                       mock.MagicMock(return_value={
                           'definition': base.get_resource("test_rest.yaml")
                       }))
    @mock.patch.object(actions.RestAction, "run",
                       mock.MagicMock(return_value="result"))
    def test_engine_multiple_tasks(self):
        execution = ENGINE.start_workflow_execution(WB_NAME, "backup-vms",
                                                    CONTEXT)

        tasks = db_api.tasks_get(WB_NAME, execution['id'])

        ENGINE.convey_task_result(WB_NAME, execution['id'],
                                  tasks[0]['id'],
                                  states.SUCCESS, None)

        tasks = db_api.tasks_get(WB_NAME, execution['id'])

        self.assertIsNotNone(tasks)
        self.assertEqual(2, len(tasks))
        self.assertEqual(tasks[0]['state'], states.SUCCESS)

        # Since we mocked out executor notification we expect IDLE
        # for the second task.
        self.assertEqual(tasks[1]['state'], states.IDLE)
        self.assertEqual(states.RUNNING,
                         ENGINE.get_workflow_execution_state(WB_NAME,
                                                             execution['id']))

        ENGINE.convey_task_result(WB_NAME, execution['id'],
                                  tasks[1]['id'],
                                  states.SUCCESS, None)

        tasks = db_api.tasks_get(WB_NAME, execution['id'])
        execution = db_api.execution_get(WB_NAME, execution['id'])

        self.assertEqual(execution['state'], states.SUCCESS)
        self.assertEqual(tasks[0]['state'], states.SUCCESS)
        self.assertEqual(tasks[1]['state'], states.SUCCESS)
        self.assertEqual(states.SUCCESS,
                         ENGINE.get_workflow_execution_state(WB_NAME,
                                                             execution['id']))
