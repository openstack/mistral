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

ACTION_EXECUTIONS = 'action_executions:%s'

rules = [
    policy.DocumentedRuleDefault(
        name=ACTION_EXECUTIONS % 'create',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='Create new action execution.',
        operations=[
            {
                'path': '/v2/action_executions',
                'method': 'POST'
            }
        ]
    ),
    policy.DocumentedRuleDefault(
        name=ACTION_EXECUTIONS % 'delete',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='Delete the specified action execution.',
        operations=[
            {
                'path': '/v2/action_executions',
                'method': 'DELETE'
            }
        ]
    ),
    policy.DocumentedRuleDefault(
        name=ACTION_EXECUTIONS % 'get',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='Return the specified action execution.',
        operations=[
            {
                'path': '/v2/action_executions/{action_execution_id}',
                'method': 'GET'
            }
        ]
    ),
    policy.DocumentedRuleDefault(
        name=ACTION_EXECUTIONS % 'list',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='Return all tasks within the execution.',
        operations=[
            {
                'path': '/v2/action_executions',
                'method': 'GET'
            }
        ]
    ),
    policy.DocumentedRuleDefault(
        name=ACTION_EXECUTIONS % 'update',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='Update the specified action execution.',
        operations=[
            {
                'path': '/v2/action_executions',
                'method': 'PUT'
            }
        ]
    )
]


def list_rules():
    return rules
