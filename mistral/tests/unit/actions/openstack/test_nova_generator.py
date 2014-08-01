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

from oslotest import base

from mistral.actions import generator_factory
from mistral.actions.openstack import actions


class NovaGeneratorTest(base.BaseTestCase):
    def test_generator(self):
        action_name = "nova.servers_get"
        generator = generator_factory.all_generators()["nova"]()
        action_classes = generator.create_action_classes()
        short_action_name = action_name.split(".")[1]
        action_class = action_classes[short_action_name]

        self.assertIsNotNone(generator)
        self.assertIn(short_action_name, action_classes)
        self.assertTrue(issubclass(action_class, actions.NovaAction))
        self.assertEqual("servers.get", action_class.client_method)
