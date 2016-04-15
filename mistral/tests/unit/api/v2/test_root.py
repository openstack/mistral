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
from oslo_serialization import jsonutils

from mistral.tests.unit.api import base
from mistral.tests.unit.api import test_auth


class TestRootController(base.APITest):
    def test_index(self):
        resp = self.app.get('/', headers={'Accept': 'application/json'})

        self.assertEqual(200, resp.status_int)

        data = jsonutils.loads(resp.body.decode())

        self.assertEqual('v2.0', data[0]['id'])
        self.assertEqual('CURRENT', data[0]['status'])
        self.assertEqual(
            {'href': 'http://localhost/v2', 'target': 'v2'},
            data[0]['link']
        )

    def test_v2_root(self):
        resp = self.app.get('/v2/', headers={'Accept': 'application/json'})

        self.assertEqual(200, resp.status_int)

        data = jsonutils.loads(resp.body.decode())

        self.assertEqual(
            'http://localhost/v2',
            data['uri']
        )


class TestRootControllerWithAuth(test_auth.TestKeystoneMiddleware):
    def test_index(self):
        resp = self.app.get('/', headers={'Accept': 'application/json'})

        self.assertEqual(200, resp.status_int)

        data = jsonutils.loads(resp.body.decode())

        self.assertEqual('v2.0', data[0]['id'])
        self.assertEqual('CURRENT', data[0]['status'])
        self.assertEqual(
            {'href': 'http://localhost/v2', 'target': 'v2'},
            data[0]['link']
        )

    def test_v2_root(self):
        resp = self.app.get('/v2/', headers={'Accept': 'application/json'})

        self.assertEqual(200, resp.status_int)

        data = jsonutils.loads(resp.body.decode())

        self.assertEqual(
            'http://localhost/v2',
            data['uri']
        )
