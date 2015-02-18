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

from tempest import test
from tempest_lib import decorators

from mistral.tests.functional import base


class OpenStackActionsTestsV2(base.TestCase):

    _service = 'workflowv2'

    # TODO(akuznetsova): add checks for task result after task_output
    # TODO(akuznetsova): refactoring will be finished

    @classmethod
    def setUpClass(cls):
        super(OpenStackActionsTestsV2, cls).setUpClass()

        _, cls.wb = cls.client.create_workbook(
            'openstack/action_collection_wb.yaml')

    @test.attr(type='openstack')
    def test_nova_actions(self):
        wf_name = self.wb['name'] + '.nova'
        _, execution = self.client.create_execution(wf_name)
        self.client.wait_execution_success(execution)
        executed_task = self.client.get_wf_tasks(wf_name)[-1]

        self.assertEqual(executed_task['state'], 'SUCCESS')

    @test.attr(type='openstack')
    def test_keystone_actions(self):
        wf_name = self.wb['name'] + '.keystone'
        _, execution = self.client.create_execution(wf_name)
        self.client.wait_execution_success(execution)
        executed_task = self.client.get_wf_tasks(wf_name)[-1]

        self.assertEqual(executed_task['state'], 'SUCCESS')

    @test.attr(type='openstack')
    def test_heat_actions(self):
        wf_name = self.wb['name'] + '.heat'
        _, execution = self.client.create_execution(wf_name)
        self.client.wait_execution_success(execution)
        executed_task = self.client.get_wf_tasks(wf_name)[-1]

        self.assertEqual(executed_task['state'], 'SUCCESS')

    @test.attr(type='openstack')
    def test_glance_actions(self):
        wf_name = self.wb['name'] + '.glance'
        _, execution = self.client.create_execution(wf_name)
        self.client.wait_execution_success(execution)
        executed_task = self.client.get_wf_tasks(wf_name)[-1]

        self.assertEqual(executed_task['state'], 'SUCCESS')

    @test.attr(type='openstack')
    def test_cinder_actions(self):
        wf_name = self.wb['name'] + '.cinder'
        _, execution = self.client.create_execution(wf_name)
        self.client.wait_execution_success(execution)
        executed_task = self.client.get_wf_tasks(wf_name)[-1]

        self.assertEqual(executed_task['state'], 'SUCCESS')

    @decorators.skip_because(bug='1422725')
    @test.attr(type='openstack')
    def test_neutron_actions(self):
        wf_name = self.wb['name'] + '.neutron'
        _, execution = self.client.create_execution(wf_name)
        self.client.wait_execution_success(execution)
        executed_task = self.client.get_wf_tasks(wf_name)[-1]

        self.assertEqual(executed_task['state'], 'SUCCESS')
