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
from oslo_policy import policy

from mistral.policies import base

ENVIRONMENTS = 'environments:%s'

rules = [
    policy.DocumentedRuleDefault(
        name=ENVIRONMENTS % 'create',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='Create a new environment.',
        operations=[
            {
                'path': '/v2/environments',
                'method': 'POST'
            }
        ]
    ),
    policy.DocumentedRuleDefault(
        name=ENVIRONMENTS % 'delete',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='Delete the named environment.',
        operations=[
            {
                'path': '/v2/environments/{environment_name}',
                'method': 'DELETE'
            }
        ]
    ),
    policy.DocumentedRuleDefault(
        name=ENVIRONMENTS % 'get',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='Return the named environment.',
        operations=[
            {
                'path': '/v2/environments/{environment_name}',
                'method': 'GET'
            }
        ]
    ),
    policy.DocumentedRuleDefault(
        name=ENVIRONMENTS % 'list',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='Return all environments.',
        operations=[
            {
                'path': '/v2/environments',
                'method': 'GET'
            }
        ]
    ),
    policy.DocumentedRuleDefault(
        name=ENVIRONMENTS % 'update',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='Update an environment.',
        operations=[
            {
                'path': '/v2/environments',
                'method': 'PUT'
            }
        ]
    )
]


def list_rules():
    return rules
