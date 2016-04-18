# Copyright 2013 Mirantis, Inc. All Rights Reserved.
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

import mock
import six

from oslo_utils import uuidutils
from tempest import clients
from tempest import config
from tempest.lib import auth
from tempest.lib.common import rest_client
from tempest.lib import exceptions
from tempest import test as test

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


class MistralClientV2(MistralClientBase):

    def post_request(self, url, file_name):
        headers = {"headers": "Content-Type:text/plain"}

        return self.post(url, get_resource(file_name), headers=headers)

    def post_json(self, url, obj):
        headers = {"Content-Type": "application/json"}

        return self.post(url, json.dumps(obj), headers=headers)

    def update_request(self, url, file_name):
        headers = {"headers": "Content-Type:text/plain"}

        resp, body = self.put(url, get_resource(file_name), headers=headers)

        return resp, json.loads(body)

    def get_definition(self, item, name):
        resp, body = self.get("%s/%s" % (item, name))

        return resp, json.loads(body)['definition']

    def create_workbook(self, yaml_file):
        resp, body = self.post_request('workbooks', yaml_file)

        wb_name = json.loads(body)['name']
        self.workbooks.append(wb_name)

        _, wfs = self.get_list_obj('workflows')

        for wf in wfs['workflows']:
            if wf['name'].startswith(wb_name):
                self.workflows.append(wf['name'])

        return resp, json.loads(body)

    def create_workflow(self, yaml_file, scope=None):
        if scope:
            resp, body = self.post_request('workflows?scope=public', yaml_file)
        else:
            resp, body = self.post_request('workflows', yaml_file)

        for wf in json.loads(body)['workflows']:
            self.workflows.append(wf['name'])

        return resp, json.loads(body)

    def create_execution(self, identifier, wf_input=None, params=None):
        if uuidutils.is_uuid_like(identifier):
            body = {"workflow_id": "%s" % identifier}
        else:
            body = {"workflow_name": "%s" % identifier}

        if wf_input:
            body.update({'input': json.dumps(wf_input)})
        if params:
            body.update({'params': json.dumps(params)})

        resp, body = self.post('executions', json.dumps(body))

        self.executions.append(json.loads(body)['id'])

        return resp, json.loads(body)

    def update_execution(self, execution_id, put_body):
        resp, body = self.put('executions/%s' % execution_id, put_body)

        return resp, json.loads(body)

    def create_cron_trigger(self, name, wf_name, wf_input=None, pattern=None,
                            first_time=None, count=None):
        post_body = {
            'name': name,
            'workflow_name': wf_name,
            'pattern': pattern,
            'remaining_executions': count,
            'first_execution_time': first_time
        }

        if wf_input:
            post_body.update({'workflow_input': json.dumps(wf_input)})

        rest, body = self.post('cron_triggers', json.dumps(post_body))

        self.triggers.append(name)

        return rest, json.loads(body)

    def create_action(self, yaml_file):
        resp, body = self.post_request('actions', yaml_file)

        self.actions.extend(
            [action['name'] for action in json.loads(body)['actions']])

        return resp, json.loads(body)

    def get_wf_tasks(self, wf_name):
        all_tasks = self.get_list_obj('tasks')[1]['tasks']

        return [t for t in all_tasks if t['workflow_name'] == wf_name]

    def create_action_execution(self, request_body):
        resp, body = self.post_json('action_executions', request_body)

        params = json.loads(request_body.get('params', '{}'))
        if params.get('save_result', False):
            self.action_executions.append(json.loads(body)['id'])

        return resp, json.loads(body)


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


class TestCase(test.BaseTestCase):

    credentials = ['primary', 'alt']

    @classmethod
    def resource_setup(cls):
        """Client authentication.

        This method allows to initialize authentication before
        each test case and define parameters of Mistral API Service.
        """
        super(TestCase, cls).resource_setup()

        if 'WITHOUT_AUTH' in os.environ:
            cls.mgr = mock.MagicMock()
            cls.mgr.auth_provider = AuthProv()
            cls.alt_mgr = cls.mgr
        else:
            cls.mgr = cls.manager
            cls.alt_mgr = cls.alt_manager

        if cls._service == 'workflowv2':
            cls.client = MistralClientV2(
                cls.mgr.auth_provider, cls._service)
            cls.alt_client = MistralClientV2(
                cls.alt_mgr.auth_provider, cls._service)

    def setUp(self):
        super(TestCase, self).setUp()

    def tearDown(self):
        super(TestCase, self).tearDown()

        for wb in self.client.workbooks:
            self.client.delete_obj('workbooks', wb)

        self.client.workbooks = []


class TestCaseAdvanced(TestCase):
    @classmethod
    def resource_setup(cls):
        super(TestCaseAdvanced, cls).resource_setup()

        cls.server_client = clients.ServersClient(
            cls.mgr.auth_provider,
            "compute",
            region=CONF.identity.region
        )

        cls.image_ref = CONF.compute.image_ref
        cls.flavor_ref = CONF.compute.flavor_ref

    def tearDown(self):
        for wb in self.client.workbooks:
            self.client.delete_obj('workbooks', wb)

        self.client.workbooks = []

        for ex in self.client.executions:
            self.client.delete_obj('executions', ex)

        self.client.executions = []

        super(TestCaseAdvanced, self).tearDown()
