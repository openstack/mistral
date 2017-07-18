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

from mistral_tempest_tests.tests import base


class WorkbookTestsV2(base.TestCase):

    _service = 'workflowv2'

    def tearDown(self):
        for wf in self.client.workflows:
            self.client.delete_obj('workflows', wf)
        self.client.workflows = []

        super(WorkbookTestsV2, self).tearDown()

    @decorators.attr(type='smoke')
    @decorators.idempotent_id('4d8752b9-8d69-4d81-8710-5dd8ef699b95')
    def test_get_list_workbooks(self):
        resp, body = self.client.get_list_obj('workbooks')

        self.assertEqual(200, resp.status)
        self.assertEmpty(body['workbooks'])

    @decorators.attr(type='sanity')
    @decorators.idempotent_id('1a078ca2-bcf9-4eb9-8ed5-e3545038aa76')
    def test_create_and_delete_workbook(self):
        self.useFixture(lockutils.LockFixture('mistral-workflow'))
        resp, body = self.client.create_workbook('wb_v2.yaml')
        name = body['name']
        self.assertEqual(201, resp.status)

        resp, body = self.client.get_list_obj('workbooks')
        self.assertEqual(200, resp.status)
        self.assertEqual(name, body['workbooks'][0]['name'])

        self.client.delete_obj('workbooks', name)
        self.client.workbooks.remove(name)

        _, body = self.client.get_list_obj('workbooks')
        self.assertEmpty(body['workbooks'])

    @decorators.attr(type='sanity')
    @decorators.idempotent_id('80f7d7a6-2821-4ab0-b090-ca45c98258ba')
    def test_get_workbook(self):
        self.useFixture(lockutils.LockFixture('mistral-workflow'))
        _, body = self.client.create_workbook('wb_v2.yaml')
        name = body['name']

        resp, body = self.client.get_object('workbooks', name)
        self.assertEqual(200, resp.status)
        self.assertEqual(name, body['name'])

    @decorators.attr(type='sanity')
    @decorators.idempotent_id('4d3b1e43-a493-41be-9c8a-389511675403')
    def test_update_workbook(self):
        self.useFixture(lockutils.LockFixture('mistral-workflow'))
        _, body = self.client.create_workbook('wb_v2.yaml')
        name = body['name']
        resp, body = self.client.update_request('workbooks', 'wb_v2.yaml')

        self.assertEqual(200, resp.status)
        self.assertEqual(name, body['name'])

    @decorators.attr(type='sanity')
    @decorators.idempotent_id('506cdcc2-082f-4e1f-9ab2-717acd7f0eb5')
    def test_get_workbook_definition(self):
        self.useFixture(lockutils.LockFixture('mistral-workflow'))
        _, body = self.client.create_workbook('wb_v2.yaml')
        name = body['name']
        resp, body = self.client.get_definition('workbooks', name)

        self.assertEqual(200, resp.status)
        self.assertIsNotNone(body)

    @decorators.attr(type='negative')
    @decorators.idempotent_id('d99f11c1-05a3-4d90-89c6-8d85558d3708')
    def test_get_nonexistent_workbook_definition(self):
        self.assertRaises(exceptions.NotFound,
                          self.client.get_definition,
                          'workbooks', 'nonexist')

    @decorators.attr(type='negative')
    @decorators.idempotent_id('61ed021e-ec56-42cb-ad05-eb6979aa00fd')
    def test_get_nonexistent_workbook(self):
        self.assertRaises(exceptions.NotFound, self.client.get_object,
                          'workbooks', 'nonexist')

    @decorators.attr(type='negative')
    @decorators.idempotent_id('e3d76f8b-220d-4250-8238-0ba27fda6de9')
    def test_double_create_workbook(self):
        self.useFixture(lockutils.LockFixture('mistral-workflow'))
        _, body = self.client.create_workbook('wb_v2.yaml')
        name = body['name']
        self.assertRaises(exceptions.Conflict,
                          self.client.create_workbook,
                          'wb_v2.yaml')

        self.client.delete_obj('workbooks', name)
        self.client.workbooks.remove(name)
        _, body = self.client.get_list_obj('workbooks')

        self.assertEmpty(body['workbooks'])

    @decorators.attr(type='negative')
    @decorators.idempotent_id('1cd6f6f7-b166-454e-96d2-bf1f95c23015')
    def test_create_wb_with_invalid_def(self):
        self.assertRaises(
            exceptions.BadRequest,
            self.client.create_workbook,
            'wb_v1.yaml'
        )

    @decorators.attr(type='negative')
    @decorators.idempotent_id('ac9a05d3-e285-4d88-91eb-fb9ad694a89a')
    def test_update_wb_with_invalid_def(self):
        self.assertRaises(
            exceptions.BadRequest,
            self.client.update_request,
            'workbooks',
            'wb_v1.yaml'
        )
