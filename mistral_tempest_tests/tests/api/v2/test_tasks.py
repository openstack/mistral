# Copyright 2016 NEC Corporation. All rights reserved.
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

from oslo_concurrency.fixture import lockutils
from tempest import test

from mistral_tempest_tests.tests import base


class TasksTestsV2(base.TestCase):

    _service = 'workflowv2'

    def setUp(self):
        super(TasksTestsV2, self).setUp()
        self.useFixture(lockutils.LockFixture('mistral-workflow'))
        _, body = self.client.create_workflow('wf_v2.yaml')
        self.direct_wf_name = body['workflows'][0]['name']
        _, execution = self.client.create_execution(self.direct_wf_name)

    def tearDown(self):
        for wf in self.client.workflows:
            self.client.delete_obj('workflows', wf)
        self.client.workflows = []

        for wf in self.client.executions:
            self.client.delete_obj('executions', wf)
        self.client.executions = []

        super(TasksTestsV2, self).tearDown()

    @test.attr(type='smoke')
    def test_get_tasks_list(self):
        resp, body = self.client.get_list_obj('tasks')

        self.assertEqual(200, resp.status)
        self.assertNotEmpty(body['tasks'])

    @test.attr(type='sanity')
    def test_get_task(self):
        resp, body = self.client.get_list_obj('tasks')

        self.assertEqual(200, resp.status)
        self.assertEqual(
            self.direct_wf_name, body['tasks'][-1]['workflow_name']
        )


class TaskTypesTestsV2(base.TestCase):

    _service = 'workflowv2'

    def setUp(self):
        super(TaskTypesTestsV2, self).setUp()

        self.useFixture(lockutils.LockFixture('mistral-workflow'))

        _, wb_body = self.client.create_workbook('wb_with_nested_wf.yaml')
        self.nested_wf_name = 'wb_with_nested_wf.wrapping_wf'
        _, execution = self.client.create_execution(self.nested_wf_name)

    @test.attr(type='sanity')
    def test_task_type(self):
        resp, body = self.client.get_list_obj('tasks')

        self.assertEqual(200, resp.status)

        bt = body['tasks']
        ll = [[v for k, v in d.iteritems() if 'type' in k] for d in bt]
        types_list = [item for sublist in ll for item in sublist]

        self.assertIn(
            'WORKFLOW', types_list
        )
        self.assertIn(
            'ACTION', types_list
        )

        # there are 2 tasks in the workflow one of each type
        self.assertEqual(
            2, len(types_list)
        )
