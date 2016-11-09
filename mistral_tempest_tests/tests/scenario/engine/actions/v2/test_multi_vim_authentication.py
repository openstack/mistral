# Copyright 2016 - Nokia, Inc.
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
import base64
from urlparse import urlparse

from oslo_serialization import jsonutils
from oslo_utils import uuidutils
from tempest import test

from mistral_tempest_tests.tests import base


class MultiVimActionsTests(base.TestCase):
    _service = 'workflowv2'

    @classmethod
    def resource_setup(cls):
        super(MultiVimActionsTests, cls).resource_setup()

    @test.attr(type='openstack')
    def test_multi_vim_support_target_headers(self):
        client_1 = self.alt_client
        client_2 = self.client

        # Create stack with client2.
        result = _execute_action(client_2, _get_create_stack_request())
        stack_id = str(
            jsonutils.loads(result['output'])['result']['stack']['id']
        )

        # List stacks with client1, and assert that there is no stack.
        result = _execute_action(client_1, _get_list_stack_request())
        self.assertEmpty(jsonutils.loads(result['output'])['result'])

        # List stacks with client1, but with the target headers of client2,
        # and assert the created stack is there.
        result = _execute_action(
            client_1,
            _get_list_stack_request(),
            extra_headers=_extract_target_headers_from_client(client_2)
        )
        self.assertEqual(
            stack_id,
            str(jsonutils.loads(result['output'])['result'][0]['id'])
        )

    @test.attr(type='openstack')
    def test_multi_vim_support_target_headers_and_service_catalog(self):
        client_1 = self.alt_client
        client_2 = self.client

        # List stacks with client1, but with the target headers of client2,
        # and additionally with an invalid X-Target-Service-Catalog.
        extra_headers = _extract_target_headers_from_client(client_2)
        service_dict = dict(client_2.auth_provider.cache[1])

        for endpoint in service_dict['serviceCatalog']:
            if endpoint['name'] == 'heat':
                endpoint['endpoints'][0]['publicURL'] = "invalid"

        service_catalog = {
            "X-Target-Service-Catalog": base64.b64encode(
                jsonutils.dumps(service_dict)
            )
        }
        extra_headers.update(service_catalog)
        result = _execute_action(
            client_1,
            _get_list_stack_request(),
            extra_headers=extra_headers
        )

        # Assert that the invalid catalog was used.
        self.assertIn("Invalid URL", result['output'])


def _extract_target_headers_from_client(client):
    u = urlparse(client.auth_provider.auth_url)
    v3_auth_url = '{}://{}/identity/v3/'.format(u.scheme, u.netloc)
    return {
        'X-Target-Auth-Token': client.token,
        'X-Target-Auth-Uri': v3_auth_url,
        'X-Target-Project-Id': client.tenant_id,
        'X-Target-User-Id': client.user_id,
    }


def _execute_action(client, request, extra_headers={}):
    _, result = client.create_action_execution(
        request,
        extra_headers=extra_headers
    )

    return result


def _get_create_stack_request():
    stack_name = 'multi_vim_test_stack_{}'.format(
        uuidutils.generate_uuid()[:8])

    return {
        'name': 'heat.stacks_create',
        'input': {
            'stack_name': stack_name,
            "template": {"heat_template_version": "2013-05-23"}
        }
    }


def _get_list_stack_request():
    return {
        'name': 'heat.stacks_list',
    }
