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
from tempest.lib import exceptions

from mistral import utils
from mistral_tempest_tests.tests import base

import json


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

    @decorators.attr(type='smoke')
    @decorators.idempotent_id('c0b4b658-6f01-4680-b402-2f683b3d78b6')
    def test_get_list_executions(self):
        resp, body = self.client.get_list_obj('executions')
        self.assertEqual(200, resp.status)
        self.assertNotIn('next', body)

    @decorators.attr(type='smoke')
    @decorators.idempotent_id('0bfcb4b0-b1e4-4499-b81b-0e86c8a2a841')
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
            'executions?limit=1&sort_keys=workflow_name&sort_dirs=asc')

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

    @decorators.attr(type='sanity')
    @decorators.idempotent_id('5d8ebe04-8de6-414d-908f-213af59e4c6a')
    def test_create_execution_for_direct_wf(self):
        resp, body = self.client.create_execution(self.direct_wf_name)
        exec_id = body['id']
        self.assertEqual(201, resp.status)
        self.assertEqual(self.direct_wf_name, body['workflow_name'])
        self.assertEqual('RUNNING', body['state'])

        resp, body = self.client.get_list_obj('executions')
        self.assertIn(exec_id,
                      [ex_id['id'] for ex_id in body['executions']])

    @decorators.attr(type='sanity')
    @decorators.idempotent_id('101bfdff-8309-4add-9504-544b15f13d95')
    def test_create_execution_for_reverse_wf(self):
        resp, body = self.client.create_execution(
            self.reverse_wf['name'],
            wf_input={self.reverse_wf['input']: "Bye"},
            params={"task_name": "goodbye"})

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

    @decorators.attr(type='sanity')
    @decorators.idempotent_id('2df30966-9c45-4a2e-942d-e74bd92cb5aa')
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

    @decorators.attr(type='sanity')
    @decorators.idempotent_id('f7f50198-2dbd-4ca1-af51-d0eadc1108ac')
    def test_get_execution(self):
        _, execution = self.client.create_execution(self.direct_wf_name)

        resp, body = self.client.get_object('executions', execution['id'])

        del execution['state']
        del body['state']

        self.assertEqual(200, resp.status)
        self.assertEqual(execution['id'], body['id'])

    @decorators.attr(type='sanity')
    @decorators.idempotent_id('2f142ba0-6b88-4d63-8544-05c3dbfe13cc')
    def test_update_execution_pause(self):
        _, execution = self.client.create_execution(self.direct_wf_name)
        resp, body = self.client.update_execution(
            execution['id'], '{"state": "PAUSED"}')

        self.assertEqual(200, resp.status)
        self.assertEqual('PAUSED', body['state'])

    @decorators.attr(type='sanity')
    @decorators.idempotent_id('f0557236-55ab-457d-9197-05bc2ae53e21')
    def test_update_execution_description(self):
        _, execution = self.client.create_execution(self.direct_wf_name)
        resp, body = self.client.update_execution(
            execution['id'], '{"description": "description"}')

        self.assertEqual(200, resp.status)
        self.assertEqual('description', body['description'])

    @decorators.attr(type='sanity')
    @decorators.idempotent_id('c54b4d68-b179-4339-bdab-a91cd6e819b7')
    def test_update_execution_fail(self):
        _, execution = self.client.create_execution(self.direct_wf_name)
        resp, body = self.client.update_execution(
            execution['id'], '{"state": "ERROR", "state_info": "Forced"}')

        self.assertEqual(200, resp.status)
        self.assertEqual('ERROR', body['state'])
        self.assertEqual('Forced', body['state_info'])

    @decorators.attr(type='sanity')
    @decorators.idempotent_id('b5ce0d18-7d78-45bb-813e-ed94cea65fd0')
    def test_update_execution_by_admin(self):
        _, execution = self.client.create_execution(self.direct_wf_name)
        resp, body = self.admin_client.update_execution(
            execution['id'], '{"description": "description set by admin"}')

        self.assertEqual(200, resp.status)
        self.assertEqual('description set by admin', body['description'])

        resp, body = self.client.get_object('executions', execution['id'])

        self.assertEqual(200, resp.status)
        self.assertEqual("description set by admin", body['description'])

    @decorators.attr(type='sanity')
    @decorators.idempotent_id('c6247362-a082-49ad-a2c3-aaf12419a477')
    def test_update_execution_by_other_fail(self):
        _, execution = self.client.create_execution(self.direct_wf_name)

        self.assertRaises(
            exceptions.NotFound,
            self.alt_client.update_execution,
            execution['id'],
            '{"description": "description set by admin"}'
        )

    @decorators.attr(type='negative')
    @decorators.idempotent_id('d8bde271-6785-4ace-9173-a8a3a01d5eaa')
    def test_get_nonexistent_execution(self):
        self.assertRaises(exceptions.NotFound, self.client.get_object,
                          'executions', '1a2b3c')

    @decorators.attr(type='negative')
    @decorators.idempotent_id('e26e31ba-88cf-4b90-8b3a-fd4ecc612252')
    def test_update_nonexistent_execution(self):
        put_body = '{"state": "STOPPED"}'

        self.assertRaises(exceptions.NotFound,
                          self.client.update_execution,
                          '1a2b3c', put_body)

    @decorators.attr(type='negative')
    @decorators.idempotent_id('b337e270-b3b6-41e2-8de2-05030b06fc37')
    def test_delete_nonexistent_execution(self):
        self.assertRaises(exceptions.NotFound,
                          self.client.delete_obj,
                          'executions', 'nonexist')

    @decorators.attr(type='negative')
    @decorators.idempotent_id('46f7b4b0-7d4a-4bdc-b2b6-46343cdd6f3a')
    def test_create_ex_for_nonexistent_wf(self):
        self.assertRaises(exceptions.NotFound,
                          self.client.create_execution,
                          'nonexist')

    @decorators.attr(type='negative')
    @decorators.idempotent_id('9d27247e-b4d4-40ab-9181-9986655a6be4')
    def test_create_execution_for_reverse_wf_invalid_start_task(self):
        self.assertRaises(
            exceptions.BadRequest,
            self.client.create_execution,
            self.reverse_wf['name'],
            {self.reverse_wf['input']: "Bye"},
            {"task_name": "nonexist"}
        )

    @decorators.attr(type='negative')
    @decorators.idempotent_id('0d6ac42b-4059-40ef-99d0-a65b3cd1837c')
    def test_create_execution_forgot_input_params(self):
        self.assertRaises(
            exceptions.BadRequest,
            self.client.create_execution,
            self.reverse_wf['name'],
            params={"task_name": "nonexist"}
        )

    @decorators.attr(type='sanity')
    @decorators.idempotent_id('52779c73-7563-47b2-8231-a24d6bf531a7')
    def test_action_ex_concurrency(self):
        resp, wf = self.client.create_workflow("wf_action_ex_concurrency.yaml")
        self.assertEqual(201, resp.status)

        wf_name = wf['workflows'][0]['name']
        resp, execution = self.client.create_execution(wf_name)

        self.assertEqual(201, resp.status)
        self.assertEqual('RUNNING', execution['state'])

        self.client.wait_execution_success(execution)

    @decorators.attr(type='sanity')
    @decorators.idempotent_id('eb061c4d-2892-47f0-81e6-37ba15c376bb')
    def test_task_ex_concurrency(self):
        resp, wf = self.client.create_workflow("wf_task_ex_concurrency.yaml")
        self.assertEqual(201, resp.status)

        wf_name = wf['workflows'][0]['name']
        resp, execution = self.client.create_execution(wf_name)

        self.assertEqual(201, resp.status)
        self.assertEqual('RUNNING', execution['state'])

        self.client.wait_execution(execution, target_state='ERROR')

    @decorators.attr(type='sanity')
    @decorators.idempotent_id('acc8e401-2b26-4c41-9e79-8da791da85c0')
    def test_delete_execution_by_admin(self):
        _, body = self.client.create_execution(self.direct_wf_id)
        exec_id = body['id']
        resp, _ = self.admin_client.delete_obj('executions', exec_id)

        self.assertEqual(204, resp.status)

        self.client.executions.remove(exec_id)

        self.assertRaises(
            exceptions.NotFound,
            self.client.get_object,
            'executions',
            exec_id
        )

    @decorators.idempotent_id('a882876b-7565-4f7f-9714-d99032ffaabb')
    @decorators.attr(type='sanity')
    def test_workflow_execution_of_nested_workflows_within_namespace(self):
        low_wf = 'for_wf_namespace/lowest_level_wf.yaml'
        middle_wf = 'for_wf_namespace/middle_wf.yaml'
        top_wf = 'for_wf_namespace/top_level_wf.yaml'

        resp, wf = self.client.create_workflow(low_wf)
        self.assertEqual(201, resp.status)

        namespace = 'abc'
        resp, wf = self.client.create_workflow(low_wf, namespace=namespace)
        self.assertEqual(201, resp.status)

        resp, wf = self.client.create_workflow(middle_wf)
        self.assertEqual(201, resp.status)

        resp, wf = self.client.create_workflow(top_wf)
        self.assertEqual(201, resp.status)

        resp, wf = self.client.create_workflow(top_wf, namespace=namespace)
        self.assertEqual(201, resp.status)

        wf_name = wf['workflows'][0]['name']
        resp, top_execution = self.client.create_execution(wf_name, namespace)

        self.assertEqual(201, resp.status)
        self.assertEqual('RUNNING', top_execution['state'])
        self.assertEqual(wf_name, top_execution['workflow_name'])
        self.assertEqual(wf_name, top_execution['workflow_name'])
        self.assertEqual(namespace, top_execution['workflow_namespace'])

        self.client.wait_execution(top_execution, target_state='SUCCESS')

        self.assertEqual(
            namespace,
            json.loads(top_execution['params'])['namespace']
        )

        resp, tasks = self.client.get_tasks(top_execution['id'])
        top_task = tasks['tasks'][0]

        self.assertEqual(wf_name, top_task['workflow_name'])
        self.assertEqual(namespace, top_task['workflow_namespace'])

        resp, executions = self.client.get_executions(top_task['id'])
        middle_execution = executions['executions'][0]

        self.assertEqual('middle_wf', middle_execution['workflow_name'])
        self.assertEqual('', middle_execution['workflow_namespace'])

        self.assertEqual(
            namespace,
            json.loads(middle_execution['params'])['namespace']
        )

        resp, tasks = self.client.get_tasks(middle_execution['id'])
        middle_task = tasks['tasks'][0]

        self.assertEqual('middle_wf', middle_task['workflow_name'])
        self.assertEqual('', middle_task['workflow_namespace'])

        resp, executions = self.client.get_executions(middle_task['id'])
        lowest_execution = executions['executions'][0]

        self.assertEqual('lowest_level_wf', lowest_execution['workflow_name'])
        self.assertEqual(namespace, lowest_execution['workflow_namespace'])

        self.assertEqual(
            namespace,
            json.loads(lowest_execution['params'])['namespace']
        )

        resp, tasks = self.client.get_tasks(lowest_execution['id'])
        lowest_task = tasks['tasks'][0]

        self.assertEqual('lowest_level_wf', lowest_task['workflow_name'])
        self.assertEqual(namespace, lowest_task['workflow_namespace'])

        resp, action_executions = self.client.get_action_executions(
            lowest_task['id']
        )

        action_execution = action_executions['action_executions'][0]

        self.assertEqual('lowest_level_wf', action_execution['workflow_name'])
        self.assertEqual(namespace, action_execution['workflow_namespace'])
