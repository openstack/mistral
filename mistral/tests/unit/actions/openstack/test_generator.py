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

from mistral.actions import generator_factory
from mistral.actions.openstack import actions
from mistral.tests.unit import base


MODULE_MAPPING = {
    'nova': ['nova.servers_get', actions.NovaAction],
    'glance': ['glance.images_list', actions.GlanceAction],
    'keystone': ['keystone.users_create', actions.KeystoneAction],
    'heat': ['heat.stacks_list', actions.HeatAction],
    'neutron': ['neutron.show_network', actions.NeutronAction],
    'cinder': ['cinder.volumes_list', actions.CinderAction],
    'ceilometer': ['ceilometer.alarms_list', actions.CeilometerAction],
    'trove': ['trove.instances_list', actions.TroveAction],
    'ironic': ['ironic.node_list', actions.IronicAction],
    'baremetal_introspection': ['baremetal_introspection.introspect',
                                actions.BaremetalIntrospectionAction],
    'swift': ['swift.head_account', actions.SwiftAction],
    'zaqar': ['zaqar.queue_messages', actions.ZaqarAction],
    'barbican': ['barbican.orders_list', actions.BarbicanAction],
    'mistral': ['mistral.workflows_get', actions.MistralAction],
    'designate': ['designate.domains_list', actions.DesignateAction],
    'magnum': ['magnum.bays_list', actions.MagnumAction],
    'murano': ['murano.deployments_list', actions.MuranoAction],
    'tacker': ['tacker.list_vims', actions.TackerAction]
}

EXTRA_MODULES = ['neutron', 'swift', 'zaqar', 'tacker']


class GeneratorTest(base.BaseTest):
    def test_generator(self):
        for generator_cls in generator_factory.all_generators():
            action_classes = generator_cls.create_actions()

            action_name = MODULE_MAPPING.get(generator_cls.action_namespace)[0]
            action_cls = MODULE_MAPPING.get(generator_cls.action_namespace)[1]
            method_name_pre = action_name.split('.')[1]
            method_name = (
                method_name_pre
                if generator_cls.action_namespace in EXTRA_MODULES
                else method_name_pre.replace('_', '.')
            )

            action = self._assert_single_item(
                action_classes,
                name=action_name
            )

            self.assertTrue(issubclass(action['class'], action_cls))
            self.assertEqual(method_name, action['class'].client_method_name)
