
# Copyright 2013 Mirantis, Inc.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import json
import os
import time

from tempest import clients
from tempest.common import rest_client
from tempest import config
from tempest import exceptions
import tempest.test

CONF = config.CONF


class MistralClient(rest_client.RestClient):

    def __init__(self, auth_provider):
        super(MistralClient, self).__init__(auth_provider)

        self.service = 'workflow_service'
        self.endpoint_url = 'publicURL'

    def get_list_obj(self, name):
        resp, body = self.get(name)
        return resp, json.loads(body)

    def create_obj(self, path, name):
        post_body = '{"name": "%s"}' % name
        resp, body = self.post(path, post_body)
        return resp, json.loads(body)

    def delete_obj(self, path, name):
        return self.delete('{path}/{name}'.format(path=path, name=name))

    def update_obj(self, path, name):
        post_body = '{"name": "%s"}' % (name + 'updated')
        resp, body = self.put('{path}/{name}'.format(path=path, name=name),
                              post_body)
        return resp, json.loads(body)

    def get_workbook_definition(self, name):
        headers = {'X-Auth-Token': self.auth_provider.get_token()}
        return self.get('workbooks/{name}/definition'.format(name=name),
                        headers)

    def upload_workbook_definition(self, name):
        headers = {'Content-Type': 'text/plain',
                   'X-Auth-Token': self.auth_provider.get_token()}

        __location = os.path.realpath(os.path.join(os.getcwd(),
                                                   os.path.dirname(__file__)))

        file = open(os.path.join(__location, 'v1/demo.yaml'), 'rb').read()
        return self.put('workbooks/{name}/definition'.format(name=name),
                        file, headers)

    def create_execution(self, workbook_name, body):
        return self.post('workbooks/{name}/executions'.format(
            name=workbook_name), json.dumps(body))

    def get_execution(self, workbook_name, execution_id):
        return self.get('/workbooks/{name}/executions/{execution}'.format(
            name=workbook_name, execution=execution_id))

    def update_execution(self, workbook_name, execution_id, put_body):
        return self.put('/workbooks/{name}/executions/{execution}'.format(
            name=workbook_name, execution=execution_id), json.dumps(put_body))

    def get_tasks_list(self, workbook_name, execution_id):
        resp, body = self.get(
            '/workbooks/{name}/executions/{execution}/tasks'.format(
                name=workbook_name,
                execution=execution_id))

        return resp, json.loads(body)['tasks']

    def get_task(self, workbook_name, execution_id, task_id):
        resp, body = self.get(
            '/workbooks/{name}/executions/{execution}/tasks/{task}'.format(
                name=workbook_name,
                execution=execution_id,
                task=task_id))

        return resp, json.loads(body)

    def update_task(self, workbook_name, execution_id, task_id, put_body):
        resp, body = self.put(
            '/workbooks/{name}/executions/{execution}/tasks/{task}'.format(
                name=workbook_name,
                execution=execution_id,
                task=task_id), json.dumps(put_body))

        return resp, json.loads(body)


class TestCase(tempest.test.BaseTestCase):

    @classmethod
    def setUpClass(cls):
        """This method allows to initialize authentication before
        each test case and define parameters of Mistral API Service.
        """
        super(TestCase, cls).setUpClass()

        cls.mgr = clients.Manager()
        cls.client = MistralClient(cls.mgr.auth_provider)

    def setUp(self):
        super(TestCase, self).setUp()
        self.obj = []

    def tearDown(self):
        super(TestCase, self).tearDown()

        for i in self.obj:
            try:
                self.client.delete_obj(i[0], i[1])
            except exceptions.NotFound:
                pass


class TestCaseAdvanced(TestCase):

    @classmethod
    def setUpClass(cls):

        super(TestCaseAdvanced, cls).setUpClass()

        cls.server_client = cls.mgr.servers_client

        cls.image_ref = CONF.compute.image_ref
        cls.flavor_ref = CONF.compute.flavor_ref

    def setUp(self):
        super(TestCaseAdvanced, self).setUp()

        self.server_ids = []

        self.client.create_obj('workbooks', 'test123')
        self.obj.append(['workbooks', 'test123'])
        self.client.upload_workbook_definition('test123')

    def tearDown(self):
        super(TestCaseAdvanced, self).tearDown()

        for server_id in self.server_ids:
            try:
                self.server_client.delete_server(server_id)
                self.server_client.wait_for_server_termination(server_id)
            except exceptions.NotFound:
                pass

    def _create_execution(self, workbook_name, server_name):

        nova_url = "/".join(self.server_client.base_url.split('/')[:-1])

        context = {
            "server_name": server_name,
            "nova_url": nova_url,
            "image_id": self.image_ref,
            "flavor_id": self.flavor_ref
        }

        post_body = {
            "workbook_name": workbook_name,
            "task": "create-vm",
            "context": json.dumps(context)
        }

        resp, body = self.client.create_execution(workbook_name, post_body)

        while not self.server_client.list_servers()[1]['servers']:
            time.sleep(2)
        for server in self.server_client.list_servers()[1]['servers']:
            if server['name'] == server_name:
                self.server_ids.append(server['id'])

        return resp, json.loads(body)
