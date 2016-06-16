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

from mistral_tempest_tests.tests import base


LOG = logging.getLogger(__name__)


class WorkbookTestsV2(base.TestCase):

    _service = 'workflowv2'

    def tearDown(self):
        for wf in self.client.workflows:
            self.client.delete_obj('workflows', wf)
        self.client.workflows = []

        super(WorkbookTestsV2, self).tearDown()

    @test.attr(type='smoke')
    def test_get_list_workbooks(self):
        resp, body = self.client.get_list_obj('workbooks')

        self.assertEqual(200, resp.status)
        self.assertEqual([], body['workbooks'])

    @test.attr(type='sanity')
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
        self.assertEqual([], body['workbooks'])

    @test.attr(type='sanity')
    def test_get_workbook(self):
        self.useFixture(lockutils.LockFixture('mistral-workflow'))
        _, body = self.client.create_workbook('wb_v2.yaml')
        name = body['name']

        resp, body = self.client.get_object('workbooks', name)
        self.assertEqual(200, resp.status)
        self.assertEqual(name, body['name'])

    @test.attr(type='sanity')
    def test_update_workbook(self):
        self.useFixture(lockutils.LockFixture('mistral-workflow'))
        _, body = self.client.create_workbook('wb_v2.yaml')
        name = body['name']
        resp, body = self.client.update_request('workbooks', 'wb_v2.yaml')

        self.assertEqual(200, resp.status)
        self.assertEqual(name, body['name'])

    @test.attr(type='sanity')
    def test_get_workbook_definition(self):
        self.useFixture(lockutils.LockFixture('mistral-workflow'))
        _, body = self.client.create_workbook('wb_v2.yaml')
        name = body['name']
        resp, body = self.client.get_definition('workbooks', name)

        self.assertEqual(200, resp.status)
        self.assertIsNotNone(body)

    @test.attr(type='negative')
    def test_get_nonexistent_workbook_definition(self):
        self.assertRaises(exceptions.NotFound,
                          self.client.get_definition,
                          'workbooks', 'nonexist')

    @test.attr(type='negative')
    def test_get_nonexistent_workbook(self):
        self.assertRaises(exceptions.NotFound, self.client.get_object,
                          'workbooks', 'nonexist')

    @test.attr(type='negative')
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

        self.assertEqual([], body['workbooks'])

    @test.attr(type='negative')
    def test_create_wb_with_invalid_def(self):
        self.assertRaises(
            exceptions.BadRequest,
            self.client.create_workbook,
            'wb_v1.yaml'
        )

    @test.attr(type='negative')
    def test_update_wb_with_invalid_def(self):
        self.assertRaises(
            exceptions.BadRequest,
            self.client.update_request,
            'workbooks',
            'wb_v1.yaml'
        )
