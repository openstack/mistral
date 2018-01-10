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
import contextlib
import os

from oslo_config import cfg

import mock

from mistral.actions import generator_factory
from mistral.actions.openstack.action_generator import base as generator_base
from mistral.actions.openstack import actions
from mistral import config

from mistral.tests.unit import base

ABSOLUTE_TEST_MAPPING_PATH = os.path.realpath(
    os.path.join(os.path.dirname(__file__),
                 "../../../resources/openstack/test_mapping.json")
)

RELATIVE_TEST_MAPPING_PATH = "tests/resources/openstack/test_mapping.json"

MODULE_MAPPING = {
    'nova': ['nova.servers_get', actions.NovaAction],
    'glance': ['glance.images_list', actions.GlanceAction],
    'keystone': ['keystone.users_create', actions.KeystoneAction],
    'heat': ['heat.stacks_list', actions.HeatAction],
    'neutron': ['neutron.show_network', actions.NeutronAction],
    'cinder': ['cinder.volumes_list', actions.CinderAction],
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
    'tacker': ['tacker.list_vims', actions.TackerAction],
    'senlin': ['senlin.get_profile', actions.SenlinAction],
    'aodh': ['aodh.alarm_list', actions.AodhAction],
    'gnocchi': ['gnocchi.metric_list', actions.GnocchiAction],
    'glare': ['glare.artifacts_list', actions.GlareAction]
}

EXTRA_MODULES = ['neutron', 'swift', 'zaqar', 'tacker']


CONF = cfg.CONF
CONF.register_opt(config.os_actions_mapping_path)


class GeneratorTest(base.BaseTest):

    def setUp(self):
        super(GeneratorTest, self).setUp()

        # The baremetal inspector client expects the service to be running
        # when it is initialised and attempts to connect. This mocks out this
        # service only and returns a simple function that can be used by the
        # inspection utils.
        self.baremetal_patch = mock.patch.object(
            actions.BaremetalIntrospectionAction,
            "get_fake_client_method",
            return_value=lambda x: None)

        self.baremetal_patch.start()
        self.addCleanup(self.baremetal_patch.stop)

    def test_generator(self):
        for generator_cls in generator_factory.all_generators():
            action_classes = generator_cls.create_actions()

            action_name = MODULE_MAPPING[generator_cls.action_namespace][0]
            action_cls = MODULE_MAPPING[generator_cls.action_namespace][1]
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

            modules = CONF.openstack_actions.modules_support_region
            if generator_cls.action_namespace in modules:
                self.assertIn('action_region', action['arg_list'])

    def test_missing_module_from_mapping(self):
        with _patch_openstack_action_mapping_path(RELATIVE_TEST_MAPPING_PATH):
            for generator_cls in generator_factory.all_generators():
                action_classes = generator_cls.create_actions()
                action_names = [action['name'] for action in action_classes]

                cls = MODULE_MAPPING.get(generator_cls.action_namespace)[1]
                if cls == actions.NovaAction:
                    self.assertIn('nova.servers_get', action_names)
                    self.assertEqual(3, len(action_names))
                elif cls not in (actions.GlanceAction, actions.KeystoneAction):
                    self.assertEqual([], action_names)

    def test_absolute_mapping_path(self):
        with _patch_openstack_action_mapping_path(ABSOLUTE_TEST_MAPPING_PATH):
            self.assertTrue(os.path.isabs(ABSOLUTE_TEST_MAPPING_PATH),
                            "Mapping path is relative: %s" %
                            ABSOLUTE_TEST_MAPPING_PATH)
            for generator_cls in generator_factory.all_generators():
                action_classes = generator_cls.create_actions()
                action_names = [action['name'] for action in action_classes]

                cls = MODULE_MAPPING.get(generator_cls.action_namespace)[1]
                if cls == actions.NovaAction:
                    self.assertIn('nova.servers_get', action_names)
                    self.assertEqual(3, len(action_names))
                elif cls not in (actions.GlanceAction, actions.KeystoneAction):
                    self.assertEqual([], action_names)

    def test_prepare_action_inputs(self):
        inputs = generator_base.OpenStackActionGenerator.prepare_action_inputs(
            'a,b,c',
            added=['region=RegionOne']
        )

        self.assertEqual('a, b, c, region=RegionOne', inputs)

        inputs = generator_base.OpenStackActionGenerator.prepare_action_inputs(
            'a,b,c=1',
            added=['region=RegionOne']
        )

        self.assertEqual('a, b, region=RegionOne, c=1', inputs)

        inputs = generator_base.OpenStackActionGenerator.prepare_action_inputs(
            'a,b,c=1,**kwargs',
            added=['region=RegionOne']
        )

        self.assertEqual('a, b, region=RegionOne, c=1, **kwargs', inputs)

        inputs = generator_base.OpenStackActionGenerator.prepare_action_inputs(
            '**kwargs',
            added=['region=RegionOne']
        )

        self.assertEqual('region=RegionOne, **kwargs', inputs)

        inputs = generator_base.OpenStackActionGenerator.prepare_action_inputs(
            '',
            added=['region=RegionOne']
        )

        self.assertEqual('region=RegionOne', inputs)


@contextlib.contextmanager
def _patch_openstack_action_mapping_path(path):
    original_path = CONF.openstack_actions_mapping_path
    CONF.set_default("openstack_actions_mapping_path", path)
    yield
    CONF.set_default("openstack_actions_mapping_path", original_path)
