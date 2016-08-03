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
import json
from mistral_tempest_tests.tests import base
from tempest import test
from urlparse import urlparse
import uuid


class MultiVimActionsTests(base.TestCase):
    _service = 'workflowv2'

    @classmethod
    def resource_setup(cls):
        super(MultiVimActionsTests, cls).resource_setup()

    @test.attr(type='openstack')
    def test_multi_vim_support(self):

        client_1 = self.alt_client
        client_2 = self.client

        stack_name = 'multi_vim_test_stack_{}'.format(str(uuid.uuid4())[:8])
        create_request = {
            'name': 'heat.stacks_create',
            'input': {
                'stack_name': stack_name,
                "template": {"heat_template_version": "2013-05-23"}
            }
        }
        _, body = client_2.create_action_execution(create_request)
        stack_id = str(json.loads(body['output'])['result']['stack']['id'])

        u = urlparse(client_2.auth_provider.auth_url)
        v3_auth_url = '{}://{}/identity/v3/'.format(u.scheme, u.netloc)
        extra_headers = {
            'X-Target-Auth-Token': client_2.token,
            'X-Target-Auth-Uri': v3_auth_url,
            'X-Target-Project-Id': client_2.tenant_id,
            'X-Target-User-Id': client_2.user_id,
            'X-Target-User-Name': client_2.user,
        }

        list_request = {
            'name': 'heat.stacks_list',
        }

        _, body = client_1.create_action_execution(list_request)
        self.assertEmpty(json.loads(body['output'])['result'])

        _, body = client_1.create_action_execution(list_request,
                                                   extra_headers=extra_headers)
        self.assertEqual(
            stack_id,
            str(json.loads(body['output'])['result'][0]['id'])
        )
