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


class TestWorkbooksController(base.FunctionalTest):
    def test_get(self):
        db_api.workbook_get = mock.MagicMock(return_value=WORKBOOKS[0])

        resp = self.app.get('/v1/workbooks/my_workbook')

        self.assertEqual(resp.status_int, 200)
        self.assertDictEqual(WORKBOOKS[0], resp.json)

    def test_put(self):
        updated_workbook = WORKBOOKS[0].copy()
        updated_workbook['description'] = 'new description'

        db_api.workbook_update = mock.MagicMock(return_value=updated_workbook)

        resp = self.app.put_json('/v1/workbooks/my_workbook',
                                 dict(description='new description'))

        self.assertEqual(resp.status_int, 200)
        self.assertDictEqual(updated_workbook, resp.json)

    def test_post(self):
        db_api.workbook_create = mock.MagicMock(return_value=WORKBOOKS[0])

        resp = self.app.post_json('/v1/workbooks', WORKBOOKS[0])

        self.assertEqual(resp.status_int, 201)
        self.assertDictEqual(WORKBOOKS[0], resp.json)

    def test_delete(self):
        db_api.workbook_delete = mock.MagicMock(return_value=None)
        resp = self.app.delete('/v1/workbooks/my_workbook')

        self.assertEqual(resp.status_int, 204)

    def test_get_all(self):
        db_api.workbooks_get = mock.MagicMock(return_value=WORKBOOKS)

        resp = self.app.get('/v1/workbooks')

        self.assertEqual(resp.status_int, 200)

        self.assertEqual(len(resp.json), 1)
        self.assertDictEqual(WORKBOOKS[0], resp.json['workbooks'][0])
