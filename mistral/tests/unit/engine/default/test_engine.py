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

from mistral.actions import std_actions
from mistral.db import api as db_api
from mistral import engine
from mistral.engine.drivers.default import engine as concrete_engine
from mistral.engine import states
from mistral import expressions
from mistral.openstack.common import log as logging
from mistral.tests import base


LOG = logging.getLogger(__name__)

WB_NAME = "my_workbook"
CONTEXT = None  # TODO(rakhmerov): Use a meaningful value.

# Use the set_default method to set value otherwise in certain test cases
# the change in value is not permanent.
cfg.CONF.set_default('auth_enable', False, group='pecan')

# TODO(rakhmerov): add more tests for errors, execution stop etc.


@mock.patch.object(
    engine.EngineClient, 'start_workflow_execution',
    mock.MagicMock(side_effect=base.EngineTestCase.mock_start_workflow))
@mock.patch.object(
    engine.EngineClient, 'convey_task_result',
    mock.MagicMock(side_effect=base.EngineTestCase.mock_task_result))
@mock.patch.object(
    std_actions.HTTPAction, 'run',
    mock.MagicMock(return_value={'state': states.SUCCESS}))
class TestEngine(base.EngineTestCase):
    @mock.patch.object(
        concrete_engine.DefaultEngine, "_notify_task_executors",
        mock.MagicMock(return_value=""))
    @mock.patch.object(
        db_api, 'workbook_get',
        mock.MagicMock(return_value={'definition': base.get_resource(
            'control_flow/one_async_task.yaml')}))
    def test_with_one_task(self):
        execution = self.engine.start_workflow_execution(WB_NAME, "create-vms",
                                                         CONTEXT)

        task = db_api.tasks_get(workbook_name=WB_NAME,
                                execution_id=execution['id'])[0]

        self.engine.convey_task_result(task['id'], states.SUCCESS, None)

        task = db_api.tasks_get(workbook_name=WB_NAME,
                                execution_id=execution['id'])[0]
        execution = db_api.execution_get(execution['id'])

        self.assertEqual(execution['state'], states.SUCCESS)
        self.assertEqual(task['state'], states.SUCCESS)

    @mock.patch.object(
        engine.EngineClient, 'get_workflow_execution_state',
        mock.MagicMock(
            side_effect=base.EngineTestCase.mock_get_workflow_state))
    @mock.patch.object(
        concrete_engine.DefaultEngine, "_notify_task_executors",
        mock.MagicMock(return_value=""))
    @mock.patch.object(
        db_api, 'workbook_get',
        mock.MagicMock(return_value={'definition': base.get_resource(
            'control_flow/require_flow.yaml')}))
    def test_require_flow(self):
        execution = self.engine.start_workflow_execution(WB_NAME, "backup-vms",
                                                         CONTEXT)

        tasks = db_api.tasks_get(workbook_name=WB_NAME,
                                 execution_id=execution['id'])

        self.engine.convey_task_result(tasks[0]['id'],
                                       states.SUCCESS, None)

        tasks = db_api.tasks_get(workbook_name=WB_NAME,
                                 execution_id=execution['id'])

        self.assertIsNotNone(tasks)
        self.assertEqual(2, len(tasks))
        self.assertEqual(tasks[0]['state'], states.SUCCESS)

        # Since we mocked out executor notification we expect IDLE
        # for the second task.
        self.assertEqual(tasks[1]['state'], states.IDLE)
        self.assertEqual(states.RUNNING,
                         self.engine.get_workflow_execution_state(
                             WB_NAME, execution['id']))

        self.engine.convey_task_result(tasks[1]['id'],
                                       states.SUCCESS, None)

        tasks = db_api.tasks_get(workbook_name=WB_NAME,
                                 execution_id=execution['id'])
        execution = db_api.execution_get(execution['id'])

        self.assertEqual(execution['state'], states.SUCCESS)
        self.assertEqual(tasks[0]['state'], states.SUCCESS)
        self.assertEqual(tasks[1]['state'], states.SUCCESS)
        self.assertEqual(states.SUCCESS,
                         self.engine.get_workflow_execution_state(
                             WB_NAME, execution['id']))

    @mock.patch.object(
        concrete_engine.DefaultEngine, '_run_tasks',
        mock.MagicMock(side_effect=base.EngineTestCase.mock_run_tasks))
    @mock.patch.object(
        expressions, "evaluate", mock.MagicMock(side_effect=lambda x, y: x))
    @mock.patch.object(
        db_api, 'workbook_get',
        mock.MagicMock(return_value={'definition': base.get_resource(
            'control_flow/one_sync_task.yaml')}))
    def test_with_one_sync_task(self):
        execution = self.engine.start_workflow_execution(WB_NAME,
                                                         "create-vm-nova",
                                                         CONTEXT)

        task = db_api.tasks_get(workbook_name=WB_NAME,
                                execution_id=execution['id'])[0]
        execution = db_api.execution_get(execution['id'])

        self.assertEqual(execution['state'], states.SUCCESS)
        self.assertEqual(task['state'], states.SUCCESS)

    @mock.patch.object(
        concrete_engine.DefaultEngine, '_run_tasks',
        mock.MagicMock(side_effect=base.EngineTestCase.mock_run_tasks))
    @mock.patch.object(
        expressions, "evaluate", mock.MagicMock(side_effect=lambda x, y: x))
    @mock.patch.object(
        db_api, 'workbook_get',
        mock.MagicMock(return_value={'definition': base.get_resource(
            'control_flow/direct_flow.yaml')}))
    def test_direct_flow_on_success_finish(self):
        # Start workflow.
        execution = self.engine.start_workflow_execution(WB_NAME,
                                                         "start-task",
                                                         CONTEXT)
        # Only the first task is RUNNING
        tasks = db_api.tasks_get(workbook_name=WB_NAME,
                                 execution_id=execution['id'])
        self.assertEqual(len(tasks), 1)
        task = self._assert_single_item(tasks,
                                        name='start-task',
                                        state=states.RUNNING)

        # Make 'start-task' successful.
        self.engine.convey_task_result(task['id'],
                                       states.SUCCESS, None)

        tasks = db_api.tasks_get(workbook_name=WB_NAME,
                                 execution_id=execution['id'])
        self.assertEqual(len(tasks), 3)
        self._assert_single_item(tasks,
                                 name='start-task',
                                 state=states.SUCCESS)
        task1 = self._assert_single_item(tasks,
                                         name='task-one',
                                         state=states.RUNNING)
        self._assert_single_item(tasks,
                                 name='task-two',
                                 state=states.RUNNING)

        # Make 'task-one' tasks successful.
        self.engine.convey_task_result(task1['id'],
                                       states.SUCCESS, None)

        tasks = db_api.tasks_get(workbook_name=WB_NAME,
                                 execution_id=execution['id'])

        tasks_2 = self._assert_multiple_items(tasks, 2,
                                              name='task-two',
                                              state=states.RUNNING)

        # Make both 'task-two' task successful.
        self.engine.convey_task_result(tasks_2[0]['id'],
                                       states.SUCCESS, None)
        self.engine.convey_task_result(tasks_2[1]['id'],
                                       states.SUCCESS, None)

        tasks = db_api.tasks_get(workbook_name=WB_NAME,
                                 execution_id=execution['id'])
        execution = db_api.execution_get(execution['id'])

        self._assert_multiple_items(tasks, 4, state=states.SUCCESS)
        self.assertEqual(execution['state'], states.SUCCESS)

    @mock.patch.object(
        concrete_engine.DefaultEngine, '_run_tasks',
        mock.MagicMock(side_effect=base.EngineTestCase.mock_run_tasks))
    @mock.patch.object(
        expressions, "evaluate", mock.MagicMock(side_effect=lambda x, y: x))
    @mock.patch.object(
        db_api, 'workbook_get',
        mock.MagicMock(return_value={'definition': base.get_resource(
            'control_flow/direct_flow.yaml')}))
    def test_direct_flow_on_error_finish(self):
        # Start workflow.
        execution = self.engine.start_workflow_execution(WB_NAME,
                                                         "start-task",
                                                         CONTEXT)
        tasks = db_api.tasks_get(workbook_name=WB_NAME,
                                 execution_id=execution['id'])

        self.assertEqual(execution['state'], states.RUNNING)
        start_task = self._assert_single_item(tasks,
                                              name='start-task',
                                              state=states.RUNNING)

        # Make 'start-task' task fail.
        self.engine.convey_task_result(start_task['id'],
                                       states.ERROR, CONTEXT)
        tasks = db_api.tasks_get(workbook_name=WB_NAME,
                                 execution_id=execution['id'])

        self.assertEqual(len(tasks), 4)
        task3 = self._assert_single_item(tasks,
                                         name='task-three',
                                         state=states.RUNNING)
        task2 = self._assert_single_item(tasks,
                                         name='task-two',
                                         state=states.RUNNING)
        task4 = self._assert_single_item(tasks,
                                         name='task-four',
                                         state=states.RUNNING)

        # Make all running tasks successful.
        self.engine.convey_task_result(task2['id'],
                                       states.SUCCESS, None)
        self.engine.convey_task_result(task3['id'],
                                       states.SUCCESS, None)
        self.engine.convey_task_result(task4['id'],
                                       states.SUCCESS, None)

        tasks = db_api.tasks_get(workbook_name=WB_NAME,
                                 execution_id=execution['id'])
        execution = db_api.execution_get(execution['id'])

        self._assert_multiple_items(tasks, 3, state=states.SUCCESS)
        self._assert_single_item(tasks, state=states.ERROR)
        self.assertEqual(execution['state'], states.SUCCESS)

    @mock.patch.object(
        concrete_engine.DefaultEngine, "_notify_task_executors",
        mock.MagicMock(return_value=""))
    @mock.patch.object(
        db_api, 'workbook_get',
        mock.MagicMock(return_value={'definition': base.get_resource(
            'control_flow/no_namespaces.yaml')}))
    @mock.patch.object(
        concrete_engine.DefaultEngine, '_run_tasks',
        mock.MagicMock(side_effect=base.EngineTestCase.mock_run_tasks))
    def test_engine_with_no_namespaces(self):
        execution = self.engine.start_workflow_execution(WB_NAME, "task1", {})

        tasks = db_api.tasks_get(workbook_name=WB_NAME,
                                 execution_id=execution['id'])
        execution = db_api.execution_get(execution['id'])

        self.assertIsNotNone(tasks)
        self.assertEqual(1, len(tasks))
        self.assertEqual(tasks[0]['state'], states.SUCCESS)
        self.assertEqual(execution['state'], states.SUCCESS)

    @mock.patch.object(
        db_api, 'workbook_get',
        mock.MagicMock(return_value={'definition': base.get_resource(
            'control_flow/one_std_task.yaml')}))
    @mock.patch.object(
        concrete_engine.DefaultEngine, '_run_tasks',
        mock.MagicMock(side_effect=base.EngineTestCase.mock_run_tasks))
    def test_engine_task_std_action_with_namespaces(self):
        execution = self.engine.start_workflow_execution(WB_NAME,
                                                         "std_http_task", {})

        tasks = db_api.tasks_get(workbook_name=WB_NAME,
                                 execution_id=execution['id'])
        execution = db_api.execution_get(execution['id'])

        self.assertEqual(1, len(tasks))
        self.assertEqual(states.SUCCESS, tasks[0]['state'])
        self.assertEqual(states.SUCCESS, execution['state'])
