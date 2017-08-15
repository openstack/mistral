# Copyright 2016 NEC Corporation. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import json
import six

from oslo_log import log as logging
from tempest.lib import decorators
from tempest.lib import exceptions

from mistral_tempest_tests.tests import base


LOG = logging.getLogger(__name__)


class ActionExecutionTestsV2(base.TestCase):
    _service = 'workflowv2'

    @classmethod
    def resource_setup(cls):
        super(ActionExecutionTestsV2, cls).resource_setup()

        cls.client.create_action_execution(
            {
                'name': 'std.echo',
                'input': '{"output": "Hello, Mistral!"}'
            }
        )

    @classmethod
    def resource_cleanup(cls):
        for action_ex in cls.client.action_executions:
            try:
                cls.client.delete_obj('action_executions', action_ex)
            except Exception as e:
                LOG.exception(
                    'Exception raised when deleting '
                    'action_executions %s, error message: %s.',
                    action_ex, six.text_type(e)
                )

        cls.client.action_executions = []

        super(ActionExecutionTestsV2, cls).resource_cleanup()

    @decorators.attr(type='sanity')
    @decorators.idempotent_id('a72603bd-5d49-4d92-9747-8da6322e867d')
    def test_run_action_execution(self):
        resp, body = self.client.create_action_execution(
            {
                'name': 'std.echo',
                'input': '{"output": "Hello, Mistral!"}'
            }
        )

        self.assertEqual(201, resp.status)
        output = json.loads(body['output'])
        self.assertDictEqual(
            {'result': 'Hello, Mistral!'},
            output
        )

    @decorators.attr(type='sanity')
    @decorators.idempotent_id('0623cb62-b20a-45c8-afd9-8da46e1bb3cb')
    def test_list_action_executions(self):
        resp, body = self.client.get_list_obj('action_executions')

        self.assertEqual(200, resp.status)

    @decorators.attr(type='sanity')
    @decorators.idempotent_id('cd36ea00-7e22-4c3d-90c3-fb441b93cf12')
    def test_output_appear_in_response_only_when_needed(self):
        resp, body = self.client.get_list_obj('action_executions')

        self.assertEqual(200, resp.status)
        action_execution = body['action_executions'][0]
        self.assertNotIn("output", action_execution)

        resp, body = self.client.get_list_obj(
            'action_executions?include_output=True'
        )

        self.assertEqual(200, resp.status)
        action_execution = body['action_executions'][0]
        self.assertIn("output", action_execution)

        resp, body = self.client.get_action_execution(action_execution['id'])
        self.assertIn("output", body)

        # Test when passing task execution ID

        resp, body = self.client.create_workflow('wf_v2.yaml')
        wf_name = body['workflows'][0]['name']
        self.assertEqual(201, resp.status)
        resp, body = self.client.create_execution(wf_name)
        self.assertEqual(201, resp.status)
        resp, body = self.client.get_list_obj('tasks')
        self.assertEqual(200, resp.status)
        task_id = body['tasks'][0]['id']

        resp, body = self.client.get_list_obj(
            'action_executions?include_output=true&task_execution_id=%s' %
            task_id
        )

        self.assertEqual(200, resp.status)
        action_execution = body['action_executions'][0]
        self.assertIn("output", action_execution)

        resp, body = self.client.get_list_obj(
            'action_executions?&task_execution_id=%s' %
            task_id
        )

        self.assertEqual(200, resp.status)
        action_execution = body['action_executions'][0]
        self.assertNotIn("output", action_execution)

    @decorators.attr(type='sanity')
    @decorators.idempotent_id('dc76aeda-9243-45cf-bfd2-141d3af8b28b')
    def test_run_action_std_http(self):
        resp, body = self.client.create_action_execution(
            {
                'name': 'std.http',
                'input': '{"url": "http://wiki.openstack.org"}'
            }
        )

        self.assertEqual(201, resp.status)
        output = json.loads(body['output'])
        self.assertTrue(output['result']['status'] in range(200, 307))

    @decorators.attr(type='sanity')
    @decorators.idempotent_id('befa9b1c-01a4-41bc-b060-88cb1b147dfb')
    def test_run_action_std_http_error(self):
        resp, body = self.client.create_action_execution(
            {
                'name': 'std.http',
                'input': '{"url": "http://www.google.ru/not-found-test"}'
            }
        )

        self.assertEqual(201, resp.status)
        output = json.loads(body['output'])
        self.assertEqual(404, output['result']['status'])

    @decorators.attr(type='sanity')
    @decorators.related_bug('1667415')
    @decorators.idempotent_id('3c73de7a-4af0-4657-90d6-d7ebd3c7da18')
    def test_run_action_std_http_non_utf8_response(self):
        resp, body = self.client.create_action_execution(
            {
                'name': 'std.http',
                'input':
                    '{"url": "https://httpbin.org/encoding/utf8"}'
            }
        )

        self.assertEqual(201, resp.status)
        output = json.loads(body['output'])
        self.assertEqual(200, output['result']['status'])

    @decorators.attr(type='sanity')
    @decorators.idempotent_id('d98586bf-fdc4-44f6-9837-700d35b5f889')
    def test_create_action_execution(self):
        resp, body = self.client.create_action_execution(
            {
                'name': 'std.echo',
                'input': '{"output": "Hello, Mistral!"}',
                'params': '{"save_result": true}'
            }
        )

        self.assertEqual(201, resp.status)
        self.assertEqual('RUNNING', body['state'])

        # We must reread action execution in order to get actual
        # state and output.
        body = self.client.wait_execution_success(
            body,
            url='action_executions'
        )
        output = json.loads(body['output'])

        self.assertEqual('SUCCESS', body['state'])
        self.assertDictEqual(
            {'result': 'Hello, Mistral!'},
            output
        )

    @decorators.attr(type='negative')
    @decorators.idempotent_id('99f22c17-6fb4-4480-96d3-4a82672916b7')
    def test_delete_nonexistent_action_execution(self):
        self.assertRaises(
            exceptions.NotFound,
            self.client.delete_obj,
            'action_executions',
            'nonexist'
        )

    @decorators.attr(type='sanity')
    @decorators.idempotent_id('2dbd74ba-4950-4c52-8bd3-070d634dcd05')
    def test_create_action_execution_sync(self):
        token = self.client.auth_provider.get_token()
        resp, body = self.client.create_action_execution(
            {
                'name': 'std.http',
                'input': ('{{"url": "http://localhost:8989/v2/workflows",'
                          '"headers": {{"X-Auth-Token": "{}"}}}}'
                          ).format(token)
            }
        )

        self.assertEqual(201, resp.status)
        output = json.loads(body['output'])
        self.assertEqual(200, output['result']['status'])

    @decorators.idempotent_id('9438e195-031c-4502-b216-6d72941ec281')
    @decorators.attr(type='sanity')
    def test_action_execution_of_workflow_within_namespace(self):

        resp, body = self.client.create_workflow('wf_v2.yaml', namespace='abc')
        wf_name = body['workflows'][0]['name']
        wf_namespace = body['workflows'][0]['namespace']
        self.assertEqual(201, resp.status)
        resp, body = self.client.create_execution(
            wf_name,
            wf_namespace=wf_namespace
        )
        self.assertEqual(201, resp.status)
        resp, body = self.client.get_list_obj('tasks')
        self.assertEqual(200, resp.status)
        task_id = body['tasks'][0]['id']

        resp, body = self.client.get_list_obj(
            'action_executions?include_output=true&task_execution_id=%s' %
            task_id)

        self.assertEqual(200, resp.status)
        action_execution = body['action_executions'][0]

        self.assertEqual(200, resp.status)
        action_execution = body['action_executions'][0]
        self.assertEqual(wf_namespace, action_execution['workflow_namespace'])
