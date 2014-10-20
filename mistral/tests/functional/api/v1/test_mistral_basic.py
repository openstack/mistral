# Copyright 2013 Mirantis, Inc.
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
import uuid

from tempest import exceptions
from tempest import test

from mistral.tests.functional import base


class WorkbookTestsV1(base.TestCase):

    _version = 1

    @test.attr(type='smoke')
    def test_get_list_obj(self):
        resp, _ = self.client.get_list_obj('')
        self.assertEqual(200, resp.status)

    @test.attr(type='smoke')
    def test_get_list_workbooks(self):
        resp, body = self.client.get_list_obj('workbooks')

        self.assertEqual(200, resp.status)
        self.assertEqual([], body['workbooks'])

    @test.attr(type='smoke')
    def test_create_and_delete_workbook(self):
        resp, body = self.client.create_workbook('test')

        self.assertEqual(201, resp.status)
        self.assertEqual('test', body['name'])

        resp, body = self.client.get_list_obj('workbooks')

        self.assertEqual(200, resp.status)
        self.assertEqual('test', body['workbooks'][0]['name'])

        self.client.delete_obj('workbooks', 'test')
        self.client.workbooks.remove('test')

        _, body = self.client.get_list_obj('workbooks')

        self.assertEqual([], body['workbooks'])

    @test.attr(type='smoke')
    def test_get_workbook(self):
        self.client.create_workbook('test')
        resp, body = self.client.get_list_obj('workbooks/test')

        self.assertEqual(200, resp.status)
        self.assertEqual('test', body['name'])

    @test.attr(type='smoke')
    def test_update_workbook(self):
        self.client.create_workbook('test')
        resp, body = self.client.update_workbook('test')

        self.assertEqual(200, resp.status)
        self.assertEqual('test', body['name'])

    @test.attr(type='smoke')
    def test_get_workbook_definition(self):
        self.client.create_workbook('test')
        self.client.upload_workbook_definition('test')
        resp, body = self.client.get_workbook_definition('test')

        self.assertEqual(200, resp.status)
        self.assertIsNotNone(body)

    @test.attr(type='smoke')
    def test_upload_workbook_definition(self):
        self.client.create_workbook('test1')
        resp, body = self.client.upload_workbook_definition(
            'test1')

        self.assertEqual(200, resp.status)
        self.assertIsNotNone(body)

    @test.attr(type='negative')
    def test_get_nonexistent_workbook_definition(self):
        self.assertRaises(exceptions.NotFound,
                          self.client.get_workbook_definition,
                          'nonexist')

    @test.attr(type='negative')
    def test_get_nonexistent_workbook(self):
        self.assertRaises(exceptions.NotFound, self.client.get_object,
                          'workbooks', 'nonexist')

    @test.attr(type='negative')
    def test_double_create_obj(self):
        self.client.create_workbook('test')

        self.assertRaises(exceptions.Conflict, self.client.create_workbook,
                          'test')

        self.client.delete_obj('workbooks', 'test')
        self.client.workbooks.remove('test')
        _, body = self.client.get_list_obj('workbooks')

        self.assertEqual([], body['workbooks'])


class ExecutionTestsV1(base.TestCase):

    _version = 1

    def setUp(self):
        super(ExecutionTestsV1, self).setUp()

        self.client.create_workbook('test')
        self.client.upload_workbook_definition('test')
        self.entity_type = 'workbook_name'
        self.entity_name = 'test'

    def tearDown(self):
        super(ExecutionTestsV1, self).tearDown()

        for ex in self.client.executions:
            self.client.delete_obj('executions', ex)
        self.client.executions = []

    @test.attr(type='positive')
    def test_create_execution(self):
        resp, body = self.client.create_execution(self.entity_name)

        self.assertEqual(201, resp.status)
        self.assertEqual(self.entity_name, body[self.entity_type])

    @test.attr(type='positive')
    def test_get_execution(self):
        _, execution = self.client.create_execution(self.entity_name)

        resp, body = self.client.get_object('executions', execution['id'])

        del execution['state']
        del body['state']

        self.assertEqual(200, resp.status)
        self.assertEqual(execution['id'], body['id'])

    @test.attr(type='positive')
    def test_update_execution(self):
        _, execution = self.client.create_execution(self.entity_name)

        resp, body = self.client.update_execution(
            execution['id'], '{}')

        body = json.loads(body)
        del execution['state']
        del body['state']

        self.assertEqual(200, resp.status)
        self.assertEqual(execution['id'], body['id'])

    @test.attr(type='negative')
    def test_get_nonexistent_execution(self):
        self.assertRaises(exceptions.NotFound, self.client.get_object,
                          'executions', str(uuid.uuid4()))

    @test.attr(type='negative')
    def test_update_nonexistent_execution(self):
        id = str(uuid.uuid4())
        put_body = {
            "state": "STOPPED"
        }

        self.assertRaises(exceptions.NotFound, self.client.update_execution,
                          id, put_body)
