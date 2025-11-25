# Copyright 2025 - NetCracker Technology Corp.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


#!/usr/bin/python
import six
from mistral_lib import exceptions
from keystoneclient.v3 import Client as KeystoneClient
from keystoneclient.v3.endpoints import Endpoint
from keystoneclient import service_catalog as ServiceCatalog
from novaclient.client import Client as NovaClient
from glanceclient import Client as GlanceClient


def nova_client(context):
    keystone_endpoint = get_keystone_endpoint_v2(context)
    nova_endpoint = get_endpoint_for_project(context, u'nova')

    client = NovaClient(
        2,
        username=None,
        api_key=None,
        endpoint_type=u'public',
        service_type=u'compute',
        auth_token=context.auth_token,
        tenant_id=context.project_id,
        region_name=keystone_endpoint.region,
        auth_url=keystone_endpoint.url,
        insecure=context.insecure
    )

    client.client.management_url = format_url(
        nova_endpoint.url,
        {u'tenant_id': context.project_id}
    )
    return client


def glance_client(context):
    glance_endpoint = get_endpoint_for_project(context, u'glance')

    return GlanceClient(
        glance_endpoint.url,
        region_name=glance_endpoint.region,
        token=context.auth_token,
        insecure=context.insecure
    )


def client(context):
    ctx = context.ctx()
    auth_url = ctx.auth_uri

    cl = KeystoneClient(
        user_id=ctx.user_id,
        token=ctx.auth_token,
        tenant_id=ctx.project_id,
        auth_url=auth_url,
        insecure=ctx.insecure
    )

    cl.management_url = auth_url

    return cl


def get_keystone_endpoint_v2(context):
    return get_endpoint_for_project(context=context, service_name=u'keystone',
                                    service_type=u'identity')


def obtain_service_catalog(context):
    token = context.auth_token

    if context.is_trust_scoped and is_token_trust_scoped(context, token):
        if context.trust_id is None:
            raise Exception(
                u"'trust_id' must be provided in the admin context."
            )

        trust_client = client_for_trusts(context, context.trust_id)
        response = trust_client.tokens.get_token_data(
            token,
            include_catalog=True
        )[u'token']
    else:
        response = context.service_catalog

        # Target service catalog may not be passed via API.
        if not response and context.is_target:
            response = client(context).tokens.get_token_data(
                token,
                include_catalog=True
            )[u'token']

    if not response:
        raise exceptions.MistralError(u"Unauthorized")

    service_catalog = ServiceCatalog.factory(response)

    return service_catalog


def client_for_trusts(context, trust_id):
    return _admin_client(context=context, trust_id=trust_id)


def _admin_client(context, trust_id=None, project_name=None):
    ctx = context.ctx()
    auth_url = context.auth_uri

    cl = KeystoneClient(
        username=context.admin_user,
        password=context.admin_password,
        project_name=project_name,
        auth_url=auth_url,
        trust_id=trust_id,
        insecure=ctx.insecure
    )

    cl.management_url = auth_url

    return cl


def is_token_trust_scoped(context, auth_token):
    admin_project_name = context.admin_tenant_name
    keystone_client = _admin_client(context=context,
                                    project_name=admin_project_name)

    token_info = keystone_client.tokens.validate(auth_token)

    return u'OS-TRUST:trust' in token_info


def get_endpoint_for_project(context, service_name=None, service_type=None):
    if service_name is None and service_type is None:
        raise exceptions.MistralException(
            u"Either 'service_name' or 'service_type' must be provided."
        )

    service_catalog = obtain_service_catalog(context)

    service_endpoints = service_catalog.get_endpoints(
        service_name=service_name,
        service_type=service_type,
        region_name=context.region_name
    )

    endpoint = None
    for endpoints in six.itervalues(service_endpoints):
        for ep in endpoints:
            # is V3 interface?
            if u'interface' in ep:
                interface_type = ep[u'interface']
                if context.os_actions_endpoint_type in interface_type:
                    endpoint = Endpoint(
                        None,
                        ep,
                        loaded=True
                    )
                    break
            # is V2 interface?
            if u'publicURL' in ep:
                endpoint_data = {
                    u'url': ep[u'publicURL'],
                    u'region': ep[u'region']
                }
                endpoint = endpoints.Endpoint(
                    None,
                    endpoint_data,
                    loaded=True
                )
                break

    if not endpoint:
        raise exceptions.MistralException(
            u"No endpoints found [service_name=%s, service_type=%s,"
            u" region_name=%s]"
            % (service_name, service_type, context.region_name)
        )
    else:
        return endpoint


def format_url(url_template, values):
    # Since we can't use keystone module, we can do similar thing:
    # see https://github.com/openstack/keystone/blob/master/keystone/
    # catalog/core.py#L42-L60
    return url_template.replace(u'$(', u'%(') % values
