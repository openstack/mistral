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
from tempest.lib import decorators

from mistral_tempest_tests.tests import base


class TasksTestsV2(base.TestCase):

    _service = 'workflowv2'

    def setUp(self):
        super(TasksTestsV2, self).setUp()
        self.useFixture(lockutils.LockFixture('mistral-workflow'))
        _, body = self.client.create_workflow('wf_v2.yaml')
        self.direct_wf_name = body['workflows'][0]['name']
        _, execution = self.client.create_execution(self.direct_wf_name)
        self.execution_id = execution['id']

    def tearDown(self):
        for wf in self.client.workflows:
            self.client.delete_obj('workflows', wf)
        self.client.workflows = []

        for wf in self.client.executions:
            self.client.delete_obj('executions', wf)
        self.client.executions = []

        super(TasksTestsV2, self).tearDown()

    @decorators.attr(type='smoke')
    @decorators.idempotent_id('81159dce-3802-44ee-a8d4-5ddca106fd91')
    def test_get_tasks_list(self):
        resp, body = self.client.get_list_obj('tasks')

        self.assertEqual(200, resp.status)
        self.assertNotEmpty(body['tasks'])

    @decorators.attr(type='sanity')
    @decorators.idempotent_id('f62664de-bd2b-4153-8d0f-5a76d78abbad')
    def test_get_task(self):
        resp, body = self.client.get_list_obj('tasks')

        self.assertEqual(200, resp.status)
        self.assertEqual(
            self.direct_wf_name, body['tasks'][-1]['workflow_name']
        )

    @decorators.attr(type='sanity')
    @decorators.idempotent_id('3230d694-40fd-4094-ad12-024f40a21b94')
    def test_get_tasks_of_execution(self):
        resp, body = self.client.get_list_obj(
            'tasks?workflow_execution_id=%s' % self.execution_id)

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

    @decorators.attr(type='sanity')
    @decorators.idempotent_id('1ac726eb-b945-4b82-8755-a2fb2dc009bc')
    def test_task_type(self):
        resp, body = self.client.get_list_obj('tasks')

        self.assertEqual(200, resp.status)

        bt = body['tasks']
        ll = [[v for k, v in d.items() if 'type' in k] for d in bt]
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
