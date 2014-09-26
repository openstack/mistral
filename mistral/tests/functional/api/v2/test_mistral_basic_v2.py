# Copyright 2014 Mirantis, Inc.
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

from tempest import test

from mistral.tests.functional.api.v1 import test_mistral_basic
from mistral.tests.functional import base


class WorkbookTestsV2(test_mistral_basic.WorkbookTestsV1):

    _version = 2

    def tearDown(self):
        for wf in self.client.workflows:
            self.client.delete_obj('workflows', wf)
            self.client.workflows.remove(wf)

        super(WorkbookTestsV2, self).tearDown()


class WorkflowTestsV2(base.TestCase):

    _version = 2

    def tearDown(self):
        for wf in self.client.workflows:
            self.client.delete_obj('workflows', wf)
            self.client.workflows.remove(wf)

        super(WorkflowTestsV2, self).tearDown()

    @test.attr(type='smoke')
    def test_get_list_workflows(self):
        resp, body = self.client.get_list_obj('workflows')

        self.assertEqual(200, resp.status)
        self.assertEqual([], body['workflows'])

    @test.attr(type='smoke')
    def test_create_and_delete_workflow(self):
        resp, body = self.client.create_workflow()

        self.assertEqual(201, resp.status)
        self.assertEqual('wf', body['workflows'][0]['name'])

        resp, body = self.client.get_list_obj('workflows')

        self.assertEqual(200, resp.status)
        names = [body['workflows'][i]['name']
                 for i in range(len(body['workflows']))]
        self.assertIn('wf', names)

        self.client.delete_obj('workflows', 'wf')
        self.client.workflows.remove('wf')

        _, body = self.client.get_list_obj('workflows')

        names = [body['workflows'][i]['name']
                 for i in range(len(body['workflows']))]
        self.assertNotIn('wf', names)

    @test.attr(type='smoke')
    def test_get_workflow(self):
        self.client.create_workflow()
        resp, body = self.client.get_object('workflows', 'wf')

        self.assertEqual(200, resp.status)
        self.assertEqual('wf', body['name'])

    @test.attr(type='smoke')
    def test_update_workflow(self):
        self.client.create_workflow()
        resp, body = self.client.update_workflow()

        self.assertEqual(200, resp.status)
        self.assertEqual('wf', body['workflows'][0]['name'])

    @test.attr(type='smoke')
    def test_get_workflow_definition(self):
        self.client.create_workflow()
        resp, body = self.client.get_workflow_definition('wf')

        self.assertEqual(200, resp.status)
        self.assertIsNotNone(body)


class ExecutionTestsV2(test_mistral_basic.ExecutionTestsV1):

    _version = 2

    def setUp(self):
        super(ExecutionTestsV2, self).setUp()

        self.entity_type = 'workflow_name'
        self.entity_name = 'test.test'

    def tearDown(self):
        for wf in self.client.workflows:
            self.client.delete_obj('workflows', wf)
            self.client.workflows.remove(wf)

        super(ExecutionTestsV2, self).tearDown()
