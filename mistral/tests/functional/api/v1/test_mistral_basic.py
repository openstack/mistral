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


class SanityTests(base.TestCase):

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
    def test_get_workbook(self):
        self.client.create_workbook('test')
        resp, body = self.client.get_list_obj('workbooks/test')

        self.assertEqual(200, resp.status)
        self.assertEqual('test', body['name'])

    @test.attr(type='smoke')
    def test_get_executions(self):
        self.client.create_workbook('test')
        resp, body = self.client.get_list_obj('workbooks/test/executions')

        self.assertEqual(200, resp.status)
        self.assertEqual([], body['executions'])

    @test.attr(type='smoke')
    def test_create_and_delete_workbook(self):
        resp, body = self.client.create_workbook('test')

        self.assertEqual(201, resp.status)
        self.assertEqual('test', body['name'])

        resp, body = self.client.get_list_obj('workbooks')

        self.assertEqual(200, resp.status)
        self.assertEqual('test', body['workbooks'][0]['name'])

        self.client.delete_workbook('test')
        _, body = self.client.get_list_obj('workbooks')

        self.assertEqual([], body['workbooks'])

    @test.attr(type='smoke')
    def test_update_workbook(self):
        self.client.create_workbook('test')
        resp, body = self.client.update_obj('workbooks', 'test')

        self.assertEqual(200, resp.status)
        self.assertEqual('testupdated', body['name'])

    @test.attr(type='smoke')
    def test_get_workbook_definition(self):
        self.client.create_workbook('test')
        text = base.get_resource('resources/hello.yaml')
        self.client.upload_workbook_definition(
            'test', text)
        resp, body = self.client.get_workbook_definition('test')

        self.assertEqual(200, resp.status)
        self.assertIsNotNone(body)

    @test.attr(type='smoke')
    def test_upload_workbook_definition(self):
        self.client.create_workbook('test1')
        text = base.get_resource('resources/hello.yaml')
        resp, body = self.client.upload_workbook_definition(
            'test1', text)

        self.assertEqual(200, resp.status)
        self.assertIsNotNone(body)

    @test.attr(type='negative')
    def test_double_create_obj(self):
        self.client.create_workbook('test')

        self.assertRaises(exceptions.Conflict, self.client.create_workbook,
                          'test')

        self.client.delete_workbook('test')
        _, body = self.client.get_list_obj('workbooks')

        self.assertEqual([], body['workbooks'])

    @test.attr(type='negative')
    def test_get_nonexistent_workbook_definition(self):
        self.assertRaises(exceptions.NotFound,
                          self.client.get_workbook_definition,
                          'fksn')

    @test.attr(type='negative')
    def test_get_executions_list_from_nonexistent_workbook(self):
        self.assertRaises(exceptions.NotFound, self.client.get_list_obj,
                          'workbooks/nonexistentworkbook/executions')


class AdvancedTests(base.TestCaseAdvanced):
    def setUp(self):
        super(AdvancedTests, self).setUp()

        wb = base.get_resource('resources/hello.yaml')
        self.client.upload_workbook_definition('test', wb)

    @test.attr(type='positive')
    def test_create_execution(self):
        resp, body = self.client.create_execution_wait_success(
            'test', '', 'hello')

        self.assertEqual(201, resp.status)
        self.assertEqual('test', body["workbook_name"])

    @test.attr(type='positive')
    def test_get_execution(self):
        _, execution = self.client.create_execution_wait_success('test', '',
                                                                 'hello')

        resp, body = self.client.get_execution('test', execution['id'])

        body = json.loads(body)
        del execution['state']
        del body['state']

        self.assertEqual(200, resp.status)
        self.assertEqual(execution, body)

    @test.attr(type='positive')
    def test_update_execution(self):
        _, execution = self.client.create_execution_wait_success('test', '',
                                                                 'hello')

        resp, body = self.client.update_execution(
            'test', execution['id'], '{}')

        body = json.loads(body)
        del execution['state']
        del body['state']

        self.assertEqual(200, resp.status)
        self.assertEqual(execution, body)

    @test.attr(type='positive')
    def test_get_tasks_list(self):
        _, execution = self.client.create_execution_wait_success('test', '',
                                                                 'hello')

        resp, tasks = self.client.get_tasks_list('test', execution['id'])

        self.assertEqual(200, resp.status)
        for task in tasks:
            self.assertEqual(execution['id'], task['execution_id'])
            self.assertEqual('test', task['workbook_name'])

    @test.attr(type='positive')
    def test_get_task(self):
        _, execution = self.client.create_execution_wait_success('test', '',
                                                                 'hello')

        _, tasks = self.client.get_tasks_list('test', execution['id'])

        resp, task = self.client.get_task('test', execution['id'],
                                          tasks[0]['id'])

        del tasks[0]['state']
        del task['state']

        self.assertEqual(200, resp.status)
        self.assertEqual(tasks[0], task)

    @test.attr(type='negative')
    def test_create_execution_in_nonexistent_workbook(self):
        self.assertRaises(exceptions.NotFound,
                          self.client.create_execution_wait_success,
                          'nonexistentworkbook', '', 'catchme')

    def test_get_nonexistent_execution(self):
        self.assertRaises(exceptions.NotFound, self.client.get_execution,
                          'test', str(uuid.uuid4()))

    @test.attr(type='negative')
    def test_update_nonexistent_execution(self):
        id = str(uuid.uuid4())
        put_body = {
            "id": id,
            "state": "STOPPED"
        }

        self.assertRaises(exceptions.NotFound, self.client.update_execution,
                          'test', id, put_body)

    @test.attr(type='negative')
    def test_get_tasks_list_of_nonexistent_execution(self):
        self.assertRaises(exceptions.NotFound, self.client.get_tasks_list,
                          'test', str(uuid.uuid4()))


class AdvancedNegativeTestsWithExecutionCreate(base.TestCaseAdvanced):
    def setUp(self):
        super(AdvancedNegativeTestsWithExecutionCreate, self).setUp()
        wb = base.get_resource('resources/hello.yaml')
        self.client.upload_workbook_definition('test', wb)
        _, self.execution = self.client.create_execution_wait_success(
            'test', '', 'hello')

    @test.attr(type='negative')
    def test_get_nonexistent_task(self):
        self.assertRaises(exceptions.NotFound, self.client.get_task,
                          'test', self.execution['id'], str(uuid.uuid4()))

    @test.attr(type='negative')
    def test_update_nonexistent_task(self):
        id = str(uuid.uuid4())
        put_body = {
            "id": id,
            "state": "ERROR"
        }

        self.assertRaises(exceptions.NotFound, self.client.update_task,
                          'test', self.execution['id'], str(uuid.uuid4()),
                          put_body)
