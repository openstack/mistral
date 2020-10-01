# Copyright 2020 Nokia Software.
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

from oslo_policy import policy

from mistral.policies import base

ACTIONS = 'dynamic_actions:%s'
BASE_PATH = '/v2/dynamic_actions'

rules = [
    policy.DocumentedRuleDefault(
        name=ACTIONS % 'create',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='Create a new dynamic action.',
        operations=[
            {
                'path': BASE_PATH,
                'method': 'POST'
            }
        ]
    ),
    policy.DocumentedRuleDefault(
        name=ACTIONS % 'delete',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='Delete the named dynamic action.',
        operations=[
            {
                'path': BASE_PATH,
                'method': 'DELETE'
            }
        ]
    ),
    policy.DocumentedRuleDefault(
        name=ACTIONS % 'get',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='Return the named dynamic action.',
        operations=[
            {
                'path': BASE_PATH + '/{action_id}',
                'method': 'GET'
            }
        ]
    ),
    policy.DocumentedRuleDefault(
        name=ACTIONS % 'list',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='Return all dynamic actions.',
        operations=[
            {
                'path': BASE_PATH,
                'method': 'GET'
            }
        ]
    ),
    policy.DocumentedRuleDefault(
        name=ACTIONS % 'update',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='Update one or more dynamic actions.',
        operations=[
            {
                'path': BASE_PATH,
                'method': 'PUT'
            }
        ]
    )
]


def list_rules():
    return rules
