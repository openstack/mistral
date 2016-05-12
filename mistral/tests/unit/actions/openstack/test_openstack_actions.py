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

    @mock.patch.object(actions.CeilometerAction, '_get_client')
    def test_ceilometer_action(self, mocked):
        method_name = "alarms.get"
        action_class = actions.CeilometerAction
        action_class.client_method_name = method_name
        params = {'alarm_id': '1234-abcd'}
        action = action_class(**params)
        action.run()

        self.assertTrue(mocked().alarms.get.called)
        mocked().alarms.get.assert_called_once_with(alarm_id="1234-abcd")

    @mock.patch.object(actions.TroveAction, '_get_client')
    def test_trove_action(self, mocked):
        method_name = "instances.get"
        action_class = actions.TroveAction
        action_class.client_method_name = method_name
        params = {'instance': '1234-abcd'}
        action = action_class(**params)
        action.run()

        self.assertTrue(mocked().instances.get.called)
        mocked().instances.get.assert_called_once_with(instance="1234-abcd")

    @mock.patch.object(actions.IronicAction, '_get_client')
    def test_ironic_action(self, mocked):
        method_name = "node.get"
        action_class = actions.IronicAction
        action_class.client_method_name = method_name
        params = {'node': '1234-abcd'}
        action = action_class(**params)
        action.run()

        self.assertTrue(mocked().node.get.called)
        mocked().node.get.assert_called_once_with(node="1234-abcd")

    @mock.patch.object(actions.BaremetalIntrospectionAction, '_get_client')
    def test_baremetal_introspector_action(self, mocked):
        method_name = "get_status"
        action_class = actions.BaremetalIntrospectionAction
        action_class.client_method_name = method_name
        params = {'uuid': '1234'}
        action = action_class(**params)
        action.run()

        self.assertTrue(mocked().get_status.called)
        mocked().get_status.assert_called_once_with(uuid="1234")

    @mock.patch.object(actions.MistralAction, '_get_client')
    def test_mistral_action(self, mocked):
        method_name = "workflows.get"
        action_class = actions.MistralAction
        action_class.client_method_name = method_name
        params = {'name': '1234-abcd'}
        action = action_class(**params)
        action.run()

        self.assertTrue(mocked().workflows.get.called)
        mocked().workflows.get.assert_called_once_with(name="1234-abcd")

    @mock.patch.object(actions.SwiftAction, '_get_client')
    def test_swift_action(self, mocked):
        method_name = "get_object"
        action_class = actions.SwiftAction
        action_class.client_method_name = method_name
        params = {'container': 'foo', 'object': 'bar'}
        action = action_class(**params)
        action.run()

        self.assertTrue(mocked().get_object.called)
        mocked().get_object.assert_called_once_with(container='foo',
                                                    object='bar')

    @mock.patch.object(actions.ZaqarAction, '_get_client')
    def test_zaqar_action(self, mocked):
        method_name = "queue_messages"
        action_class = actions.ZaqarAction
        action_class.client_method_name = method_name
        params = {'queue_name': 'foo'}
        action = action_class(**params)
        action.run()

        mocked().queue.assert_called_once_with('foo')
        mocked().queue().messages.assert_called_once_with()

    @mock.patch.object(actions.BarbicanAction, '_get_client')
    def test_barbican_action(self, mocked):
        method_name = "orders_list"
        action_class = actions.BarbicanAction
        action_class.client_method_name = method_name
        params = {'limit': 5}
        action = action_class(**params)
        action.run()

        self.assertTrue(mocked().orders_list.called)
        mocked().orders_list.assert_called_once_with(limit=5)

    @mock.patch.object(actions.DesignateAction, '_get_client')
    def test_designate_action(self, mocked):
        method_name = "domain.get"
        action_class = actions.DesignateAction
        action_class.client_method_name = method_name
        params = {'domain': 'example.com'}
        action = action_class(**params)
        action.run()

        self.assertTrue(mocked().domain.get.called)
        mocked().domain.get.assert_called_once_with(domain="example.com")
