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
from mistralclient.tests import base

# TODO: later we need additional tests verifying all the errors etc.

WORKBOOKS = [
    {
        'name': "my_workbook",
        'description': "My cool Mistral workbook",
        'tags': ['deployment', 'demo']
    }
]

WB_DEF = """
Service:
   name: my_service
   type: REST
   parameters:
       baseUrl: http://my.service.org
   actions:
       action1:
         parameters:
             url: servers
             method: POST
         task-parameters:
            param1:
              optional: false
            param2:
              optional: false
Workflow:
   tasks:
     task1:
         action: my_service:create-vm
         parameters:
            param1: 1234
            param2: 42
"""


class TestWorkbooks(base.BaseClientTest):
    def test_create(self):
        self.mock_http_post(json=WORKBOOKS[0])

        wb = self.workbooks.create(WORKBOOKS[0]['name'],
                                   WORKBOOKS[0]['description'],
                                   WORKBOOKS[0]['tags'])

        self.assertIsNotNone(wb)
        self.assertEqual(WORKBOOKS[0]['name'], wb.name)
        self.assertEqual(WORKBOOKS[0]['description'], wb.description)
        self.assertEqual(WORKBOOKS[0]['tags'], wb.tags)

    def test_update(self):
        self.mock_http_put(json=WORKBOOKS[0])

        wb = self.workbooks.update(WORKBOOKS[0]['name'],
                                   WORKBOOKS[0]['description'],
                                   WORKBOOKS[0]['tags'])

        self.assertIsNotNone(wb)
        self.assertEqual(WORKBOOKS[0]['name'], wb.name)
        self.assertEqual(WORKBOOKS[0]['description'], wb.description)
        self.assertEqual(WORKBOOKS[0]['tags'], wb.tags)

    def test_list(self):
        self.mock_http_get(json={'workbooks': WORKBOOKS})

        workbooks = self.workbooks.list()

        self.assertEqual(1, len(workbooks))

        wb = workbooks[0]

        self.assertEqual(WORKBOOKS[0]['name'], wb.name)
        self.assertEqual(WORKBOOKS[0]['description'], wb.description)
        self.assertEqual(WORKBOOKS[0]['tags'], wb.tags)

    def test_get(self):
        self.mock_http_get(json=WORKBOOKS[0])

        wb = self.workbooks.get(WORKBOOKS[0]['name'])

        self.assertIsNotNone(wb)
        self.assertEqual(WORKBOOKS[0]['name'], wb.name)
        self.assertEqual(WORKBOOKS[0]['description'], wb.description)
        self.assertEqual(WORKBOOKS[0]['tags'], wb.tags)

    def test_delete(self):
        self.mock_http_delete(status_code=204)

        # Just make sure it doesn't throw any exceptions.
        self.workbooks.delete(WORKBOOKS[0]['name'])

    def test_upload_definition(self):
        self.mock_http_put(None, status_code=200)

        # Just make sure it doesn't throw any exceptions.
        self.workbooks.upload_definition("my_workbook", WB_DEF)

    def test_get_definition(self):
        self._client.http_client.get =\
            mock.MagicMock(return_value=base.FakeResponse(200, None, WB_DEF))

        text = self.workbooks.get_definition("my_workbook")

        self.assertEqual(WB_DEF, text)
