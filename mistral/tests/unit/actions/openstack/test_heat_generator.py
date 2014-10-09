# Copyright 2014 - Mirantis, Inc.
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

from mistral.actions.openstack.action_generator import generators
from mistral.actions.openstack import actions
from mistral.tests import base


class HeatGeneratorTest(base.BaseTest):
    def test_generator(self):
        action_name = "heat.stacks_list"
        generator = generators.HeatActionGenerator
        action_classes = generator.create_actions()
        action = self._assert_single_item(
            action_classes,
            name=action_name
        )

        self.assertIsNotNone(generator)
        self.assertTrue(issubclass(action['class'], actions.HeatAction))
        self.assertEqual("stacks.list", action['class'].client_method_name)
