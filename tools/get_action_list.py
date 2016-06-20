# Copyright 2015 - Mirantis, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
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

import argparse
import collections
import inspect
import json
import os

from barbicanclient import base as barbican_base
from barbicanclient import client as barbicanclient
from ceilometerclient.v2 import client as ceilometerclient
from cinderclient.openstack.common.apiclient import base as cinder_base
from cinderclient.v2 import client as cinderclient
from designateclient import client as designateclient
from glanceclient.v2 import client as glanceclient
from heatclient.openstack.common.apiclient import base as heat_base
from heatclient.v1 import client as heatclient
from ironicclient.common import base as ironic_base
from ironicclient.v1 import client as ironicclient
from keystoneclient import base as keystone_base
from keystoneclient.v3 import client as keystoneclient
from magnumclient.common import base as magnum_base
from magnumclient.v1 import client as magnumclient
from mistralclient.api import base as mistral_base
from mistralclient.api.v2 import client as mistralclient
from muranoclient.common import base as murano_base
from muranoclient.v1 import client as muranoclient
from novaclient import base as nova_base
from novaclient import client as novaclient
from troveclient import base as trove_base
from troveclient.v1 import client as troveclient

# TODO(nmakhotkin): Find a rational way to do it for neutron.
# TODO(nmakhotkin): Implement recursive way of searching for managers
# TODO(nmakhotkin): (e.g. keystone).
# TODO(dprince): Need to update ironic_inspector_client before we can
# plug it in cleanly here.
# TODO(dprince): Swiftclient doesn't currently support discovery
# like we do in this class.
# TODO(therve): Zaqarclient doesn't currently support discovery
# like we do in this class.
# TODO(sa709c): Tackerclient doesn't currently support discovery
# like we do in this class.

"""It is simple CLI tool which allows to see and update mapping.json file
if needed. mapping.json contains all allowing OpenStack actions sorted by
service name. Usage example:

  python tools/get_action_list.py nova

The result will be simple JSON containing action name as a key and method
path as a value. For updating mapping.json it is need to copy all keys and
values of the result to corresponding section of mapping.json:

  ...mapping.json...
  "nova": {
      <put it here>
  },
  ...mapping.json...


Note: in case of Keystone service, correct OS_AUTH_URL v3 and the rest auth
info must be provided. It can be provided either via environment variables
or CLI arguments. See --help for details.
"""

BASE_HEAT_MANAGER = heat_base.HookableMixin
BASE_NOVA_MANAGER = nova_base.HookableMixin
BASE_KEYSTONE_MANAGER = keystone_base.Manager
BASE_CINDER_MANAGER = cinder_base.HookableMixin
BASE_MISTRAL_MANAGER = mistral_base.ResourceManager
BASE_TROVE_MANAGER = trove_base.Manager
BASE_IRONIC_MANAGER = ironic_base.Manager
BASE_BARBICAN_MANAGER = barbican_base.BaseEntityManager
BASE_MAGNUM_MANAGER = magnum_base.Manager
BASE_MURANO_MANAGER = murano_base.Manager


def get_parser():
    parser = argparse.ArgumentParser(
        description='Gets All needed methods of OpenStack clients.',
        usage="python get_action_list.py <service_name>"
    )
    parser.add_argument(
        'service',
        choices=CLIENTS.keys(),
        help='Service name which methods need to be found.'
    )
    parser.add_argument(
        '--os-username',
        dest='username',
        default=os.environ.get('OS_USERNAME', 'admin'),
        help='Authentication username (Env: OS_USERNAME)'
    )
    parser.add_argument(
        '--os-password',
        dest='password',
        default=os.environ.get('OS_PASSWORD', 'openstack'),
        help='Authentication password (Env: OS_PASSWORD)'
    )
    parser.add_argument(
        '--os-tenant-name',
        dest='tenant_name',
        default=os.environ.get('OS_TENANT_NAME', 'Default'),
        help='Authentication tenant name (Env: OS_TENANT_NAME)'
    )
    parser.add_argument(
        '--os-auth-url',
        dest='auth_url',
        default=os.environ.get('OS_AUTH_URL'),
        help='Authentication URL (Env: OS_AUTH_URL)'
    )

    return parser


GLANCE_NAMESPACE_LIST = [
    'image_members', 'image_tags', 'images', 'schemas', 'tasks',
    'metadefs_resource_type', 'metadefs_property', 'metadefs_object',
    'metadefs_tag', 'metadefs_namespace', 'versions'
]

CEILOMETER_NAMESPACE_LIST = [
    'alarms', 'capabilities', 'event_types', 'events', 'meters',
    'new_samples', 'query_alarm_history', 'query_alarms', 'query_samples',
    'resources', 'samples', 'statistics', 'trait_descriptions', 'traits'
]

DESIGNATE_NAMESPACE_LIST = [
    'diagnostics', 'domains', 'quotas', 'records', 'reports', 'servers',
    'sync', 'touch'
]


