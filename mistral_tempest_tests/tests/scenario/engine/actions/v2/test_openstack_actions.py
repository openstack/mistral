# Copyright 2015 - Mirantis, Inc.
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

from tempest.lib import decorators
from tempest import test

from mistral_tempest_tests.tests import base


class OpenStackActionsTestsV2(base.TestCase):

    _service = 'workflowv2'

    # TODO(akuznetsova): add checks for task result after task_output
    # TODO(akuznetsova): refactoring will be finished

    @classmethod
    def resource_setup(cls):
        super(OpenStackActionsTestsV2, cls).resource_setup()

        _, cls.wb = cls.client.create_workbook(
            'openstack/action_collection_wb.yaml')

    @test.attr(type='openstack')
    @decorators.idempotent_id('9a999fc2-a089-4375-bc69-e1ed85b17a82')
    def test_nova_actions(self):
        wf_name = self.wb['name'] + '.nova'
        _, execution = self.client.create_execution(wf_name)
        self.client.wait_execution_success(execution)
        executed_task = self.client.get_wf_tasks(wf_name)[-1]

        self.assertEqual('SUCCESS', executed_task['state'])

    @test.attr(type='openstack')
    @decorators.idempotent_id('81bdc1c9-cd9a-4c97-b8ce-e44f5211eace')
    def test_keystone_actions(self):
        wf_name = self.wb['name'] + '.keystone'
        _, execution = self.admin_client.create_execution(wf_name)
        self.admin_client.wait_execution_success(execution)
        executed_task = self.admin_client.get_wf_tasks(wf_name)[-1]

        self.assertEqual('SUCCESS', executed_task['state'])

    @test.attr(type='openstack')
    @decorators.idempotent_id('fde681b8-3e1b-4172-a4b8-2fcac1f070d9')
    def test_heat_actions(self):
        wf_name = self.wb['name'] + '.heat'
        _, execution = self.client.create_execution(wf_name)
        self.client.wait_execution_success(execution)
        executed_task = self.client.get_wf_tasks(wf_name)[-1]

        self.assertEqual('SUCCESS', executed_task['state'])

    @test.attr(type='openstack')
    @decorators.idempotent_id('5981360d-f336-45ca-9d38-799c7a8ade26')
    def test_glance_actions(self):
        wf_name = self.wb['name'] + '.glance'
        _, execution = self.client.create_execution(wf_name)
        self.client.wait_execution_success(execution)
        executed_task = self.client.get_wf_tasks(wf_name)[-1]

        self.assertEqual('SUCCESS', executed_task['state'])

    @test.attr(type='openstack')
    @decorators.idempotent_id('a1f71a72-3681-4d32-aad9-117068717b33')
    def test_cinder_actions(self):
        wf_name = self.wb['name'] + '.cinder'
        _, execution = self.client.create_execution(wf_name)
        self.client.wait_execution_success(execution)
        executed_task = self.client.get_wf_tasks(wf_name)[-1]

        self.assertEqual('SUCCESS', executed_task['state'])

    @test.attr(type='openstack')
    @decorators.idempotent_id('586dd973-fc65-40e2-9a85-31418b22473a')
    def test_neutron_actions(self):
        wf_name = self.wb['name'] + '.neutron'
        _, execution = self.client.create_execution(wf_name)
        self.client.wait_execution_success(execution)
        executed_task = self.client.get_wf_tasks(wf_name)[-1]

        self.assertEqual('SUCCESS', executed_task['state'])
