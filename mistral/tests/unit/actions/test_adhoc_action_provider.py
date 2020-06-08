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

from mistral.actions import adhoc
from mistral.services import adhoc_actions as adhoc_action_service
from mistral.tests.unit import base


class AdHocActionProviderTest(base.DbTestCase):
    def test_adhoc_actions(self):
        provider = adhoc.AdHocActionProvider()

        action_descs = provider.find_all()

        self.assertEqual(0, len(action_descs))

        action_txt = """
        version: '2.0'

        my_adhoc_action:
          base: std.echo
          base-input:
            output: "<% $.s1 %>+<% $.s2 %>"
          input:
            - s1: "a"
            - s2
          output: "<% $ %> and <% $ %>"
        """

        adhoc_action_service.create_actions(action_txt)

        action_descs = provider.find_all()

        self.assertEqual(1, len(action_descs))

        action_desc = action_descs[0]

        self.assertEqual('my_adhoc_action', action_desc.name)
        self.assertEqual(action_txt, action_desc.definition)
