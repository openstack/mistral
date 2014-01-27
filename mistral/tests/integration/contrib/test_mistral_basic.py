# vim: tabstop=4 shiftwidth=4 softtabstop=4

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

import testtools
from tempest.api.mistral import base
from tempest.test import attr
from tempest import exceptions


class SanityTests(base.MistralTest):

    @attr(type='smoke')
    def test_check_base_url(self):
        resp, _ = self.check_base_url()
        self.assertEqual(resp['status'], '200')

    @attr(type='smoke')
    def test_get_list_obj(self):
        resp, _ = self.check_base_url_with_version()
        self.assertEqual(resp['status'], '200')

    @attr(type='smoke')
    def test_get_list_workbooks(self):
        resp, body = self.get_list_obj('workbooks')

        self.assertEqual(resp['status'], '200')
        self.assertEqual(body['workbooks'], [])

    @attr(type='smoke')
    def test_get_workbook(self):
        self.create_obj('workbooks', 'test')
        self.obj.append(['workbooks', 'test'])
        resp, body = self.get_list_obj('workbooks/test')

        self.assertEqual(resp['status'], '200')
        self.assertEqual(body['name'], 'test')

    @attr(type='smoke')
    def test_get_executions(self):
        self.create_obj('workbooks', 'test')
        self.obj.append(['workbooks', 'test'])
        resp, body = self.get_list_obj('workbooks/test/executions')

        self.assertEqual(resp['status'], '200')
        self.assertEqual(body['executions'], [])

    @attr(type='smoke')
    def test_create_and_delete_workbook(self):
        resp, body = self.create_obj('workbooks', 'test')
        self.obj.append(['workbooks', 'test'])

        self.assertEqual(resp['status'], '201')
        self.assertEqual(body['name'], 'test')

        resp, body = self.get_list_obj('workbooks')

        self.assertEqual(resp['status'], '200')
        self.assertEqual(body['workbooks'][0]['name'], 'test')

        self.delete_obj('workbooks', 'test')
        _, body = self.get_list_obj('workbooks')

        self.assertEqual(body['workbooks'], [])

    @attr(type='smoke')
    def test_update_workbook(self):
        self.create_obj('workbooks', 'test')
        self.obj.append(['workbooks', 'test'])
        resp, body = self.update_obj('workbooks', 'test')

        self.assertEqual(resp['status'], '200')
        self.assertEqual(body['name'], 'testupdated')

        self.obj.append(['workbooks', 'testupdated'])

    @attr(type='smoke')
    def test_get_workbook_definition(self):
        self.create_obj('workbooks', 'test')
        self.obj.append(['workbooks', 'test'])
        resp, body = self.get_workbook_definition('test')

        self.assertEqual(resp['status'], '200')
        self.assertIsNotNone(body)

    @testtools.skip('It is not implemented')
    @attr(type='smoke')
    def test_upload_workbook_definition(self):
        self.create_obj('workbooks', 'test1')
        self.obj.append(['workbooks', 'test1'])
        resp, body = self.upload_workbook_definition('test1')

        self.assertEqual(resp['status'], '200')

    @attr(type='negative')
    def test_double_create_obj(self):
        self.create_obj('workbooks', 'test')
        self.obj.append(['workbooks', 'test'])

        self.assertRaises(exceptions.BadRequest, self.create_obj, 'workbooks',
                          'test')

        self.delete_obj('workbooks', 'test')
        _, body = self.get_list_obj('workbooks')

        self.assertEqual(body['workbooks'], [])
