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

import json

from tempest.config import cfg
from tempest import test

from mistral.tests.functional import base


CONF = cfg.CONF


class OpenStackActionsTest(base.TestCaseAdvanced):

    _version = 1

    @classmethod
    def setUpClass(cls):
        super(OpenStackActionsTest, cls).setUpClass()

        cls.identity_client = cls.mgr.identity_v3_client
        cls.images_client = cls.mgr.images_client

    @test.attr(type='openstack')
    def test_nova_actions(self):
        nova_wb = base.get_resource(
            'resources/openstack/nova_actions.yaml')
        self.client.prepare_workbook(self.workbook_name, nova_wb)

        context = {
            'server_name': 'mistral-test',
            'image_ref': self.image_ref,
            'flavor_ref': self.flavor_ref
        }

        _, execution = self.client.create_execution_wait_success(
            self.workbook_name, context, 'server_create')
        _, task_list = self.client.get_tasks_list(self.workbook_name,
                                                  execution['id'])
        final_task = base.find_items(task_list,
                                     name='wait_instance', state='SUCCESS')

        self.assertIsNotNone(final_task)
        self.assertEqual('SUCCESS', execution['state'])

        server_id = json.loads(final_task['output'])['instance_id']
        _, server = self.server_client.get_server(server_id)

        self.assertEqual('ACTIVE', server['status'])

        self.server_client.delete_server(server_id)

    @test.attr(type='openstack')
    def test_keystone_actions(self):
        keystone_wb = base.get_resource(
            'resources/openstack/keystone_actions.yaml')
        self.client.prepare_workbook(self.workbook_name,
                                     keystone_wb)
        _, execution = self.client.create_execution_wait_success(
            self.workbook_name, context={}, task='get_some_endpoint')
        _, tasks = self.client.get_tasks_list(self.workbook_name,
                                              execution['id'])
        final_task = base.find_items(tasks, name="get_some_endpoint",
                                     state='SUCCESS')

        self.assertIsNotNone(final_task)
        self.assertEqual('SUCCESS', execution['state'])

        output = json.loads(final_task['output'])
        url = output['endpoint_url']
        self.assertIn("http://", url)

    @test.attr(type='openstack')
    def test_glance_actions(self):
        glance_wb = base.get_resource(
            'resources/openstack/glance_actions.yaml')
        self.client.prepare_workbook(self.workbook_name,
                                     glance_wb)

        _, execution = self.client.create_execution_wait_success(
            self.workbook_name, context={}, task='image_list')
        _, task_list = self.client.get_tasks_list(self.workbook_name,
                                                  execution['id'])
        final_task = base.find_items(task_list,
                                     name='image_get', state='SUCCESS')

        self.assertIsNotNone(final_task)
        self.assertEqual('SUCCESS', execution['state'])

        output = json.loads(final_task['output'])
        _, image = self.images_client.get_image(output['image_id'])

        self.assertEqual(output['image_name'], image['name'])
