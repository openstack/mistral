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
from mistral.engine.local import engine
from mistral.engine import states
from mistral.tests import base


ENGINE = engine.get_engine()

WB_NAME = "my_workbook"
CONTEXT = None  # TODO(rakhmerov): Use a meaningful value.

#TODO(rakhmerov): add more tests for errors, execution stop etc.


def print_tasks(tasks):
    for t in tasks:
        print t['name'], t['state']


class TestLocalEngine(base.DbTestCase):
    @mock.patch.object(db_api, "workbook_get",
                       mock.MagicMock(return_value={
                           'definition': base.get_resource("test_rest.yaml")
                       }))
    @mock.patch.object(actions.RestAction, "run",
                       mock.MagicMock(return_value={'state': states.RUNNING}))
    def test_engine_one_task(self):
        # Start workflow.
        execution = ENGINE.start_workflow_execution(WB_NAME, "create-vms",
                                                    CONTEXT)

        tasks = db_api.tasks_get(WB_NAME, execution['id'])

        self.assertEqual(1, len(tasks))
        self._assert_single_item(tasks,
                                 name='create-vms',
                                 state=states.RUNNING)

        # Make 'create-vms' task successful.
        ENGINE.convey_task_result(WB_NAME, execution['id'], tasks[0]['id'],
                                  states.SUCCESS, None)

        execution = db_api.execution_get(WB_NAME, execution['id'])

        self.assertEqual(execution['state'], states.SUCCESS)

        tasks = db_api.tasks_get(WB_NAME, execution['id'])

        self.assertEqual(1, len(tasks))
        self._assert_single_item(tasks,
                                 name='create-vms',
                                 state=states.SUCCESS)

    @mock.patch.object(db_api, "workbook_get",
                       mock.MagicMock(return_value={
                           'definition': base.get_resource("test_rest.yaml")
                       }))
    @mock.patch.object(actions.RestAction, "run",
                       mock.MagicMock(return_value={'state': states.RUNNING}))
    def test_engine_multiple_tasks(self):
        # Start workflow.
        execution = ENGINE.start_workflow_execution(WB_NAME, "backup-vms",
                                                    CONTEXT)

        tasks = db_api.tasks_get(WB_NAME, execution['id'])

        task = self._assert_single_item(tasks,
                                        name='create-vms',
                                        state=states.RUNNING)

        # Make 'create-vms' task successful.
        ENGINE.convey_task_result(WB_NAME, execution['id'],
                                  task['id'],
                                  states.SUCCESS, None)

        tasks = db_api.tasks_get(WB_NAME, execution['id'])

        self.assertEqual(2, len(tasks))

        self._assert_single_item(tasks,
                                 name='create-vms',
                                 state=states.SUCCESS)
        self._assert_single_item(tasks,
                                 name='backup-vms',
                                 state=states.RUNNING)

        self.assertEqual(states.RUNNING,
                         ENGINE.get_workflow_execution_state(WB_NAME,
                                                             execution['id']))

        task = self._assert_single_item(tasks, name='backup-vms')

        # Make 'backup-vms' task successful.
        ENGINE.convey_task_result(WB_NAME, execution['id'],
                                  task['id'],
                                  states.SUCCESS, None)

        execution = db_api.execution_get(WB_NAME, execution['id'])

        self.assertEqual(execution['state'], states.SUCCESS)

        tasks = db_api.tasks_get(WB_NAME, execution['id'])

        self._assert_single_item(tasks,
                                 name='create-vms',
                                 state=states.SUCCESS)
        self._assert_single_item(tasks,
                                 name='backup-vms',
                                 state=states.SUCCESS)

        self.assertEqual(states.SUCCESS,
                         ENGINE.get_workflow_execution_state(WB_NAME,
                                                             execution['id']))

    @mock.patch.object(actions.RestAction, "run",
                       mock.MagicMock(return_value={'state': states.SUCCESS}))
    @mock.patch.object(db_api, "workbook_get",
                       mock.MagicMock(return_value={
                           'definition': base.get_resource("test_rest.yaml")
                       }))
    @mock.patch.object(states, "get_state_by_http_status_code",
                       mock.MagicMock(return_value=states.SUCCESS))
    def test_engine_sync_task(self):
        execution = ENGINE.start_workflow_execution(WB_NAME, "create-vm-nova",
                                                    CONTEXT)

        task = db_api.tasks_get(WB_NAME, execution['id'])[0]
        execution = db_api.execution_get(WB_NAME, execution['id'])

        self.assertEqual(execution['state'], states.SUCCESS)
        self.assertEqual(task['state'], states.SUCCESS)

    @mock.patch.object(db_api, "workbook_get",
                       mock.MagicMock(return_value={
                           'definition': base.get_resource("test_rest.yaml")
                       }))
    @mock.patch.object(actions.RestAction, "run",
                       mock.MagicMock(return_value={'state': states.SUCCESS}))
    def test_engine_tasks_on_success_finish(self):
        # Start workflow.
        execution = ENGINE.start_workflow_execution(WB_NAME, "test_subsequent",
                                                    CONTEXT)
        tasks = db_api.tasks_get(WB_NAME, execution['id'])

        self.assertEqual(len(tasks), 1)

        execution = db_api.execution_get(WB_NAME, execution['id'])

        task = self._assert_single_item(tasks, name='test_subsequent')

        # Make 'test_subsequent' task successful.
        ENGINE.convey_task_result(WB_NAME, execution['id'],
                                  task['id'],
                                  states.SUCCESS, None)

        tasks = db_api.tasks_get(WB_NAME, execution['id'])

        self.assertEqual(len(tasks), 4)

        self._assert_single_item(tasks,
                                 name='test_subsequent',
                                 state=states.SUCCESS)
        self._assert_single_item(tasks,
                                 name='attach-volumes',
                                 state=states.IDLE)

        tasks2 = self._assert_multiple_items(tasks, 2,
                                             name='create-vms',
                                             state=states.RUNNING)

        # Make 2 'create-vms' tasks successful.
        ENGINE.convey_task_result(WB_NAME, execution['id'],
                                  tasks2[0]['id'],
                                  states.SUCCESS, None)
        ENGINE.convey_task_result(WB_NAME, execution['id'],
                                  tasks2[1]['id'],
                                  states.SUCCESS, None)

        tasks = db_api.tasks_get(WB_NAME, execution['id'])

        self._assert_multiple_items(tasks, 2,
                                    name='create-vms',
                                    state=states.SUCCESS)
        task = self._assert_single_item(tasks,
                                        name='attach-volumes',
                                        state=states.RUNNING)

        # Make 'attach-volumes' task successful.
        ENGINE.convey_task_result(WB_NAME, execution['id'],
                                  task['id'],
                                  states.SUCCESS, None)

        execution = db_api.execution_get(WB_NAME, execution['id'])
        tasks = db_api.tasks_get(WB_NAME, execution['id'])

        self.assertEqual(execution['state'], states.SUCCESS)
        self._assert_multiple_items(tasks, 4, state=states.SUCCESS)

    @mock.patch.object(db_api, "workbook_get",
                       mock.MagicMock(return_value={
                           'definition': base.get_resource("test_rest.yaml")
                       }))
    @mock.patch.object(actions.RestAction, "run",
                       mock.MagicMock(return_value={'state': states.SUCCESS}))
    def test_engine_tasks_on_error_finish(self):
        # Start workflow.
        execution = ENGINE.start_workflow_execution(WB_NAME, "test_subsequent",
                                                    CONTEXT)

        tasks = db_api.tasks_get(WB_NAME, execution['id'])
        execution = db_api.execution_get(WB_NAME, execution['id'])

        # Make 'test_subsequent' task successful.
        ENGINE.convey_task_result(WB_NAME, execution['id'],
                                  tasks[0]['id'],
                                  states.ERROR, None)

        tasks = db_api.tasks_get(WB_NAME, execution['id'])

        self.assertEqual(len(tasks), 6)

        self._assert_single_item(tasks,
                                 name='backup-vms',
                                 state=states.IDLE)
        self._assert_single_item(tasks,
                                 name='test_subsequent',
                                 state=states.ERROR)
        self._assert_single_item(tasks,
                                 name='attach-volumes',
                                 state=states.IDLE)

        tasks2 = self._assert_multiple_items(tasks, 3,
                                             name='create-vms',
                                             state=states.RUNNING)

        # Make 'create-vms' tasks successful.
        ENGINE.convey_task_result(WB_NAME, execution['id'],
                                  tasks2[0]['id'],
                                  states.SUCCESS, None)
        ENGINE.convey_task_result(WB_NAME, execution['id'],
                                  tasks2[1]['id'],
                                  states.SUCCESS, None)
        ENGINE.convey_task_result(WB_NAME, execution['id'],
                                  tasks2[2]['id'],
                                  states.SUCCESS, None)

        tasks = db_api.tasks_get(WB_NAME, execution['id'])

        task1 = self._assert_single_item(tasks,
                                         name='backup-vms',
                                         state=states.RUNNING)
        task2 = self._assert_single_item(tasks,
                                         name='attach-volumes',
                                         state=states.RUNNING)

        self._assert_multiple_items(tasks, 3,
                                    name='create-vms',
                                    state=states.SUCCESS)

        # Make tasks 'backup-vms' and 'attach-volumes' successful.
        ENGINE.convey_task_result(WB_NAME, execution['id'],
                                  task1['id'],
                                  states.SUCCESS, None)
        ENGINE.convey_task_result(WB_NAME, execution['id'],
                                  task2['id'],
                                  states.SUCCESS, None)

        execution = db_api.execution_get(WB_NAME, execution['id'])

        self.assertEqual(execution['state'], states.SUCCESS)

        tasks = db_api.tasks_get(WB_NAME, execution['id'])

        self._assert_single_item(tasks, state=states.ERROR)
        self._assert_multiple_items(tasks, 5, state=states.SUCCESS)
