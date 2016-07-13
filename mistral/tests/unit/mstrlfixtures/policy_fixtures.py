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

import os

import fixtures
from oslo_config import cfg
from oslo_policy import opts as policy_opts
from oslo_policy import policy as oslo_policy

from mistral.api import access_control as acl
from mistral.tests.unit import fake_policy


class PolicyFixture(fixtures.Fixture):
    """Load a fake policy from nova.tests.unit.fake_policy"""

    def setUp(self):
        super(PolicyFixture, self).setUp()

        self.policy_dir = self.useFixture(fixtures.TempDir())
        self.policy_file_name = os.path.join(
            self.policy_dir.path,
            'policy.json'
        )

        with open(self.policy_file_name, 'w') as policy_file:
            policy_file.write(fake_policy.policy_data)

        policy_opts.set_defaults(cfg.CONF)

        cfg.CONF.set_override(
            'policy_file',
            self.policy_file_name,
            'oslo_policy'
        )

        acl._ENFORCER = oslo_policy.Enforcer(cfg.CONF)
        acl._ENFORCER.load_rules()

        self.addCleanup(acl._ENFORCER.clear)

    def set_rules(self, rules):
        policy = acl._ENFORCER

        policy.set_rules(oslo_policy.Rules.from_dict(rules))
