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

CRON_TRIGGERS = 'cron_triggers:%s'

rules = [
    policy.DocumentedRuleDefault(
        name=CRON_TRIGGERS % 'create',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='Creates a new cron trigger.',
        operations=[
            {
                'path': '/v2/cron_triggers',
                'method': 'POST'
            }
        ]
    ),
    policy.DocumentedRuleDefault(
        name=CRON_TRIGGERS % 'delete',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='Delete cron trigger.',
        operations=[
            {
                'path': '/v2/cron_triggers',
                'method': 'DELETE'
            }
        ]
    ),
    policy.DocumentedRuleDefault(
        name=CRON_TRIGGERS % 'get',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='Returns the named cron trigger.',
        operations=[
            {
                'path': '/v2/cron_triggers/{cron_trigger_id}',
                'method': 'GET'
            }
        ]
    ),
    policy.DocumentedRuleDefault(
        name=CRON_TRIGGERS % 'list',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='Return all cron triggers.',
        operations=[
            {
                'path': '/v2/cron_triggers',
                'method': 'GET'
            }
        ]
    ),
    policy.DocumentedRuleDefault(
        name=CRON_TRIGGERS % 'list:all_projects',
        check_str=base.RULE_ADMIN_ONLY,
        description='Return all cron triggers of all projects.',
        operations=[
            {
                'path': '/v2/cron_triggers',
                'method': 'GET'
            }
        ]
    )
]


def list_rules():
    return rules
