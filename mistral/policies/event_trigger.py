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

EVENT_TRIGGERS = 'event_triggers:%s'

# NOTE(hieulq): all API operations of below rules are not documented in API
# reference docs yet.
rules = [
    policy.DocumentedRuleDefault(
        name=EVENT_TRIGGERS % 'create',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='Create a new event trigger.',
        operations=[
            {
                'path': '/v2/event_triggers',
                'method': 'POST'
            }
        ]
    ),
    policy.DocumentedRuleDefault(
        name=EVENT_TRIGGERS % 'create:public',
        check_str=base.RULE_ADMIN_ONLY,
        description='Create a new event trigger for public usage.',
        operations=[
            {
                'path': '/v2/event_triggers',
                'method': 'POST'
            }
        ]
    ),
    policy.DocumentedRuleDefault(
        name=EVENT_TRIGGERS % 'delete',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='Delete event trigger.',
        operations=[
            {
                'path': '/v2/event_triggers/{event_trigger_id}',
                'method': 'DELETE'
            }
        ]
    ),
    policy.DocumentedRuleDefault(
        name=EVENT_TRIGGERS % 'get',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='Returns the specified event trigger.',
        operations=[
            {
                'path': '/v2/event_triggers/{event_trigger_id}',
                'method': 'GET'
            }
        ]
    ),
    policy.DocumentedRuleDefault(
        name=EVENT_TRIGGERS % 'list',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='Return all event triggers.',
        operations=[
            {
                'path': '/v2/event_triggers',
                'method': 'GET'
            }
        ]
    ),
    policy.DocumentedRuleDefault(
        name=EVENT_TRIGGERS % 'list:all_projects',
        check_str=base.RULE_ADMIN_ONLY,
        description='Return all event triggers from all projects.',
        operations=[
            {
                'path': '/v2/event_triggers',
                'method': 'GET'
            }
        ]
    ),
    policy.DocumentedRuleDefault(
        name=EVENT_TRIGGERS % 'update',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='Updates an existing event trigger.',
        operations=[
            {
                'path': '/v2/event_triggers',
                'method': 'PUT'
            }
        ]
    )
]


def list_rules():
    return rules
