# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2013 Mirantis, Inc.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import tempest.test
import json
from tempest.common import rest_client
import os
import tempest.api.mistral.config as cfg


class MistralTest(tempest.test.BaseTestCase):

    @classmethod
    def setUpClass(cls):
        """
            This method allows to initialize authentication before
            each test case and define parameters of Mistral API Service
        """
        super(MistralTest, cls).setUpClass()

        if not cfg.mistral.service_available:
            raise cls.skipException("Mistral tests are disabled")

        user = cfg.mistral.user
        password = cfg.mistral.password
        tenant = cfg.mistral.tenant
        auth_url = cfg.mistral.auth_url
        client_args = (cls.config, user, password, auth_url, tenant)

        cls.client = rest_client.RestClient(*client_args)
        cls.client.service = 'identity'
        cls.token = cls.client.get_auth()
        cls.client.base_url = cfg.mistral.mistral_url
        cls.obj = []

    def tearDown(self):
        super(MistralTest, self).tearDown()

        for i in self.obj:
            try:
                self.delete_obj(i[0], i[1])
            except Exception:
                pass

    def check_base_url(self):
        resp, body = self.client.get('', self.client.headers)
        return resp, json.loads(body)

    def check_base_url_with_version(self):
        resp, body = self.client.get('v1/', self.client.headers)
        return resp, json.loads(body)

    def get_list_obj(self, name):
        resp, body = self.client.get('v1/%s' % name, self.client.headers)
        return resp, json.loads(body)

    def create_obj(self, path, name):
        post_body = '{"name": "%s"}' % name
        resp, body = self.client.post('v1/%s/' % path, post_body,
                                      self.client.headers)
        return resp, json.loads(body)

    def delete_obj(self, path, name):
        self.client.delete('v1/%s/%s' % (path, name), self.client.headers)

    def update_obj(self, path, name):
        post_body = '{"name": "%s"}' % (name + 'updated')
        resp, body = self.client.put('v1/%s/%s' % (path, name), post_body,
                                     self.client.headers)
        return resp, json.loads(body)

    def get_workbook_definition(self, name):
        headers = {'X-Auth-Token': self.client.headers['X-Auth-Token']}
        resp, body = self.client.get('v1/workbooks/%s/definition' % name,
                                     headers)
        return resp, body

    def upload_workbook_definition(self, name):
        headers = {'Content-Type': 'text/plain',
                   'X-Auth-Token': self.client.headers['X-Auth-Token']}
        __location = os.path.realpath(os.path.join(os.getcwd(),
                                                   os.path.dirname(__file__)))
        f = open(os.path.join(__location, 'demo.yaml'), 'rb').read()
        resp, body = self.client.put('v1/workbooks/%s/definition' % name, f,
                                     headers)
        return resp, body
