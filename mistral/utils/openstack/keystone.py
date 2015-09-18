# Copyright (c) 2013 Mirantis Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from keystoneclient.v3 import client as ks_client
from oslo_config import cfg

from mistral import context

CONF = cfg.CONF


def client():
    ctx = context.ctx()
    auth_url = CONF.keystone_authtoken.auth_uri

    cl = ks_client.Client(
        username=ctx.user_name,
        token=ctx.auth_token,
        tenant_id=ctx.project_id,
        auth_url=auth_url
    )

    cl.management_url = auth_url

    return cl


def _admin_client(trust_id=None, project_name=None):
    auth_url = CONF.keystone_authtoken.auth_uri

    cl = ks_client.Client(
        username=CONF.keystone_authtoken.admin_user,
        password=CONF.keystone_authtoken.admin_password,
        project_name=project_name,
        auth_url=auth_url,
        trust_id=trust_id
    )

    cl.management_url = auth_url

    return cl


def client_for_admin(project_name):
    return _admin_client(project_name=project_name)


def client_for_trusts(trust_id):
    return _admin_client(trust_id=trust_id)


def get_endpoint_for_project(service_name=None, service_type=None):
    admin_project_name = CONF.keystone_authtoken.admin_tenant_name
    keystone_client = _admin_client(project_name=admin_project_name)
    service_list = keystone_client.services.list()

    if service_name:
        service_ids = [s.id for s in service_list if s.name == service_name]
    elif service_type:
        service_ids = [s.id for s in service_list if s.type == service_type]
    else:
        raise Exception(
            "Either 'service_name' or 'service_type' must be provided."
        )

    if not service_ids:
        raise Exception("Either service '%s' or service type "
                        "'%s' doesn't exist!" % (service_name, service_type))

    endpoints = keystone_client.endpoints.list(
        service=service_ids[0],
        interface='public'
    )

    if not endpoints:
        raise Exception(
            "No endpoints found [service_name=%s, service_type=%s]"
            % (service_name, service_type)
        )

    # TODO(rakhmerov): We may have more than one endpoint because of regions
    # TODO(rakhmerov): and ideally we need a config option for region
    return endpoints[0]


def get_keystone_endpoint_v2():
    return get_endpoint_for_project('keystone')


def get_keystone_url_v2():
    return get_endpoint_for_project('keystone').url


def format_url(url_template, values):
    # Since we can't use keystone module, we can do similar thing:
    # see https://github.com/openstack/keystone/blob/master/keystone/
    # catalog/core.py#L42-L60
    return url_template.replace('$(', '%(') % values


def is_token_trust_scoped(auth_token):
    admin_project_name = CONF.keystone_authtoken.admin_tenant_name
    keystone_client = _admin_client(project_name=admin_project_name)

    token_info = keystone_client.tokens.validate(auth_token)

    return 'OS-TRUST:trust' in token_info
