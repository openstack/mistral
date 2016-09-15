# Copyright 2013 Mirantis, Inc. All Rights Reserved.
# Copyright 2016 NEC Corporation. All rights reserved.
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

import json
import os
import time

import six

from tempest import config
from tempest.lib import auth
from tempest.lib.common import rest_client
from tempest.lib import exceptions

CONF = config.CONF


def get_resource(path):
    main_package = 'mistral_tempest_tests'
    dir_path = __file__[0:__file__.find(main_package)]

    return open(dir_path + 'mistral/tests/resources/' + path).read()


def find_items(items, **props):
    def _matches(item, **props):
        for prop_name, prop_val in six.iteritems(props):
            if item[prop_name] != prop_val:
                return False

        return True

    filtered = list(filter(lambda item: _matches(item, **props), items))

    if len(filtered) == 1:
        return filtered[0]

    return filtered


class MistralClientBase(rest_client.RestClient):
    def __init__(self, auth_provider, service_type):
        super(MistralClientBase, self).__init__(
            auth_provider=auth_provider,
            service=service_type,
            region=CONF.identity.region,
            disable_ssl_certificate_validation=True
        )

        if service_type not in ('workflow', 'workflowv2'):
            msg = "Invalid parameter 'service_type'. "
            raise exceptions.UnprocessableEntity(msg)

        self.endpoint_url = 'publicURL'

        self.workbooks = []
        self.executions = []
        self.workflows = []
        self.triggers = []
        self.actions = []
        self.action_executions = []
        self.event_triggers = []

    def get_list_obj(self, name):
        resp, body = self.get(name)

        return resp, json.loads(body)

    def delete_obj(self, obj, name):
        return self.delete('{obj}/{name}'.format(obj=obj, name=name))

    def get_object(self, obj, id):
        resp, body = self.get('{obj}/{id}'.format(obj=obj, id=id))

        return resp, json.loads(body)

    def wait_execution_success(self, ex_body, timeout=180, url='executions'):
        return self.wait_execution(ex_body, timeout=timeout, url=url)

    def wait_execution(self, ex_body, timeout=180, url='executions',
                       target_state='SUCCESS'):
        start_time = time.time()

        expected_states = [target_state, 'RUNNING']

        while ex_body['state'] != target_state:
            if time.time() - start_time > timeout:
                msg = ("Execution exceeds timeout {0} "
                       "to change state to {1}. "
                       "Execution: {2}".format(timeout, target_state, ex_body))
                raise exceptions.TimeoutException(msg)

            _, ex_body = self.get_object(url, ex_body['id'])

            if ex_body['state'] not in expected_states:
                msg = ("Execution state %s is not in expected "
                       "states: %s" % (ex_body['state'], expected_states))
                raise exceptions.TempestException(msg)

            time.sleep(1)

        return ex_body


class AuthProv(auth.KeystoneV2AuthProvider):
    def __init__(self):
        self.alt_part = None

    def auth_request(self, method, url, *args, **kwargs):
        req_url, headers, body = super(AuthProv, self).auth_request(
            method, url, *args, **kwargs)
        return 'http://localhost:8989/{0}/{1}'.format(
            os.environ['VERSION'], url), headers, body

    def get_auth(self):
        return 'mock_str', 'mock_str'

    def base_url(self, *args, **kwargs):
        return ''
