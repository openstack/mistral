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

from tempest import auth
from tempest import clients
from tempest.common import rest_client
from tempest import config
from tempest import exceptions
import tempest.test

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

    _version = None

    def __init__(self, auth_provider):
        super(MistralClientBase, self).__init__(auth_provider)

        if self._version == 1:
            self.service = 'workflow'
        elif self._version == 2:
            self.service = 'workflowv2'
        else:
            msg = ("Invalid parameter 'version'. "
                   "Use version=1 or version=2.")
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


class MistralClientV1(MistralClientBase):

    _version = 1

    def create_workbook(self, name):
        post_body = '{"name": "%s"}' % name
        resp, body = self.post('workbooks', post_body)

        self.workbooks.append(name)

        return resp, json.loads(body)

    def update_workbook(self, name):
        post_body = '{"name": "%s"}' % name
        resp, body = self.put('workbooks/{name}'.format(name=name),
                              post_body)
        return resp, json.loads(body)

    def get_workbook_definition(self, name):
        headers = {'X-Auth-Token': self.auth_provider.get_token()}
        return self.get('workbooks/{name}/definition'.format(name=name),
                        headers)

    def upload_workbook_definition(self, name):
        headers = {'Content-Type': 'text/plain',
                   'X-Auth-Token': self.auth_provider.get_token()}
        text = get_resource('wb_v1.yaml')

        return self.put('workbooks/{name}/definition'.format(name=name),
                        text, headers)

    def create_execution(self, workbook_name, post_body=None):
        if post_body is None:
            body = {
                "workbook_name": workbook_name,
                "task": 'hello',
                "context": ''
            }
        else:
            body = post_body

        rest, body = self.post('workbooks/{name}/executions'.format(
            name=workbook_name), json.dumps(body))

        self.executions.append(json.loads(body)['id'])

        return rest, json.loads(body)

    def update_execution(self, execution_id, put_body):
        return self.put('executions/{execution}'.format(
            execution=execution_id), json.dumps(put_body))

    def get_tasks_list(self, workbook_name, execution_id):
        resp, body = self.get(
            '/workbooks/{name}/executions/{execution}/tasks'.format(
                name=workbook_name,
                execution=execution_id))

        return resp, json.loads(body)['tasks']

    def get_task(self, workbook_name, execution_id, task_id):
        resp, body = self.get(
            '/workbooks/{name}/executions/{execution}/tasks/{task}'.format(
                name=workbook_name,
                execution=execution_id,
                task=task_id))

        return resp, json.loads(body)

    def update_task(self, task_id, put_body):
        resp, body = self.put('tasks/{task}'.format(
            task=task_id), json.dumps(put_body))

        return resp, json.loads(body)

    def prepare_workbook(self, name, text):
        headers = {'Content-Type': 'text/plain',
                   'X-Auth-Token': self.auth_provider.get_token()}

        return self.put('workbooks/{name}/definition'.format(name=name),
                        text, headers)

    def create_execution_wait_success(self, workbook_name,
                                      context, task, timeout=180):

        body = {
            "workbook_name": workbook_name,
            "task": task,
            "context": json.dumps(context)
        }

        resp, ex_body = self.create_execution(workbook_name, body)

        start_time = time.time()

        expected_states = ['SUCCESS', 'RUNNING']

        while ex_body['state'] != 'SUCCESS':
            if time.time() - start_time > timeout:
                msg = "Execution exceeds timeout {0} to change state " \
                      "to SUCCESS. Execution: {1}".format(timeout, ex_body)
                raise exceptions.TimeoutException(msg)

            _, ex_body = self.get_object('executions', ex_body['id'])

            if ex_body['state'] not in expected_states:
                msg = "Execution state %s is not in expected " \
                      "states: %s" % (ex_body['state'], expected_states)
                raise exceptions.TempestException(msg)

            time.sleep(2)

        return resp, ex_body

    def get_task_by_name(self, workbook_name, execution_id, name):
        _, tasks = self.get_tasks_list(workbook_name, execution_id)
        for task in tasks:
            if task['name'] == name:
                _, task_body = self.get_task(
                    workbook_name, execution_id, task['id'])

                return task_body


class MistralClientV2(MistralClientBase):

    _version = 2

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

    def create_cron_trigger(self, name, pattern, wf_name, wf_input=None):
        post_body = {
            'name': name,
            'pattern': pattern,
            'workflow_name': wf_name,
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


class TestCase(tempest.test.BaseTestCase):

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

        if cls._version == 1:
            cls.client = MistralClientV1(cls.mgr.auth_provider)
        if cls._version == 2:
            cls.client = MistralClientV2(cls.mgr.auth_provider)

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
