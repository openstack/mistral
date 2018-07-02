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

WORKFLOWS = 'workflows:%s'

rules = [
    policy.DocumentedRuleDefault(
        name=WORKFLOWS % 'create',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='Create a new workflow.',
        operations=[
            {
                'path': '/v2/workflows',
                'method': 'POST'
            }
        ]
    ),
    policy.DocumentedRuleDefault(
        name=WORKFLOWS % 'delete',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='Delete a workflow.',
        operations=[
            {
                'path': '/v2/workflows',
                'method': 'DELETE'
            }
        ]
    ),
    policy.DocumentedRuleDefault(
        name=WORKFLOWS % 'get',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='Return the named workflow.',
        operations=[
            {
                'path': '/v2/workflows/{workflow_id}',
                'method': 'GET'
            }
        ]
    ),
    policy.DocumentedRuleDefault(
        name=WORKFLOWS % 'list',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='Return a list of workflows.',
        operations=[
            {
                'path': '/v2/workflows',
                'method': 'GET'
            }
        ]
    ),
    policy.DocumentedRuleDefault(
        name=WORKFLOWS % 'list:all_projects',
        check_str=base.RULE_ADMIN_ONLY,
        description='Return a list of workflows from all projects.',
        operations=[
            {
                'path': '/v2/workflows',
                'method': 'GET'
            }
        ]
    ),
    policy.DocumentedRuleDefault(
        name=WORKFLOWS % 'publicize',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='Make a workflow publicly available',
        operations=[
            {
                'path': '/v2/workflows',
                'method': 'POST'
            },
            {
                'path': '/v2/workflows',
                'method': 'PUT'
            }
        ]
    ),
    policy.DocumentedRuleDefault(
        name=WORKFLOWS % 'update',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='Update one or more workflows.',
        operations=[
            {
                'path': '/v2/workflows',
                'method': 'PUT'
            }
        ]
    )
]


def list_rules():
    return rules
