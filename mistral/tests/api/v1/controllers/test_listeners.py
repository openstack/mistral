# -*- coding: utf-8 -*-
#
# Copyright 2013 - Mirantis, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

import mock

from mistral.db import api as db_api
from mistral import exceptions
from mistral.tests.api import base

LISTENERS = [
    {
        'id': "1",
        'workbook_name': "my_workbook",
        'description': "My cool Mistral workbook",
        'webhook': "http://my.website.org"
    }
]

UPDATED_LSNR = LISTENERS[0].copy()
UPDATED_LSNR['description'] = 'new description'


class TestListenersController(base.FunctionalTest):
    @mock.patch.object(db_api, "listener_get",
                       mock.MagicMock(return_value=LISTENERS[0]))
    def test_get(self):
        resp = self.app.get('/v1/workbooks/my_workbook/listeners/1')

        self.assertEqual(resp.status_int, 200)
        self.assertDictEqual(LISTENERS[0], resp.json)

    @mock.patch.object(db_api, "listener_get",
                       mock.MagicMock(
                           side_effect=exceptions.NotFoundException()))
    def test_get_not_found(self):
        resp = self.app.get('/v1/workbooks/my_workbook/listeners/1',
                            expect_errors=True)

        self.assertEqual(resp.status_int, 404)

    @mock.patch.object(db_api, "listener_update",
                       mock.MagicMock(return_value=UPDATED_LSNR))
    def test_put(self):
        resp = self.app.put_json('/v1/workbooks/my_workbook/listeners/1',
                                 dict(description='new description'))

        self.assertEqual(resp.status_int, 200)
        self.assertDictEqual(UPDATED_LSNR, resp.json)

    @mock.patch.object(db_api, "listener_update",
                       mock.MagicMock(
                           side_effect=exceptions.NotFoundException()))
    def test_put_not_found(self):
        resp = self.app.put_json('/v1/workbooks/my_workbook/listeners/1',
                                 dict(description='new description'),
                                 expect_errors=True)

        self.assertEqual(resp.status_int, 404)

    @mock.patch.object(db_api, "listener_create",
                       mock.MagicMock(return_value=LISTENERS[0]))
    def test_post(self):
        resp = self.app.post_json('/v1/workbooks/my_workbook/listeners',
                                  LISTENERS[0])

        self.assertEqual(resp.status_int, 201)
        self.assertDictEqual(LISTENERS[0], resp.json)

    @mock.patch.object(db_api, "listener_delete",
                       mock.MagicMock(return_value=None))
    def test_delete(self):
        resp = self.app.delete('/v1/workbooks/my_workbook/listeners/1')

        self.assertEqual(resp.status_int, 204)

    @mock.patch.object(db_api, "listener_delete",
                       mock.MagicMock(
                           side_effect=exceptions.NotFoundException()))
    def test_delete_not_found(self):
        resp = self.app.delete('/v1/workbooks/my_workbook/listeners/1',
                               expect_errors=True)

        self.assertEqual(resp.status_int, 404)

    @mock.patch.object(db_api, "listeners_get",
                       mock.MagicMock(return_value=LISTENERS))
    def test_get_all(self):
        resp = self.app.get('/v1/workbooks/my_workbook/listeners')

        self.assertEqual(resp.status_int, 200)

        self.assertEqual(len(resp.json), 1)
        self.assertDictEqual(LISTENERS[0], resp.json['listeners'][0])
