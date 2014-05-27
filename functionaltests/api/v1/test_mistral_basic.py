

# Copyright 2013 Mirantis, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import json
import time

from tempest import exceptions
from tempest import test

from functionaltests.api import base


class SanityTests(base.TestCase):

    @test.attr(type='smoke')
    def test_get_list_obj(self):
        resp, _ = self.client.get_list_obj('')
        self.assertEqual(200, resp.status)

    @test.attr(type='smoke')
    def test_get_list_workbooks(self):
        resp, body = self.client.get_list_obj('workbooks')

        self.assertEqual(200, resp.status)
        self.assertEqual([], body['workbooks'])

    @test.attr(type='smoke')
    def test_get_workbook(self):
        self.client.create_obj('workbooks', 'test')
        self.obj.append(['workbooks', 'test'])
        resp, body = self.client.get_list_obj('workbooks/test')

        self.assertEqual(200, resp.status)
        self.assertEqual('test', body['name'])

    @test.attr(type='smoke')
    def test_get_executions(self):
        self.client.create_obj('workbooks', 'test')
        self.obj.append(['workbooks', 'test'])
        resp, body = self.client.get_list_obj('workbooks/test/executions')

        self.assertEqual(200, resp.status)
        self.assertEqual([], body['executions'])

    @test.attr(type='smoke')
    def test_create_and_delete_workbook(self):
        resp, body = self.client.create_obj('workbooks', 'test')
        self.obj.append(['workbooks', 'test'])

        self.assertEqual(201, resp.status)
        self.assertEqual('test', body['name'])

        resp, body = self.client.get_list_obj('workbooks')

        self.assertEqual(200, resp.status)
        self.assertEqual('test', body['workbooks'][0]['name'])

        self.client.delete_obj('workbooks', 'test')
        _, body = self.client.get_list_obj('workbooks')

        self.assertEqual([], body['workbooks'])

    @test.attr(type='smoke')
    def test_update_workbook(self):
        self.client.create_obj('workbooks', 'test')
        self.obj.append(['workbooks', 'test'])
        resp, body = self.client.update_obj('workbooks', 'test')

        self.assertEqual(200, resp.status)
        self.assertEqual('testupdated', body['name'])

        self.obj.append(['workbooks', 'testupdated'])

    @test.attr(type='smoke')
    def test_get_workbook_definition(self):
        self.client.create_obj('workbooks', 'test')
        self.obj.append(['workbooks', 'test'])
        resp, body = self.client.get_workbook_definition('test')

        self.assertEqual(200, resp.status)
        self.assertIsNotNone(body)

    @test.attr(type='smoke')
    def test_upload_workbook_definition(self):
        self.client.create_obj('workbooks', 'test1')
        self.obj.append(['workbooks', 'test1'])
        resp, body = self.client.upload_workbook_definition('test1')

        self.assertEqual(200, resp.status)
        self.assertIsNotNone(body)

    @test.attr(type='negative')
    def test_double_create_obj(self):
        self.client.create_obj('workbooks', 'test')
        self.obj.append(['workbooks', 'test'])

        self.assertRaises(exceptions.Conflict, self.client.create_obj,
                          'workbooks', 'test')

        self.client.delete_obj('workbooks', 'test')
        _, body = self.client.get_list_obj('workbooks')

        self.assertEqual([], body['workbooks'])

    @test.attr(type='negative')
    def test_get_nonexistent_workbook_definition(self):
        self.assertRaises(exceptions.NotFound,
                          self.client.get_workbook_definition,
                          'fksn')


class ExecutionTests(base.TestCaseAdvanced):

    @test.attr(type='smoke')
    def test_create_execution(self):
        self.client.create_obj('workbooks', 'test123')
        self.obj.append(['workbooks', 'test123'])
        self.client.upload_workbook_definition('test123')

        nova_url = "/".join(self.server_client.base_url.split('/')[:-1])

        context = {
            "server_name": "aloha",
            "nova_url": nova_url,
            "image_id": self.image_ref,
            "flavor_id": self.flavor_ref
        }

        post_body = {
            "workbook_name": "test123",
            "task": "create-vm",
            "context": json.dumps(context)
        }

        resp, body = self.client.create_execution('test123', post_body)
        body = json.loads(body)

        self.assertEqual(201, resp.status)
        self.assertEqual('test123', body["workbook_name"])
        while not self.server_client.list_servers()[1]['servers']:
            time.sleep(2)
        for server in self.server_client.list_servers()[1]['servers']:
            if server['name'] == 'aloha':
                self.server_ids.append(server['id'])
