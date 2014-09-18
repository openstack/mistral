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


class WorkbooksTestsV2(test_mistral_basic.WorkbooksTestsV1):

    _version = 2


class WorkflowsTestsV2(base.TestCase):

    _version = 2

    def tearDown(self):

        _, wfs = self.client.get_list_obj('workflows')
        for wf in wfs['workflows']:
            self.client.delete_obj('workflows', wf['name'])

        super(WorkflowsTestsV2, self).tearDown()

    @test.attr(type='smoke')
    def test_get_list_workflows(self):
        resp, body = self.client.get_list_obj('workflows')

        self.assertEqual(200, resp.status)
        self.assertEqual([], body['workflows'])

    @test.attr(type='smoke')
    def test_create_and_delete_workflow(self):
        resp, body = self.client.create_workflow('wf')

        self.assertEqual(201, resp.status)
        self.assertEqual('wf', body['name'])

        resp, body = self.client.get_list_obj('workflows')

        self.assertEqual(200, resp.status)
        names = [body['workflows'][i]['name']
                 for i in range(len(body['workflows']))]
        self.assertIn('wf', names)

        self.client.delete_obj('workflows', 'wf')
        _, body = self.client.get_list_obj('workflows')

        names = [body['workflows'][i]['name']
                 for i in range(len(body['workflows']))]
        self.assertNotIn('wf', names)

    @test.attr(type='smoke')
    def test_get_workflow(self):
        self.client.create_workflow('wf')
        resp, body = self.client.get_object('workflows', 'wf')

        self.assertEqual(200, resp.status)
        self.assertEqual('wf', body['name'])

    @test.attr(type='smoke')
    def test_update_workflow(self):
        self.client.create_workflow('wf')
        resp, body = self.client.update_workflow('wf')

        self.assertEqual(200, resp.status)
        self.assertEqual('wfupdated', body['name'])

    @test.attr(type='smoke')
    def test_upload_workflow_definition(self):
        self.client.create_workflow('test_wf')
        resp, body = self.client.upload_workflow_definition('test_wf')

        self.assertEqual(200, resp.status)
        self.assertIsNotNone(body)

    @test.attr(type='smoke')
    def test_get_workflow_definition(self):
        self.client.create_workflow('test')
        self.client.upload_workflow_definition('test')
        resp, body = self.client.get_workflow_definition('test')

        self.assertEqual(200, resp.status)
        self.assertIsNotNone(body)


class ExecutionsTestsV2(test_mistral_basic.ExecutionsTestsV1):

    _version = 2

    def setUp(self):
        super(ExecutionsTestsV2, self).setUp()
        self.entity_type = 'workflow_name'
        self.entity_name = 'test.test'
