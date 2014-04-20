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

from oslo.config import cfg

from mistral.tests import base
from mistral.openstack.common import log as logging
from mistral.db import api as db_api
from mistral.actions import std_actions
from mistral import expressions
from mistral.engine.scalable import engine
from mistral.engine import states
from mistral.engine import client


LOG = logging.getLogger(__name__)

WB_NAME = "my_workbook"
CONTEXT = None  # TODO(rakhmerov): Use a meaningful value.

# Use the set_default method to set value otherwise in certain test cases
# the change in value is not permanent.
cfg.CONF.set_default('auth_enable', False, group='pecan')

#TODO(rakhmerov): add more tests for errors, execution stop etc.


@mock.patch.object(
    client.EngineClient, 'start_workflow_execution',
    mock.MagicMock(side_effect=base.EngineTestCase.mock_start_workflow))
@mock.patch.object(
    client.EngineClient, 'convey_task_result',
    mock.MagicMock(side_effect=base.EngineTestCase.mock_task_result))
@mock.patch.object(
    db_api, 'workbook_get',
    mock.MagicMock(
        return_value={'definition': base.get_resource('test_rest.yaml')}))
@mock.patch.object(
    std_actions.HTTPAction, 'run',
    mock.MagicMock(return_value={'state': states.SUCCESS}))
class TestScalableEngine(base.EngineTestCase):
    @mock.patch.object(
        engine.ScalableEngine, "_notify_task_executors",
        mock.MagicMock(return_value=""))
    def test_engine_one_task(self):
        execution = self.engine.start_workflow_execution(WB_NAME, "create-vms",
                                                         CONTEXT)

        task = db_api.tasks_get(WB_NAME, execution['id'])[0]

        self.engine.convey_task_result(WB_NAME, execution['id'], task['id'],
                                       states.SUCCESS, None)

        task = db_api.tasks_get(WB_NAME, execution['id'])[0]
        execution = db_api.execution_get(WB_NAME, execution['id'])

        self.assertEqual(execution['state'], states.SUCCESS)
        self.assertEqual(task['state'], states.SUCCESS)

    @mock.patch.object(
        client.EngineClient, 'get_workflow_execution_state',
        mock.MagicMock(
            side_effect=base.EngineTestCase.mock_get_workflow_state))
    @mock.patch.object(
        engine.ScalableEngine, "_notify_task_executors",
        mock.MagicMock(return_value=""))
    def test_engine_multiple_tasks(self):
        execution = self.engine.start_workflow_execution(WB_NAME, "backup-vms",
                                                         CONTEXT)

        tasks = db_api.tasks_get(WB_NAME, execution['id'])

        self.engine.convey_task_result(WB_NAME, execution['id'],
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
                         self.engine.get_workflow_execution_state(
                             WB_NAME, execution['id']))

        self.engine.convey_task_result(WB_NAME, execution['id'],
                                       tasks[1]['id'],
                                       states.SUCCESS, None)

        tasks = db_api.tasks_get(WB_NAME, execution['id'])
        execution = db_api.execution_get(WB_NAME, execution['id'])

        self.assertEqual(execution['state'], states.SUCCESS)
        self.assertEqual(tasks[0]['state'], states.SUCCESS)
        self.assertEqual(tasks[1]['state'], states.SUCCESS)
        self.assertEqual(states.SUCCESS,
                         self.engine.get_workflow_execution_state(
                             WB_NAME, execution['id']))

    @mock.patch.object(
        engine.ScalableEngine, '_run_tasks',
        mock.MagicMock(side_effect=base.EngineTestCase.mock_run_tasks))
    @mock.patch.object(
        states, "get_state_by_http_status_code",
        mock.MagicMock(return_value=states.SUCCESS))
    @mock.patch.object(
        expressions, "evaluate", mock.MagicMock(side_effect=lambda x, y: x))
    def test_engine_sync_task(self):
        execution = self.engine.start_workflow_execution(WB_NAME,
                                                         "create-vm-nova",
                                                         CONTEXT)

        task = db_api.tasks_get(WB_NAME, execution['id'])[0]
        execution = db_api.execution_get(WB_NAME, execution['id'])

        self.assertEqual(execution['state'], states.SUCCESS)
        self.assertEqual(task['state'], states.SUCCESS)

    @mock.patch.object(
        engine.ScalableEngine, '_run_tasks',
        mock.MagicMock(side_effect=base.EngineTestCase.mock_run_tasks))
    @mock.patch.object(
        expressions, "evaluate", mock.MagicMock(side_effect=lambda x, y: x))
    def test_engine_tasks_on_success_finish(self):
        # Start workflow.
        execution = self.engine.start_workflow_execution(WB_NAME,
                                                         "test_subsequent",
                                                         CONTEXT)
        tasks = db_api.tasks_get(WB_NAME, execution['id'])

        self.assertEqual(len(tasks), 1)

        execution = db_api.execution_get(WB_NAME, execution['id'])

        task = self._assert_single_item(tasks, name='test_subsequent')

        # Make 'test_subsequent' task successful.
        self.engine.convey_task_result(WB_NAME, execution['id'],
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
        self.engine.convey_task_result(WB_NAME, execution['id'],
                                       tasks2[0]['id'],
                                       states.SUCCESS, None)
        self.engine.convey_task_result(WB_NAME, execution['id'],
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
        self.engine.convey_task_result(WB_NAME, execution['id'],
                                       task['id'],
                                       states.SUCCESS, None)

        execution = db_api.execution_get(WB_NAME, execution['id'])
        tasks = db_api.tasks_get(WB_NAME, execution['id'])

        self.assertEqual(execution['state'], states.SUCCESS)
        self._assert_multiple_items(tasks, 4, state=states.SUCCESS)

    @mock.patch.object(
        engine.ScalableEngine, '_run_tasks',
        mock.MagicMock(side_effect=base.EngineTestCase.mock_run_tasks))
    @mock.patch.object(
        expressions, "evaluate", mock.MagicMock(side_effect=lambda x, y: x))
    def test_engine_tasks_on_error_finish(self):
        # Start workflow.
        execution = self.engine.start_workflow_execution(WB_NAME,
                                                         "test_subsequent",
                                                         CONTEXT)

        tasks = db_api.tasks_get(WB_NAME, execution['id'])
        execution = db_api.execution_get(WB_NAME, execution['id'])

        # Make 'test_subsequent' task successful.
        self.engine.convey_task_result(WB_NAME, execution['id'],
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
        self.engine.convey_task_result(WB_NAME, execution['id'],
                                       tasks2[0]['id'],
                                       states.SUCCESS, None)
        self.engine.convey_task_result(WB_NAME, execution['id'],
                                       tasks2[1]['id'],
                                       states.SUCCESS, None)
        self.engine.convey_task_result(WB_NAME, execution['id'],
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
        self.engine.convey_task_result(WB_NAME, execution['id'],
                                       task1['id'],
                                       states.SUCCESS, None)
        self.engine.convey_task_result(WB_NAME, execution['id'],
                                       task2['id'],
                                       states.SUCCESS, None)

        execution = db_api.execution_get(WB_NAME, execution['id'])

        self.assertEqual(execution['state'], states.SUCCESS)

        tasks = db_api.tasks_get(WB_NAME, execution['id'])

        self._assert_single_item(tasks, state=states.ERROR)
        self._assert_multiple_items(tasks, 5, state=states.SUCCESS)
