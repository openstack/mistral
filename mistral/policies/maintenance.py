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

MAINTENANCE = 'maintenance:%s'

rules = [
    policy.DocumentedRuleDefault(
        name=MAINTENANCE % 'get',
        check_str=base.RULE_ADMIN_ONLY,
        description='Return the cluster maintenance status. This exposes '
                    'cluster-wide operational state, so it is restricted '
                    'to administrators.',
        operations=[
            {
                'path': '/maintenance',
                'method': 'GET'
            }
        ]
    ),
    policy.DocumentedRuleDefault(
        name=MAINTENANCE % 'update',
        check_str=base.RULE_ADMIN_ONLY,
        description='Change the cluster maintenance status. Pausing '
                    'maintenance pauses running executions across all '
                    'projects, so this is restricted to administrators.',
        operations=[
            {
                'path': '/maintenance',
                'method': 'PUT'
            }
        ]
    )
]


def list_rules():
    return rules
