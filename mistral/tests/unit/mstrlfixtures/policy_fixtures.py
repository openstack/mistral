# Copyright 2016 NEC Corporation. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import fixtures

from mistral.api import access_control as acl
from mistral import policies
from oslo_config import cfg
from oslo_policy import opts as policy_opts
from oslo_policy import policy as oslo_policy


class PolicyFixture(fixtures.Fixture):
    def setUp(self):
        super(PolicyFixture, self).setUp()

        policy_opts.set_defaults(cfg.CONF)

        acl._ENFORCER = oslo_policy.Enforcer(cfg.CONF)
        acl._ENFORCER.register_defaults(policies.list_rules())
        acl._ENFORCER.load_rules()

        self.addCleanup(acl._ENFORCER.clear)

    def register_rules(self, rules):
        enf = acl._ENFORCER
        for rule_name, rule_check_str in rules.items():
            enf.register_default(oslo_policy.RuleDefault(rule_name,
                                                         rule_check_str))

    def change_policy_definition(self, rules):
        enf = acl._ENFORCER
        for rule_name, rule_check_str in rules.items():
            enf.rules[rule_name] = oslo_policy.RuleDefault(
                rule_name, rule_check_str).check
