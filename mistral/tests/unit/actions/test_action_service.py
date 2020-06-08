# Copyright 2020 Nokia Software.
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

from mistral.services import actions
from mistral.tests.unit import base


class LegacyActionProviderTest(base.DbTestCase):
    def test_get_system_action_provider(self):
        self.override_config(
            'load_action_generators',
            False,
            'legacy_action_provider'
        )
        self.override_config(
            'only_builtin_actions',
            True,
            'legacy_action_provider'
        )

        system_provider = actions.get_system_action_provider()

        action_descs = system_provider.find_all()

        for a in action_descs:
            print(a)

        self.assertTrue(len(action_descs) > 0)

        self.assertTrue(
            all(
                [
                    a_d.action_class.__module__.startswith('mistral.')
                    for a_d in action_descs
                ]
            )
        )
