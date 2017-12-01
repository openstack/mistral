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

WORKBOOKS = 'workbooks:%s'

rules = [
    policy.DocumentedRuleDefault(
        name=WORKBOOKS % 'create',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='Create a new workbook.',
        operations=[
            {
                'path': '/v2/workbooks',
                'method': 'POST'
            }
        ]
    ),
    policy.DocumentedRuleDefault(
        name=WORKBOOKS % 'delete',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='Delete the named workbook.',
        operations=[
            {
                'path': '/v2/workbooks',
                'method': 'DELETE'
            }
        ]
    ),
    policy.DocumentedRuleDefault(
        name=WORKBOOKS % 'get',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='Return the named workbook.',
        operations=[
            {
                'path': '/v2/workbooks/{workbook_name}',
                'method': 'GET'
            }
        ]
    ),
    policy.DocumentedRuleDefault(
        name=WORKBOOKS % 'list',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='Return all workbooks.',
        operations=[
            {
                'path': '/v2/workbooks',
                'method': 'GET'
            }
        ]
    ),
    policy.DocumentedRuleDefault(
        name=WORKBOOKS % 'update',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='Update an workbook.',
        operations=[
            {
                'path': '/v2/workbooks',
                'method': 'PUT'
            }
        ]
    )
]


def list_rules():
    return rules
