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

from mistral.tests.api import base
from mistral.db import api as db_api

# TODO: later we need additional tests verifying all the errors etc.

LISTENERS = [
    {
        'id': "1",
        'workbook_name': "my_workbook",
        'description': "My cool Mistral workbook",
        'webhook': "http://my.website.org"
    }
]


class TestListenersController(base.FunctionalTest):
    def setUp(self):
        super(TestListenersController, self).setUp()
        self.listener_get = db_api.listener_get
        self.listener_update = db_api.listener_update
        self.listener_create = db_api.listener_create
        self.listeners_get = db_api.listeners_get

    def tearDown(self):
        super(TestListenersController, self).tearDown()
        db_api.listener_get = self.listener_get
        db_api.listener_update = self.listener_update
        db_api.listener_create = self.listener_create
        db_api.listeners_get = self.listeners_get

    def test_get(self):
        db_api.listener_get = mock.MagicMock(return_value=LISTENERS[0])

        resp = self.app.get('/v1/workbooks/my_workbook/listeners/1')

        self.assertEqual(resp.status_int, 200)
        self.assertDictEqual(LISTENERS[0], resp.json)

    def test_put(self):
        updated_lsnr = LISTENERS[0].copy()
        updated_lsnr['description'] = 'new description'

        db_api.listener_update = mock.MagicMock(return_value=updated_lsnr)

        resp = self.app.put_json('/v1/workbooks/my_workbook/listeners/1',
                                 dict(description='new description'))

        self.assertEqual(resp.status_int, 200)
        self.assertDictEqual(updated_lsnr, resp.json)

    def test_post(self):
        db_api.listener_create = mock.MagicMock(return_value=LISTENERS[0])

        resp = self.app.post_json('/v1/workbooks/my_workbook/listeners',
                                  LISTENERS[0])

        self.assertEqual(resp.status_int, 201)
        self.assertDictEqual(LISTENERS[0], resp.json)

    def test_delete(self):
        resp = self.app.delete('/v1/workbooks/my_workbook/listeners/1')

        self.assertEqual(resp.status_int, 204)

    def test_get_all(self):
        db_api.listeners_get = mock.MagicMock(return_value=LISTENERS)

        resp = self.app.get('/v1/workbooks/my_workbook/listeners')

        self.assertEqual(resp.status_int, 200)

        self.assertEqual(len(resp.json), 1)
        self.assertDictEqual(LISTENERS[0], resp.json['listeners'][0])
