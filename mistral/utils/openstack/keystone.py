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

import keystoneauth1.identity.generic as auth_plugins
from keystoneauth1 import session as ks_session
from keystoneclient.v3 import client as ks_client
from keystoneclient.v3 import endpoints as enp
from oslo_config import cfg
from oslo_utils import timeutils

from mistral import context

CONF = cfg.CONF


def client():
    ctx = context.ctx()
    auth_url = ctx.auth_uri

    cl = ks_client.Client(
        user_id=ctx.user_id,
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
    if service_name is None and service_type is None:
        raise Exception(
            "Either 'service_name' or 'service_type' must be provided."
        )

    ctx = context.ctx()

    token = ctx.auth_token

    if (ctx.is_trust_scoped and is_token_trust_scoped(token)):
        if ctx.trust_id is None:
            raise Exception(
                "'trust_id' must be provided in the admin context."
            )

        trust_client = client_for_trusts(ctx.trust_id)
        response = trust_client.tokens.get_token_data(
            token,
            include_catalog=True
        )
    else:
        response = client().tokens.get_token_data(token, include_catalog=True)

    endpoints = select_service_endpoints(
        service_name,
        service_type,
        response["token"]["catalog"])

    if not endpoints:
        raise Exception(
            "No endpoints found [service_name=%s, service_type=%s]"
            % (service_name, service_type)
        )
    else:
        # TODO(rakhmerov): We may have more than one endpoint because
        # TODO(rakhmerov): of regions and ideally we need a config option
        # TODO(rakhmerov): for region
        return endpoints[0]


def select_service_endpoints(service_name, service_type, services):
    endpoints = []

    for catalog in services:

        if service_name and catalog["name"] != service_name:
            continue

        if service_type and catalog["type"] != service_type:
            continue

        for endpoint in catalog["endpoints"]:
            # Keystone v2.0 uses <interface>URL while v3 only uses the
            # interface without the URL suffix.
            if CONF.os_actions_endpoint_type in endpoint["interface"]:
                endpoints.append(enp.Endpoint(None, endpoint, loaded=True))

    return endpoints


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


def get_admin_session():
    """Returns a keystone session from Mistral's service credentials."""

    auth = auth_plugins.Password(
        CONF.keystone_authtoken.auth_uri,
        username=CONF.keystone_authtoken.admin_user,
        password=CONF.keystone_authtoken.admin_password,
        project_name=CONF.keystone_authtoken.admin_tenant_name,
        # NOTE(jaosorior): Once mistral supports keystone v3 properly, we can
        # fetch the following values from the configuration.
        user_domain_name='Default',
        project_domain_name='Default')

    return ks_session.Session(auth=auth)


def will_expire_soon(expires_at):
    stale_duration = CONF.expiration_token_duration
    assert stale_duration, "expiration_token_duration must be specified"
    expires = timeutils.parse_isotime(expires_at)
    return timeutils.is_soon(expires, stale_duration)
