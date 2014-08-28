# Copyright 2014 - Mirantis, Inc.
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
from oslo.config import cfg

from mistral.actions.openstack import actions
from mistral import context as auth_context
from mistral.db.v1 import api as db_api
from mistral import engine
from mistral.engine.drivers.default import engine as concrete_engine
from mistral.engine.drivers.default import executor
from mistral.engine import states
from mistral.openstack.common import log as logging
from mistral.tests import base


LOG = logging.getLogger(__name__)

# Use the set_default method to set value otherwise in certain test cases
# the change in value is not permanent.
cfg.CONF.set_default('auth_enable', False, group='pecan')


def create_workbook(definition_path):
    return db_api.workbook_create({
        'name': 'my_workbook',
        'definition': base.get_resource(definition_path)
    })


@mock.patch.object(
    engine.EngineClient, 'start_workflow_execution',
    mock.MagicMock(side_effect=base.EngineTestCase.mock_start_workflow))
@mock.patch.object(
    engine.EngineClient, 'convey_task_result',
    mock.MagicMock(side_effect=base.EngineTestCase.mock_task_result))
@mock.patch.object(
    concrete_engine.DefaultEngine, '_run_task',
    mock.MagicMock(side_effect=base.EngineTestCase.mock_run_task))
class OpenStackActionsEngineTest(base.EngineTestCase):
    @mock.patch.object(actions.GlanceAction, 'run',
                       mock.Mock(return_value="images"))
    def test_glance_action(self):
        context = {}
        wb = create_workbook('openstack/glance.yaml')
        task_name = 'glance_image_list'
        execution = self.engine.start_workflow_execution(wb['name'],
                                                         task_name,
                                                         context)

        # We have to reread execution to get its latest version.
        execution = db_api.execution_get(execution['id'])

        self.assertEqual(states.SUCCESS, execution['state'])

        tasks = db_api.tasks_get(workbook_name=wb['name'],
                                 execution_id=execution['id'])

        self.assertEqual(1, len(tasks))

        task = self._assert_single_item(tasks, name=task_name)

        self.assertEqual(states.SUCCESS, task['state'])
        self.assertEqual("images", task['output']['task'][task_name])

    @mock.patch.object(actions.KeystoneAction, 'run',
                       mock.Mock(return_value="users"))
    def test_keystone_action(self):
        context = {}
        wb = create_workbook('openstack/keystone.yaml')
        task_name = 'keystone_user_list'
        execution = self.engine.start_workflow_execution(wb['name'],
                                                         task_name,
                                                         context)

        # We have to reread execution to get its latest version.
        execution = db_api.execution_get(execution['id'])

        self.assertEqual(states.SUCCESS, execution['state'])

        tasks = db_api.tasks_get(workbook_name=wb['name'],
                                 execution_id=execution['id'])

        self.assertEqual(1, len(tasks))

        task = self._assert_single_item(tasks, name=task_name)

        self.assertEqual(states.SUCCESS, task['state'])
        self.assertEqual("users", task['output']['task'][task_name])

    @mock.patch.object(actions.NovaAction, 'run',
                       mock.Mock(return_value="servers"))
    @mock.patch.object(executor.DefaultExecutor, "handle_task",
                       mock.MagicMock())
    def test_nova_action(self):
        context = {}
        task_name = 'nova_server_findall'
        task_params = {'status': 'ACTIVE', 'tenant_id': '8e44eb2ce32'}
        wb = create_workbook('openstack/nova.yaml')
        execution = self.engine.start_workflow_execution(wb['name'],
                                                         task_name,
                                                         context)

        tasks = db_api.tasks_get(workbook_name=wb['name'],
                                 execution_id=execution['id'])

        self.assertEqual(1, len(tasks))
        task = self._assert_single_item(tasks, name=task_name)

        executor.DefaultExecutor.handle_task.assert_called_once_with(
            auth_context.ctx(),
            params=task_params,
            task_id=task['id'],
            action_name="nova.servers_findall"
        )

        self.engine.convey_task_result(task['id'],
                                       states.SUCCESS,
                                       "servers")

        # We have to reread execution to get its latest version.
        execution = db_api.execution_get(execution['id'])

        self.assertEqual(states.SUCCESS, execution['state'])

        tasks = db_api.tasks_get(workbook_name=wb['name'],
                                 execution_id=execution['id'])

        self.assertEqual(1, len(tasks))

        task = self._assert_single_item(tasks, name=task_name)

        self.assertEqual(states.SUCCESS, task['state'])
        self.assertEqual("servers", task['output']['task'][task_name])

    @mock.patch.object(actions.HeatAction, 'run',
                       mock.Mock(return_value="stacks"))
    def test_heat_action(self):
        context = {}
        wb = create_workbook('openstack/heat.yaml')
        task_name = 'heat_stack_list'
        execution = self.engine.start_workflow_execution(wb['name'],
                                                         task_name,
                                                         context)

        # We have to reread execution to get its latest version.
        execution = db_api.execution_get(execution['id'])

        self.assertEqual(states.SUCCESS, execution['state'])

        tasks = db_api.tasks_get(workbook_name=wb['name'],
                                 execution_id=execution['id'])

        self.assertEqual(1, len(tasks))

        task = self._assert_single_item(tasks, name=task_name)

        self.assertEqual(states.SUCCESS, task['state'])
        self.assertEqual("stacks", task['output']['task'][task_name])

    @mock.patch.object(actions.NeutronAction, 'run',
                       mock.Mock(return_value="networks"))
    def test_neutron_action(self):
        context = {}
        wb = create_workbook('openstack_tasks/neutron.yaml')
        task_name = 'neutron_list_networks'
        execution = self.engine.start_workflow_execution(wb['name'],
                                                         task_name,
                                                         context)

        # We have to reread execution to get its latest version.
        execution = db_api.execution_get(execution['id'])

        self.assertEqual(states.SUCCESS, execution['state'])

        tasks = db_api.tasks_get(workbook_name=wb['name'],
                                 execution_id=execution['id'])

        self.assertEqual(1, len(tasks))

        task = self._assert_single_item(tasks, name=task_name)

        self.assertEqual(states.SUCCESS, task['state'])
        self.assertEqual("networks", task['output']['task'][task_name])
