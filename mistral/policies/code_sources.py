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

CODE_SOURCES = 'code_sources:%s'
BASE_PATH = '/v2/code_sources'

rules = [
    policy.DocumentedRuleDefault(
        name=CODE_SOURCES % 'create',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='Create a new code source.',
        operations=[
            {
                'path': BASE_PATH,
                'method': 'POST'
            }
        ]
    ),
    policy.DocumentedRuleDefault(
        name=CODE_SOURCES % 'delete',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='Delete the named code source.',
        operations=[
            {
                'path': BASE_PATH,
                'method': 'DELETE'
            }
        ]
    ),
    policy.DocumentedRuleDefault(
        name=CODE_SOURCES % 'get',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='Return the named code source.',
        operations=[
            {
                'path': BASE_PATH + '/{action_id}',
                'method': 'GET'
            }
        ]
    ),
    policy.DocumentedRuleDefault(
        name=CODE_SOURCES % 'list',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='Return all code sources.',
        operations=[
            {
                'path': BASE_PATH,
                'method': 'GET'
            }
        ]
    ),
    policy.DocumentedRuleDefault(
        name=CODE_SOURCES % 'update',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='Update one or more code source.',
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
