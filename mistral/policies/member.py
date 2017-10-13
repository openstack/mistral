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

MEMBERS = 'members:%s'

# NOTE(hieulq): all API operations of below rules are not documented in API
# reference docs yet.
rules = [
    policy.DocumentedRuleDefault(
        name=MEMBERS % 'create',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='Shares the resource to a new member.',
        operations=[
            {
                'path': '/v2/members',
                'method': 'POST'
            }
        ]
    ),
    policy.DocumentedRuleDefault(
        name=MEMBERS % 'delete',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='Deletes a member from the member list of a resource.',
        operations=[
            {
                'path': '/v2/members',
                'method': 'DELETE'
            }
        ]
    ),
    policy.DocumentedRuleDefault(
        name=MEMBERS % 'get',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='Shows resource member details.',
        operations=[
            {
                'path': '/v2/members/{member_id}',
                'method': 'GET'
            }
        ]
    ),
    policy.DocumentedRuleDefault(
        name=MEMBERS % 'list',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='Return all members with whom the resource has been '
                    'shared.',
        operations=[
            {
                'path': '/v2/members',
                'method': 'GET'
            }
        ]
    ),
    policy.DocumentedRuleDefault(
        name=MEMBERS % 'update',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='Sets the status for a resource member.',
        operations=[
            {
                'path': '/v2/members',
                'method': 'PUT'
            }
        ]
    )
]


def list_rules():
    return rules
