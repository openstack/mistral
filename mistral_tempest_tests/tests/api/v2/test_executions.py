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
from oslo_log import log as logging
from tempest.lib import exceptions
from tempest import test

from mistral import utils
from mistral_tempest_tests.tests import base


LOG = logging.getLogger(__name__)


class ExecutionTestsV2(base.TestCase):

    _service = 'workflowv2'

    def setUp(self):
        super(ExecutionTestsV2, self).setUp()
        self.useFixture(lockutils.LockFixture('mistral-workflow'))
        _, body = self.client.create_workflow('wf_v2.yaml')

        self.direct_wf_name = 'wf'
        self.direct_wf2_name = 'wf2'
        self.direct_wf_id = body['workflows'][0]['id']
        reverse_wfs = [wf for wf in body['workflows'] if wf['name'] == 'wf1']
        self.reverse_wf = reverse_wfs[0]

    def tearDown(self):
        for wf in self.client.workflows:
            self.client.delete_obj('workflows', wf)
        self.client.workflows = []

        for ex in self.client.executions:
            self.client.delete_obj('executions', ex)
        self.client.executions = []

        super(ExecutionTestsV2, self).tearDown()

    @test.attr(type='smoke')
    def test_get_list_executions(self):
        resp, body = self.client.get_list_obj('executions')
        self.assertEqual(200, resp.status)
        self.assertNotIn('next', body)

    @test.attr(type='smoke')
    def test_get_list_executions_with_pagination(self):
        resp, body = self.client.create_execution(self.direct_wf_name)
        exec_id_1 = body['id']

        self.assertEqual(201, resp.status)

        resp, body = self.client.create_execution(self.direct_wf2_name)
        exec_id_2 = body['id']

        self.assertEqual(201, resp.status)

        resp, body = self.client.get_list_obj('executions')

        self.assertIn(exec_id_1, [ex['id'] for ex in body['executions']])
        self.assertIn(exec_id_2, [ex['id'] for ex in body['executions']])

        resp, body = self.client.get_list_obj(
            'executions?limit=1&sort_keys=workflow_name&sort_dirs=asc'
        )

        self.assertEqual(200, resp.status)
        self.assertEqual(1, len(body['executions']))
        self.assertIn('next', body)

        workflow_name_1 = body['executions'][0].get('workflow_name')
        next = body.get('next')
        param_dict = utils.get_dict_from_string(
            next.split('?')[1],
            delimiter='&'
        )

        # NOTE: 'id' gets included into sort keys automatically with 'desc'
        # sorting to avoid pagination looping.
        expected_dict = {
            'limit': 1,
            'sort_keys': 'workflow_name,id',
            'sort_dirs': 'asc,asc',
        }

        self.assertTrue(
            set(expected_dict.items()).issubset(set(param_dict.items()))
        )

        # Query again using 'next' link
        url_param = next.split('/')[-1]
        resp, body = self.client.get_list_obj(url_param)

        self.assertEqual(200, resp.status)
        self.assertEqual(1, len(body['executions']))

        workflow_name_2 = body['executions'][0].get('workflow_name')

        self.assertGreater(workflow_name_2, workflow_name_1)

    @test.attr(type='sanity')
    def test_create_execution_for_direct_wf(self):
        resp, body = self.client.create_execution(self.direct_wf_name)
        exec_id = body['id']
        self.assertEqual(201, resp.status)
        self.assertEqual(self.direct_wf_name, body['workflow_name'])
        self.assertEqual('RUNNING', body['state'])

        resp, body = self.client.get_list_obj('executions')
        self.assertIn(exec_id,
                      [ex_id['id'] for ex_id in body['executions']])

    @test.attr(type='sanity')
    def test_create_execution_for_reverse_wf(self):
        resp, body = self.client.create_execution(
            self.reverse_wf['name'],
            {self.reverse_wf['input']: "Bye"},
            {"task_name": "goodbye"})

        exec_id = body['id']
        self.assertEqual(201, resp.status)
        self.assertEqual(self.reverse_wf['name'], body['workflow_name'])
        self.assertEqual('RUNNING', body['state'])

        resp, body = self.client.get_list_obj('executions')
        self.assertIn(exec_id,
                      [ex_id['id'] for ex_id in body['executions']])

        resp, body = self.client.get_object('executions', exec_id)
        # TODO(nmakhotkin): Fix this loop. It is infinite now.
        while body['state'] != 'SUCCESS':
            resp, body = self.client.get_object('executions', exec_id)
            self.assertEqual(200, resp.status)
        self.assertEqual('SUCCESS', body['state'])

    @test.attr(type='sanity')
    def test_create_execution_by_wf_id(self):
        resp, body = self.client.create_execution(self.direct_wf_id)
        exec_id = body['id']
        self.assertEqual(201, resp.status)
        self.assertEqual(self.direct_wf_id, body['workflow_id'])
        self.assertEqual('RUNNING', body['state'])

        resp, body = self.client.get_list_obj('executions')
        self.assertIn(
            exec_id,
            [ex_id['id'] for ex_id in body['executions']]
        )

    @test.attr(type='sanity')
    def test_get_execution(self):
        _, execution = self.client.create_execution(self.direct_wf_name)

        resp, body = self.client.get_object('executions', execution['id'])

        del execution['state']
        del body['state']

        self.assertEqual(200, resp.status)
        self.assertEqual(execution['id'], body['id'])

    @test.attr(type='sanity')
    def test_update_execution_pause(self):
        _, execution = self.client.create_execution(self.direct_wf_name)
        resp, body = self.client.update_execution(
            execution['id'], '{"state": "PAUSED"}')

        self.assertEqual(200, resp.status)
        self.assertEqual('PAUSED', body['state'])

    @test.attr(type='sanity')
    def test_update_execution_description(self):
        _, execution = self.client.create_execution(self.direct_wf_name)
        resp, body = self.client.update_execution(
            execution['id'], '{"description": "description"}')

        self.assertEqual(200, resp.status)
        self.assertEqual('description', body['description'])

    @test.attr(type='sanity')
    def test_update_execution_fail(self):
        _, execution = self.client.create_execution(self.direct_wf_name)
        resp, body = self.client.update_execution(
            execution['id'], '{"state": "ERROR", "state_info": "Forced"}')

        self.assertEqual(200, resp.status)
        self.assertEqual('ERROR', body['state'])
        self.assertEqual('Forced', body['state_info'])

    @test.attr(type='negative')
    def test_get_nonexistent_execution(self):
        self.assertRaises(exceptions.NotFound, self.client.get_object,
                          'executions', '1a2b3c')

    @test.attr(type='negative')
    def test_update_nonexistent_execution(self):
        put_body = '{"state": "STOPPED"}'

        self.assertRaises(exceptions.NotFound,
                          self.client.update_execution,
                          '1a2b3c', put_body)

    @test.attr(type='negative')
    def test_delete_nonexistent_execution(self):
        self.assertRaises(exceptions.NotFound,
                          self.client.delete_obj,
                          'executions', 'nonexist')

    @test.attr(type='negative')
    def test_create_ex_for_nonexistent_wf(self):
        self.assertRaises(exceptions.NotFound,
                          self.client.create_execution,
                          'nonexist')

    @test.attr(type='negative')
    def test_create_execution_for_reverse_wf_invalid_start_task(self):
        self.assertRaises(
            exceptions.BadRequest,
            self.client.create_execution,
            self.reverse_wf['name'],
            {self.reverse_wf['input']: "Bye"},
            {"task_name": "nonexist"}
        )

    @test.attr(type='negative')
    def test_create_execution_forgot_input_params(self):
        self.assertRaises(
            exceptions.BadRequest,
            self.client.create_execution,
            self.reverse_wf['name'],
            params={"task_name": "nonexist"}
        )

    @test.attr(type='sanity')
    def test_action_ex_concurrency(self):
        resp, wf = self.client.create_workflow("wf_action_ex_concurrency.yaml")
        self.assertEqual(201, resp.status)

        wf_name = wf['workflows'][0]['name']
        resp, execution = self.client.create_execution(wf_name)

        self.assertEqual(201, resp.status)
        self.assertEqual('RUNNING', execution['state'])

        self.client.wait_execution_success(execution)

    @test.attr(type='sanity')
    def test_task_ex_concurrency(self):
        resp, wf = self.client.create_workflow("wf_task_ex_concurrency.yaml")
        self.assertEqual(201, resp.status)

        wf_name = wf['workflows'][0]['name']
        resp, execution = self.client.create_execution(wf_name)

        self.assertEqual(201, resp.status)
        self.assertEqual('RUNNING', execution['state'])

        self.client.wait_execution(execution, target_state='ERROR')