def get_nova_client(**kwargs):
    return novaclient.Client(2)


def get_keystone_client(**kwargs):
    return keystoneclient.Client(**kwargs)


def get_glance_client(**kwargs):
    return glanceclient.Client(kwargs.get('auth_url'))


def get_heat_client(**kwargs):
    return heatclient.Client('')


def get_ceilometer_client(**kwargs):
    return ceilometerclient.Client('')


def get_cinder_client(**kwargs):
    return cinderclient.Client()


def get_mistral_client(**kwargs):
    return mistralclient.Client()


def get_trove_client(**kwargs):
    return troveclient.Client('username', 'password')


def get_ironic_client(**kwargs):
    return ironicclient.Client("http://127.0.0.1:6385/")


def get_barbican_client(**kwargs):
    return barbicanclient.Client(
        project_id="1",
        endpoint="http://127.0.0.1:9311"
    )


def get_designate_client(**kwargs):
    return designateclient.Client('1')


def get_magnum_client(**kwargs):
    return magnumclient.Client()


def get_murano_client(**kwargs):
    return muranoclient.Client('')


CLIENTS = {
    'nova': get_nova_client,
    'heat': get_heat_client,
    'ceilometer': get_ceilometer_client,
    'cinder': get_cinder_client,
    'keystone': get_keystone_client,
    'glance': get_glance_client,
    'trove': get_trove_client,
    'ironic': get_ironic_client,
    'barbican': get_barbican_client,
    'mistral': get_mistral_client,
    'designate': get_designate_client,
    'magnum': get_magnum_client,
    'murano': get_murano_client,
    # 'neutron': get_nova_client
    # 'baremetal_introspection': ...
    # 'swift': ...
    # 'zaqar': ...
}
BASE_MANAGERS = {
    'nova': BASE_NOVA_MANAGER,
    'heat': BASE_HEAT_MANAGER,
    'ceilometer': None,
    'cinder': BASE_CINDER_MANAGER,
    'keystone': BASE_KEYSTONE_MANAGER,
    'glance': None,
    'trove': BASE_TROVE_MANAGER,
    'ironic': BASE_IRONIC_MANAGER,
    'barbican': BASE_BARBICAN_MANAGER,
    'mistral': BASE_MISTRAL_MANAGER,
    'designate': None,
    'magnum': BASE_MAGNUM_MANAGER,
    'murano': BASE_MURANO_MANAGER,
    # 'neutron': BASE_NOVA_MANAGER
    # 'baremetal_introspection': ...
    # 'swift': ...
    # 'zaqar': ...
}
NAMESPACES = {
    'glance': GLANCE_NAMESPACE_LIST,
    'ceilometer': CEILOMETER_NAMESPACE_LIST,
    'designate': DESIGNATE_NAMESPACE_LIST
}
ALLOWED_ATTRS = ['service_catalog', 'catalog']
FORBIDDEN_METHODS = [
    'add_hook', 'alternate_service_type', 'completion_cache', 'run_hooks',
    'write_to_completion_cache', 'model', 'build_key_only_query', 'build_url',
    'head', 'put', 'unvalidated_model'
]


def get_public_attrs(obj):
    all_attrs = dir(obj)

    return [a for a in all_attrs if not a.startswith('_')]


def get_public_methods(attr, client):
    hierarchy_list = attr.split('.')
    attribute = client

    for attr in hierarchy_list:
        attribute = getattr(attribute, attr)
    all_attributes_list = get_public_attrs(attribute)

    methods = []
    for a in all_attributes_list:
        allowed = a in ALLOWED_ATTRS
        forbidden = a in FORBIDDEN_METHODS

        if (not forbidden and
                (allowed or inspect.ismethod(getattr(attribute, a)))):
            methods.append(a)

    return methods


def get_manager_list(service_name, client):
    base_manager = BASE_MANAGERS[service_name]

    if not base_manager:
        return NAMESPACES[service_name]

    public_attrs = get_public_attrs(client)

    manager_list = []

    for attr in public_attrs:
        if (isinstance(getattr(client, attr), base_manager)
                or attr in ALLOWED_ATTRS):
            manager_list.append(attr)

    return manager_list


def get_mapping_for_service(service, client):
    mapping = collections.OrderedDict()
    for man in get_manager_list(service, client):
        public_methods = get_public_methods(man, client)
        for method in public_methods:
            key = "%s_%s" % (man, method)
            value = "%s.%s" % (man, method)
            mapping[key] = value

    return mapping


def print_mapping(mapping):
    print(json.dumps(mapping, indent=8, separators=(',', ': ')))


if __name__ == "__main__":
    args = get_parser().parse_args()

    auth_info = {
        'username': args.username,
        'tenant_name': args.tenant_name,
        'password': args.password,
        'auth_url': args.auth_url
    }

    service = args.service
    client = CLIENTS.get(service)(**auth_info)

    print("Find methods for service: %s..." % service)

    print_mapping(get_mapping_for_service(service, client))
