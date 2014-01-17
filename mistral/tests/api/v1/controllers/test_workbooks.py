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

WORKBOOKS = [
    {
        'name': "my_workbook",
        'description': "My cool Mistral workbook",
        'tags': ['deployment', 'demo']
    }
]

UPDATED_WORKBOOK = WORKBOOKS[0].copy()
UPDATED_WORKBOOK['description'] = 'new description'


class TestWorkbooksController(base.FunctionalTest):
    @mock.patch.object(db_api, "workbook_get",
                       mock.MagicMock(return_value=WORKBOOKS[0]))
    def test_get(self):
        resp = self.app.get('/v1/workbooks/my_workbook')

        self.assertEqual(resp.status_int, 200)
        self.assertDictEqual(WORKBOOKS[0], resp.json)

    @mock.patch.object(db_api, "workbook_update",
                       mock.MagicMock(return_value=UPDATED_WORKBOOK))
    def test_put(self):
        resp = self.app.put_json('/v1/workbooks/my_workbook',
                                 dict(description='new description'))

        self.assertEqual(resp.status_int, 200)
        self.assertDictEqual(UPDATED_WORKBOOK, resp.json)

    @mock.patch.object(db_api, "workbook_create",
                       mock.MagicMock(return_value=WORKBOOKS[0]))
    @mock.patch("mistral.services.trusts.create_trust",
                mock.MagicMock(return_value=WORKBOOKS[0]))
    def test_post(self):
        resp = self.app.post_json('/v1/workbooks', WORKBOOKS[0])

        self.assertEqual(resp.status_int, 201)
        self.assertDictEqual(WORKBOOKS[0], resp.json)

    @mock.patch.object(db_api, "workbook_delete",
                       mock.MagicMock(return_value=None))
    def test_delete(self):
        resp = self.app.delete('/v1/workbooks/my_workbook')

        self.assertEqual(resp.status_int, 204)

    @mock.patch.object(db_api, "workbooks_get",
                       mock.MagicMock(return_value=WORKBOOKS))
    def test_get_all(self):
        resp = self.app.get('/v1/workbooks')

        self.assertEqual(resp.status_int, 200)

        self.assertEqual(len(resp.json), 1)
        self.assertDictEqual(WORKBOOKS[0], resp.json['workbooks'][0])
