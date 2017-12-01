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


RULE_ADMIN_OR_OWNER = 'rule:admin_or_owner'
RULE_ADMIN_ONLY = 'rule:admin_only'

rules = [
    policy.RuleDefault(
        "admin_only",
        "is_admin:True"),
    policy.RuleDefault(
        "admin_or_owner",
        "is_admin:True or project_id:%(project_id)s")
]


def list_rules():
    return rules
