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


from mistral.actions import std_actions as std
from mistral.services import action_manager as a_m
from mistral.tests.unit import base


class ActionManagerTest(base.DbTestCase):

    def test_register_standard_actions(self):
        action_list = a_m.get_registered_actions()

        self._assert_single_item(action_list, name="std.echo")
        self._assert_single_item(action_list, name="std.email")
        self._assert_single_item(action_list, name="std.http")
        self._assert_single_item(action_list, name="std.mistral_http")
        self._assert_single_item(action_list, name="std.ssh")
        self._assert_single_item(action_list, name="std.javascript")

        self._assert_single_item(action_list, name="nova.servers_get")
        self._assert_single_item(
            action_list,
            name="nova.volumes_delete_server_volume"
        )

        server_find_action = self._assert_single_item(
            action_list,
            name="nova.servers_find"
        )
        self.assertIn('**', server_find_action.input)

        self._assert_single_item(action_list, name="keystone.users_list")
        self._assert_single_item(action_list, name="keystone.trusts_create")

        self._assert_single_item(action_list, name="glance.images_list")
        self._assert_single_item(action_list, name="glance.images_delete")

    def test_get_action_class(self):
        self.assertTrue(
            issubclass(a_m.get_action_class("std.echo"), std.EchoAction)
        )
        self.assertTrue(
            issubclass(a_m.get_action_class("std.http"), std.HTTPAction)
        )
        self.assertTrue(
            issubclass(
                a_m.get_action_class("std.mistral_http"),
                std.MistralHTTPAction
            )
        )
        self.assertTrue(
            issubclass(a_m.get_action_class("std.email"), std.SendEmailAction)
        )
        self.assertTrue(
            issubclass(
                a_m.get_action_class("std.javascript"),
                std.JavaScriptAction
            )
        )
