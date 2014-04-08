# -*- coding: utf-8 -*-
#
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

from mistral.openstack.common import log as logging
from mistral.actions import action_factory
from mistral.actions import std_actions as std
from mistral.tests import base

LOG = logging.getLogger(__name__)


class ActionFactoryTest(base.BaseTest):
    def test_register_standard_actions(self):
        namespaces = action_factory.get_registered_namespaces()

        self.assertEqual(1, len(namespaces))
        self.assertIn("std", namespaces)

        std_ns = namespaces["std"]

        self.assertEqual(3, len(std_ns))

        self.assertTrue(std_ns.contains_action_name("echo"))
        self.assertTrue(std_ns.contains_action_name("http"))
        self.assertTrue(std_ns.contains_action_name("email"))

        self.assertEqual(std.EchoAction, std_ns.get_action_class("echo"))
        self.assertEqual(std.HTTPAction, std_ns.get_action_class("http"))
        self.assertEqual(std.SendEmailAction,
                         std_ns.get_action_class("email"))
