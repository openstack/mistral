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


class WorkflowTestsV2(base.TestCase):

    _service = 'workflowv2'

    def tearDown(self):
        for wf in self.client.workflows:
            self.client.delete_obj('workflows', wf)
        self.client.workflows = []

        super(WorkflowTestsV2, self).tearDown()

    @test.attr(type='smoke')
    def test_get_list_workflows(self):
        resp, body = self.client.get_list_obj('workflows')
        self.assertEqual(200, resp.status)

        names = [wf['name'] for wf in body['workflows']]

        self.assertIn('std.create_instance', names)

        self.assertNotIn('next', body)

    @test.attr(type='smoke')
    def test_get_list_workflows_with_fields(self):
        resp, body = self.client.get_list_obj('workflows?fields=name')

        self.assertEqual(200, resp.status)

        for wf in body['workflows']:
            self.assertListEqual(sorted(['id', 'name']), sorted(list(wf)))

    @test.attr(type='smoke')
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
    def test_get_workflow(self):
        self.useFixture(lockutils.LockFixture('mistral-workflow'))
        _, body = self.client.create_workflow('wf_v2.yaml')
        name = body['workflows'][0]['name']

        resp, body = self.client.get_object('workflows', name)

        self.assertEqual(200, resp.status)
        self.assertEqual(name, body['name'])

    @test.attr(type='sanity')
    def test_update_workflow(self):
        self.useFixture(lockutils.LockFixture('mistral-workflow'))
        _, body = self.client.create_workflow('wf_v2.yaml')
        name = body['workflows'][0]['name']

        resp, body = self.client.update_request('workflows', 'wf_v2.yaml')

        self.assertEqual(200, resp.status)
        self.assertEqual(name, body['workflows'][0]['name'])

    @test.attr(type='sanity')
    def test_get_workflow_definition(self):
        self.useFixture(lockutils.LockFixture('mistral-workflow'))
        _, body = self.client.create_workflow('wf_v2.yaml')
        name = body['workflows'][0]['name']

        resp, body = self.client.get_definition('workflows', name)

        self.assertEqual(200, resp.status)
        self.assertIsNotNone(body)

    @test.attr(type='sanity')
    def test_get_workflow_uploaded_in_wb(self):
        self.useFixture(lockutils.LockFixture('mistral-workflow'))
        _, body = self.client.create_workbook('wb_v2.yaml')
        wb_name = body['name']

        _, body = self.client.get_list_obj('workflows')
        wf_names = [wf['name'] for wf in body['workflows']
                    if wf['name'].startswith(wb_name)]

        self.assertNotEmpty(wf_names)

    @test.attr(type='negative')
    def test_get_nonexistent_workflow_definition(self):
        self.assertRaises(exceptions.NotFound,
                          self.client.get_definition,
                          'workflows', 'nonexist')

    @test.attr(type='negative')
    def test_get_nonexistent_workflow(self):
        self.assertRaises(exceptions.NotFound, self.client.get_object,
                          'workflows', 'nonexist')

    @test.attr(type='negative')
    def test_double_create_workflows(self):
        self.useFixture(lockutils.LockFixture('mistral-workflow'))
        _, body = self.client.create_workflow('wf_v2.yaml')
        self.assertRaises(exceptions.Conflict,
                          self.client.create_workflow,
                          'wf_v2.yaml')

    @test.attr(type='negative')
    def test_create_wf_with_invalid_def(self):
        self.assertRaises(exceptions.BadRequest,
                          self.client.create_workflow,
                          'wb_v1.yaml')

    @test.attr(type='negative')
    def test_update_wf_with_invalid_def(self):
        self.assertRaises(exceptions.BadRequest,
                          self.client.update_request,
                          'workflows', 'wb_v1.yaml')

    @test.attr(type='negative')
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
    def test_delete_nonexistent_wf(self):
        self.assertRaises(exceptions.NotFound,
                          self.client.delete_obj,
                          'workflows', 'nonexist')
