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

from mistralclient.tests import base

# TODO: later we need additional tests verifying all the errors etc.

LISTENERS = [
    {
        'id': "1",
        'workbook_name': "my_workbook",
        'description': "My cool Mistral workbook",
        'webhook': "http://my.website.org"
    }
]


class TestListeners(base.BaseClientTest):
    def test_create(self):
        self.mock_http_post(json=LISTENERS[0])

        lsnr = self.listeners.create(LISTENERS[0]['workbook_name'],
                                     LISTENERS[0]['webhook'],
                                     LISTENERS[0]['description'])

        self.assertIsNotNone(lsnr)
        self.assertEqual(LISTENERS[0]['id'], lsnr.id)
        self.assertEqual(LISTENERS[0]['workbook_name'], lsnr.workbook_name)
        self.assertEqual(LISTENERS[0]['webhook'], lsnr.webhook)
        self.assertEqual(LISTENERS[0]['description'], lsnr.description)

    def test_update(self):
        self.mock_http_put(json=LISTENERS[0])

        lsnr = self.listeners.update(LISTENERS[0]['workbook_name'],
                                     LISTENERS[0]['webhook'],
                                     LISTENERS[0]['description'])

        self.assertIsNotNone(lsnr)
        self.assertEqual(LISTENERS[0]['id'], lsnr.id)
        self.assertEqual(LISTENERS[0]['workbook_name'], lsnr.workbook_name)
        self.assertEqual(LISTENERS[0]['webhook'], lsnr.webhook)
        self.assertEqual(LISTENERS[0]['description'], lsnr.description)

    def test_list(self):
        self.mock_http_get(json={'listeners': LISTENERS})

        listeners = self.listeners.list(LISTENERS[0]['workbook_name'])

        self.assertEqual(1, len(listeners))

        lsnr = listeners[0]

        self.assertEqual(LISTENERS[0]['id'], lsnr.id)
        self.assertEqual(LISTENERS[0]['workbook_name'], lsnr.workbook_name)
        self.assertEqual(LISTENERS[0]['webhook'], lsnr.webhook)
        self.assertEqual(LISTENERS[0]['description'], lsnr.description)

    def test_get(self):
        self.mock_http_get(json=LISTENERS[0])

        lsnr = self.listeners.get(LISTENERS[0]['workbook_name'],
                                  LISTENERS[0]['id'])

        self.assertEqual(LISTENERS[0]['id'], lsnr.id)
        self.assertEqual(LISTENERS[0]['workbook_name'], lsnr.workbook_name)
        self.assertEqual(LISTENERS[0]['webhook'], lsnr.webhook)
        self.assertEqual(LISTENERS[0]['description'], lsnr.description)

    def test_delete(self):
        self.mock_http_delete(status_code=204)

        # Just make sure it doesn't throw any exceptions.
        self.listeners.delete(LISTENERS[0]['workbook_name'],
                              LISTENERS[0]['id'])
