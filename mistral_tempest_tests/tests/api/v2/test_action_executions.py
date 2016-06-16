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
from tempest.lib import exceptions
from tempest import test

from mistral_tempest_tests.tests import base


LOG = logging.getLogger(__name__)


class ActionExecutionTestsV2(base.TestCase):
    _service = 'workflowv2'

    @classmethod
    def resource_cleanup(cls):
        for action_ex in cls.client.action_executions:
            try:
                cls.client.delete_obj('action_executions', action_ex)
            except Exception as e:
                LOG.exception('Exception raised when deleting '
                              'action_executions %s, error message: %s.'
                              % (action_ex, six.text_type(e)))

        cls.client.action_executions = []

        super(ActionExecutionTestsV2, cls).resource_cleanup()

    @test.attr(type='sanity')
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

    @test.attr(type='sanity')
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

    @test.attr(type='sanity')
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

    @test.attr(type='sanity')
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

    @test.attr(type='negative')
    def test_delete_nonexistent_action_execution(self):
        self.assertRaises(
            exceptions.NotFound,
            self.client.delete_obj,
            'action_executions',
            'nonexist'
        )

    @test.attr(type='sanity')
    def test_create_action_execution_sync(self):
        token = self.client.auth_provider.get_token()
        resp, body = self.client.create_action_execution(
            {
                'name': 'std.http',
                'input': '{{"url": "http://localhost:8989/v2/workflows",\
                           "headers": {{"X-Auth-Token": "{}"}}}}'.format(token)
            }
        )

        self.assertEqual(201, resp.status)
        output = json.loads(body['output'])
        self.assertEqual(200, output['result']['status'])
