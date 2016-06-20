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

from oslo_utils import importutils

from mistral.actions.openstack.action_generator import base


SUPPORTED_MODULES = [
    'Nova', 'Glance', 'Keystone', 'Heat', 'Neutron', 'Cinder', 'Ceilometer',
    'Trove', 'Ironic', 'Baremetal Introspection', 'Swift', 'Zaqar', 'Barbican',
    'Mistral', 'Designate', 'Magnum', 'Murano', 'Tacker'
]


def all_generators():
    for mod_name in SUPPORTED_MODULES:
        prefix = mod_name.replace(' ', '')
        mod_namespace = mod_name.lower().replace(' ', '_')
        mod_cls_name = 'mistral.actions.openstack.actions.%sAction' % prefix
        mod_action_cls = importutils.import_class(mod_cls_name)
        generator_cls_name = '%sActionGenerator' % prefix

        yield type(
            generator_cls_name,
            (base.OpenStackActionGenerator,),
            {
                'action_namespace': mod_namespace,
                'base_action_class': mod_action_cls
            }
        )
