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
import mock
import os
import time

from tempest import clients
from tempest import config
from tempest import test as test
from tempest_lib import auth
from tempest_lib.common import rest_client
from tempest_lib import exceptions


CONF = config.CONF


def get_resource(path):
    main_package = 'mistral/tests'
    dir_path = __file__[0:__file__.find(main_package) + len(main_package) + 1]

    return open(dir_path + 'resources/' + path).read()


def find_items(items, **props):
    def _matches(item, **props):
        for prop_name, prop_val in props.iteritems():
            if item[prop_name] != prop_val:
                return False

        return True

    filtered = filter(lambda item: _matches(item, **props), items)

    if len(filtered) == 1:
        return filtered[0]

    return filtered


class MistralClientBase(rest_client.RestClient):

    def __init__(self, auth_provider, service_type):
        super(MistralClientBase, self).__init__(
            auth_provider=auth_provider,
            service=service_type,
            region=CONF.identity.region)

        if service_type not in ('workflow', 'workflowv2'):
            msg = ("Invalid parameter 'service_type'. ")
            raise exceptions.UnprocessableEntity(msg)

        self.endpoint_url = 'publicURL'

        self.workbooks = []
        self.executions = []
        self.workflows = []
        self.triggers = []
        self.actions = []

    def get_list_obj(self, name):
        resp, body = self.get(name)
        return resp, json.loads(body)

    def delete_obj(self, obj, name):
        return self.delete('{obj}/{name}'.format(obj=obj, name=name))

    def get_object(self, obj, id):
        resp, body = self.get('{obj}/{id}'.format(obj=obj, id=id))
        return resp, json.loads(body)

    def wait_execution_success(self, ex_body, timeout=180):
        start_time = time.time()

        expected_states = ['SUCCESS', 'RUNNING']

        while ex_body['state'] != 'SUCCESS':
            if time.time() - start_time > timeout:
                msg = ("Execution exceeds timeout {0} to change state "
                       "to SUCCESS. Execution: {1}".format(timeout, ex_body))
                raise exceptions.TimeoutException(msg)

            _, ex_body = self.get_object('executions', ex_body['id'])

            if ex_body['state'] not in expected_states:
                msg = ("Execution state %s is not in expected "
                       "states: %s" % (ex_body['state'], expected_states))
                raise exceptions.TempestException(msg)

            time.sleep(2)

        return True


class MistralClientV2(MistralClientBase):

    def post_request(self, url, file_name):
        text = get_resource(file_name)
        headers = {"headers": "Content-Type:text/plain"}
        return self.post(url, text, headers=headers)

    def update_request(self, url, file_name):
        text = get_resource(file_name)
        headers = {"headers": "Content-Type:text/plain"}
        resp, body = self.put(url, text, headers=headers)

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

    def create_workflow(self, yaml_file):
        resp, body = self.post_request('workflows', yaml_file)

        for wf in json.loads(body)['workflows']:
            self.workflows.append(wf['name'])

        return resp, json.loads(body)

    def create_execution(self, wf_name, wf_input=None, params=None):
        body = {"workflow_name": "%s" % wf_name}
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

    @classmethod
    def setUpClass(cls):
        """This method allows to initialize authentication before
        each test case and define parameters of Mistral API Service.
        """
        super(TestCase, cls).setUpClass()

        if 'WITHOUT_AUTH' in os.environ:
            cls.mgr = mock.MagicMock()
            cls.mgr.auth_provider = AuthProv()
        else:
            cls.mgr = clients.Manager()

        if cls._service == 'workflowv2':
            cls.client = MistralClientV2(
                cls.mgr.auth_provider, cls._service)

    def setUp(self):
        super(TestCase, self).setUp()

    def tearDown(self):
        super(TestCase, self).tearDown()

        for wb in self.client.workbooks:
            self.client.delete_obj('workbooks', wb)
        self.client.workbooks = []


class TestCaseAdvanced(TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestCaseAdvanced, cls).setUpClass()

        cls.server_client = cls.mgr.servers_client

        cls.image_ref = CONF.compute.image_ref
        cls.flavor_ref = CONF.compute.flavor_ref

    def setUp(self):
        super(TestCaseAdvanced, self).setUp()

        self.workbook_name = 'test'
        self.client.create_workbook(self.workbook_name)

    def tearDown(self):
        for wb in self.client.workbooks:
            self.client.delete_obj('workbooks', wb)
        self.client.workbooks = []

        for ex in self.client.executions:
            self.client.delete_obj('executions', ex)
        self.client.executions = []

        super(TestCaseAdvanced, self).tearDown()
