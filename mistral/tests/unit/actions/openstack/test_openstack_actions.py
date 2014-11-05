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

import mock
from oslotest import base

from mistral.actions.openstack import actions


class OpenStackActionTest(base.BaseTestCase):
    @mock.patch.object(actions.NovaAction, '_get_client')
    def test_nova_action(self, mocked):
        method_name = "servers.get"
        action_class = actions.NovaAction
        action_class.client_method_name = method_name
        params = {'server': '1234-abcd'}
        action = action_class(**params)
        action.run()

        self.assertTrue(mocked().servers.get.called)
        mocked().servers.get.assert_called_once_with(server="1234-abcd")

    @mock.patch.object(actions.GlanceAction, '_get_client')
    def test_glance_action(self, mocked):
        method_name = "images.delete"
        action_class = actions.GlanceAction
        action_class.client_method_name = method_name
        params = {'image': '1234-abcd'}
        action = action_class(**params)
        action.run()

        self.assertTrue(mocked().images.delete.called)
        mocked().images.delete.assert_called_once_with(image="1234-abcd")

    @mock.patch.object(actions.KeystoneAction, '_get_client')
    def test_keystone_action(self, mocked):
        method_name = "users.get"
        action_class = actions.KeystoneAction
        action_class.client_method_name = method_name
        params = {'user': '1234-abcd'}
        action = action_class(**params)
        action.run()

        self.assertTrue(mocked().users.get.called)
        mocked().users.get.assert_called_once_with(user="1234-abcd")

    @mock.patch.object(actions.HeatAction, '_get_client')
    def test_heat_action(self, mocked):
        method_name = "stacks.get"
        action_class = actions.HeatAction
        action_class.client_method_name = method_name
        params = {'id': '1234-abcd'}
        action = action_class(**params)
        action.run()

        self.assertTrue(mocked().stacks.get.called)
        mocked().stacks.get.assert_called_once_with(id="1234-abcd")

    @mock.patch.object(actions.NeutronAction, '_get_client')
    def test_neutron_action(self, mocked):
        method_name = "show_network"
        action_class = actions.NeutronAction
        action_class.client_method_name = method_name
        params = {'id': '1234-abcd'}
        action = action_class(**params)
        action.run()

        self.assertTrue(mocked().show_network.called)
        mocked().show_network.assert_called_once_with(id="1234-abcd")

    @mock.patch.object(actions.CinderAction, '_get_client')
    def test_cinder_action(self, mocked):
        method_name = "volumes.get"
        action_class = actions.CinderAction
        action_class.client_method_name = method_name
        params = {'volume': '1234-abcd'}
        action = action_class(**params)
        action.run()

        self.assertTrue(mocked().volumes.get.called)
        mocked().volumes.get.assert_called_once_with(volume="1234-abcd")
