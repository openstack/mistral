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
import json

from oslo_concurrency.fixture import lockutils
from tempest.lib import decorators
from tempest.lib import exceptions
from tempest import test

from mistral import utils
from mistral_tempest_tests.tests import base


class WorkflowTestsV2(base.TestCase):

    _service = 'workflowv2'

    def tearDown(self):
        for wf in self.client.workflows:
            self.client.delete_obj('workflows', wf)
        self.client.workflows = []

        super(WorkflowTestsV2, self).tearDown()

    @test.attr(type='smoke')
    @decorators.idempotent_id('e9cd6817-e8d1-4604-ba76-b0e17219f4c5')
    def test_get_list_workflows(self):
        resp, body = self.client.get_list_obj('workflows')
        self.assertEqual(200, resp.status)

        names = [wf['name'] for wf in body['workflows']]

        self.assertIn('std.create_instance', names)

        self.assertNotIn('next', body)

    @test.attr(type='smoke')
    @decorators.idempotent_id('be8a4a44-eeb3-48e3-b11d-b83ba14dbf2c')
    def test_get_list_workflows_by_admin(self):
        self.useFixture(lockutils.LockFixture('mistral-workflow'))

        _, body = self.client.create_workflow('wf_v2.yaml')
        name = body['workflows'][0]['name']

        resp, raw_body = self.admin_client.get('workflows?all_projects=true')
        body = json.loads(raw_body)

        self.assertEqual(200, resp.status)

        names = [wf['name'] for wf in body['workflows']]

        self.assertIn(name, names)

    @test.attr(type='smoke')
    @decorators.idempotent_id('c9e2ebbc-02aa-4c33-b244-e471c8266aa7')
    def test_get_list_workflows_with_project_by_admin(self):
        self.useFixture(lockutils.LockFixture('mistral-workflow'))

        _, body = self.client.create_workflow('wf_v2.yaml')

        name = body['workflows'][0]['name']

        resp, raw_body = self.admin_client.get(
            'workflows?project_id=%s' %
            self.client.auth_provider.credentials.tenant_id
        )
        body = json.loads(raw_body)

        self.assertEqual(200, resp.status)

        names = [wf['name'] for wf in body['workflows']]

        self.assertIn(name, names)

    @test.attr(type='smoke')
    @decorators.idempotent_id('b8dc1b02-8509-45e2-9df7-4630cdcfa1ab')
    def test_get_list_other_project_private_workflows(self):
        self.useFixture(lockutils.LockFixture('mistral-workflow'))

        _, body = self.client.create_workflow('wf_v2.yaml')

        name = body['workflows'][0]['name']

        resp, raw_body = self.alt_client.get(
            'workflows?project_id=%s' %
            self.client.auth_provider.credentials.tenant_id
        )
        body = json.loads(raw_body)

        self.assertEqual(200, resp.status)

        names = [wf['name'] for wf in body['workflows']]

        self.assertNotIn(name, names)

    @test.attr(type='smoke')
    @decorators.idempotent_id('2063143b-ced8-4037-9383-e2504be581e6')
    def test_get_list_workflows_with_fields(self):
        resp, body = self.client.get_list_obj('workflows?fields=name')

        self.assertEqual(200, resp.status)

        for wf in body['workflows']:
            self.assertListEqual(sorted(['id', 'name']), sorted(list(wf)))

    @test.attr(type='smoke')
    @decorators.idempotent_id('81f28735-e74e-4dc1-8b94-b548f8a80556')
    def test_get_list_workflows_with_pagination(self):
        resp, body = self.client.get_list_obj(
            'workflows?limit=1&sort_keys=name&sort_dirs=desc'
        )

        self.assertEqual(200, resp.status)
        self.assertEqual(1, len(body['workflows']))
        self.assertIn('next', body)

        name_1 = body['workflows'][0].get('name')
        next = body.get('next')

        param_dict = utils.get_dict_from_string(
            next.split('?')[1],
            delimiter='&'
        )

        # NOTE: 'id' gets included into sort keys automatically with 'desc'
        # sorting to avoid pagination looping.
        expected_sub_dict = {
            'limit': 1,
            'sort_keys': 'name,id',
            'sort_dirs': 'desc,asc'
        }

        self.assertDictContainsSubset(expected_sub_dict, param_dict)

        # Query again using 'next' hint
        url_param = next.split('/')[-1]
        resp, body = self.client.get_list_obj(url_param)

        self.assertEqual(200, resp.status)
        self.assertEqual(1, len(body['workflows']))

        name_2 = body['workflows'][0].get('name')

        self.assertGreater(name_1, name_2)

    @test.attr(type='negative')
    @decorators.idempotent_id('cdb5586f-a72f-4371-88d1-1472675915c3')
    def test_get_list_workflows_nonexist_sort_dirs(self):
        context = self.assertRaises(
            exceptions.BadRequest,
            self.client.get_list_obj,
            'workflows?limit=1&sort_keys=id&sort_dirs=nonexist'
        )

        self.assertIn(
            'Unknown sort direction',
            context.resp_body.get('faultstring')
        )

    @test.attr(type='negative')
    @decorators.idempotent_id('ac41a0ea-2be6-4307-9003-6b8dd52b0bf9')
    def test_get_list_workflows_invalid_limit(self):
        context = self.assertRaises(
            exceptions.BadRequest,
            self.client.get_list_obj,
            'workflows?limit=-1&sort_keys=id&sort_dirs=asc'
        )

        self.assertIn(
            'Limit must be positive',
            context.resp_body.get('faultstring')
        )

    @test.attr(type='negative')
    @decorators.idempotent_id('55759713-a8d7-44c2-aff1-2383f51136bd')
    def test_get_list_workflows_duplicate_sort_keys(self):
        context = self.assertRaises(
            exceptions.BadRequest,
            self.client.get_list_obj,
            'workflows?limit=1&sort_keys=id,id&sort_dirs=asc,asc'
        )

        self.assertIn(
            'Length of sort_keys must be equal or greater than sort_dirs',
            context.resp_body.get('faultstring')
        )

    @test.attr(type='sanity')
    @decorators.idempotent_id('e26b30b9-6699-4020-93a0-e25c2daca59a')
    def test_create_and_delete_workflow(self):
        self.useFixture(lockutils.LockFixture('mistral-workflow'))
        resp, body = self.client.create_workflow('wf_v2.yaml')
        name = body['workflows'][0]['name']

        self.assertEqual(201, resp.status)

        resp, body = self.client.get_list_obj('workflows')
        self.assertEqual(200, resp.status)

        names = [wf['name'] for wf in body['workflows']]
        self.assertIn(name, names)

        self.client.delete_obj('workflows', name)
        self.client.workflows.remove(name)

        _, body = self.client.get_list_obj('workflows')

        names = [wf['name'] for wf in body['workflows']]
        self.assertNotIn(name, names)

    @test.attr(type='sanity')
    @decorators.idempotent_id('f5a4a771-79b2-4f28-bfac-940aa83990a4')
    def test_get_workflow(self):
        self.useFixture(lockutils.LockFixture('mistral-workflow'))
        _, body = self.client.create_workflow('wf_v2.yaml')
        name = body['workflows'][0]['name']

        resp, body = self.client.get_object('workflows', name)

        self.assertEqual(200, resp.status)
        self.assertEqual(name, body['name'])

    @test.attr(type='sanity')
    @decorators.idempotent_id('f516aad0-9a50-4ace-a217-fa1931fd9335')
    def test_update_workflow(self):
        self.useFixture(lockutils.LockFixture('mistral-workflow'))
        _, body = self.client.create_workflow('single_wf.yaml')
        name = body['workflows'][0]['name']

        resp, body = self.client.update_request('workflows', 'single_wf.yaml')

        self.assertEqual(200, resp.status)
        self.assertEqual(name, body['workflows'][0]['name'])

    @test.attr(type='sanity')
    @decorators.idempotent_id('02bc1fc3-c31a-4e37-bb3d-eda46818505c')
    def test_get_workflow_definition(self):
        self.useFixture(lockutils.LockFixture('mistral-workflow'))
        _, body = self.client.create_workflow('wf_v2.yaml')
        name = body['workflows'][0]['name']

        resp, body = self.client.get_definition('workflows', name)

        self.assertEqual(200, resp.status)
        self.assertIsNotNone(body)

    @test.attr(type='sanity')
    @decorators.idempotent_id('04fbd003-0e52-4034-858e-6634d4f84b29')
    def test_get_workflow_uploaded_in_wb(self):
        self.useFixture(lockutils.LockFixture('mistral-workflow'))
        _, body = self.client.create_workbook('wb_v2.yaml')
        wb_name = body['name']

        _, body = self.client.get_list_obj('workflows')
        wf_names = [wf['name'] for wf in body['workflows']
                    if wf['name'].startswith(wb_name)]

        self.assertNotEmpty(wf_names)

    @test.attr(type='negative')
    @decorators.idempotent_id('5e5f0403-fb2c-41ae-bf6f-25c181515358')
    def test_get_nonexistent_workflow_definition(self):
        self.assertRaises(exceptions.NotFound,
                          self.client.get_definition,
                          'workflows', 'nonexist')

    @test.attr(type='negative')
    @decorators.idempotent_id('23c72d01-c3bb-43d6-ba15-9b49c15f800c')
    def test_get_nonexistent_workflow(self):
        self.assertRaises(exceptions.NotFound, self.client.get_object,
                          'workflows', 'nonexist')

    @test.attr(type='negative')
    @decorators.idempotent_id('6b917213-7f11-423a-8fe0-55795dcf0fb2')
    def test_double_create_workflows(self):
        self.useFixture(lockutils.LockFixture('mistral-workflow'))
        _, body = self.client.create_workflow('wf_v2.yaml')
        self.assertRaises(exceptions.Conflict,
                          self.client.create_workflow,
                          'wf_v2.yaml')

    @test.attr(type='negative')
    @decorators.idempotent_id('ffcd63d2-1104-4320-a67b-fadc4e2a0631')
    def test_create_wf_with_invalid_def(self):
        self.assertRaises(exceptions.BadRequest,
                          self.client.create_workflow,
                          'wb_v1.yaml')

    @test.attr(type='negative')
    @decorators.idempotent_id('eed46931-5485-436c-810f-1f63362223b9')
    def test_update_wf_with_invalid_def(self):
        self.assertRaises(exceptions.BadRequest,
                          self.client.update_request,
                          'workflows', 'wb_v1.yaml')

    @test.attr(type='negative')
    @decorators.idempotent_id('9b7f5b5a-cacd-4f98-a35a-decf065b8234')
    def test_delete_wf_with_trigger_associate(self):
        tr_name = 'trigger'
        resp, body = self.client.create_workflow('wf_v2.yaml')
        name = body['workflows'][0]['name']
        resp, body = self.client.create_cron_trigger(
            tr_name, name, None, '5 * * * *')

        try:
            self.assertRaises(
                exceptions.BadRequest,
                self.client.delete_obj,
                'workflows',
                name
            )
        finally:
            self.client.delete_obj('cron_triggers', tr_name)
            self.client.triggers.remove(tr_name)

    @test.attr(type='negative')
    @decorators.idempotent_id('46325022-cbd2-48f3-95f3-e587aab3b655')
    def test_delete_wf_with_event_trigger_associate(self):
        _, body = self.client.create_workflow('wf_v2.yaml')
        wf_id = body['workflows'][0]['id']
        resp, body = self.client.create_event_trigger(
            wf_id, 'openstack', 'notification', 'fake.event')
        self.assertEqual(201, resp.status)

        try:
            self.assertRaises(
                exceptions.BadRequest,
                self.client.delete_obj,
                'workflows',
                wf_id
            )
        finally:
            self.client.delete_obj('event_triggers', body['id'])
            self.client.event_triggers.remove(body['id'])

    @test.attr(type='negative')
    @decorators.idempotent_id('1cb929e6-d375-4dcb-ab7c-73aa205af896')
    def test_delete_wf_with_trigger_associate_in_other_tenant(self):
        self.useFixture(lockutils.LockFixture('mistral-workflow'))
        tr_name = 'trigger'
        _, body = self.client.create_workflow('wf_v2.yaml', scope='public')
        name = body['workflows'][0]['name']
        resp, body = self.alt_client.create_cron_trigger(
            tr_name,
            name,
            None,
            '5 * * * *'
        )

        try:
            exception = self.assertRaises(
                exceptions.BadRequest,
                self.client.delete_obj,
                'workflows',
                name
            )

            self.assertIn(
                "Can't delete workflow that has cron triggers associated",
                exception.resp_body['faultstring']
            )
        finally:
            self.alt_client.delete_obj('cron_triggers', tr_name)
            self.alt_client.triggers.remove(tr_name)

    @test.attr(type='negative')
    @decorators.idempotent_id('f575713b-27fd-4ec8-b84f-468a7adf5ed2')
    def test_delete_nonexistent_wf(self):
        self.assertRaises(exceptions.NotFound,
                          self.client.delete_obj,
                          'workflows', 'nonexist')
