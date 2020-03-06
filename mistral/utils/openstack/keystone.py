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

from keystoneauth1 import loading
from keystoneclient.v3 import client as ks_client
from oslo_config import cfg

from mistral import context

CONF = cfg.CONF


def client():
    ctx = context.ctx()
    auth_url = ctx.auth_uri or CONF.keystone_authtoken.www_authenticate_uri

    cl = ks_client.Client(
        user_id=ctx.user_id,
        token=ctx.auth_token,
        tenant_id=ctx.project_id,
        auth_url=auth_url
    )

    cl.management_url = auth_url

    return cl


def client_for_admin():
    return _admin_client()


def client_for_trusts(trust_id):
    return _admin_client(trust_id=trust_id)


def _admin_client(trust_id=None):
    if CONF.keystone_authtoken.auth_type is None:
        auth_url = CONF.keystone_authtoken.www_authenticate_uri
        project_name = CONF.keystone_authtoken.admin_tenant_name

        # You can't use trust and project together

        if trust_id:
            project_name = None

        cl = ks_client.Client(
            username=CONF.keystone_authtoken.admin_user,
            password=CONF.keystone_authtoken.admin_password,
            project_name=project_name,
            auth_url=auth_url,
            trusts=trust_id
        )

        cl.management_url = auth_url

        return cl
    else:
        kwargs = {}

        if trust_id:
            # Remove domain_id, domain_name, project_name and project_id,
            # since we need a trust scoped auth object
            kwargs['domain_id'] = None
            kwargs['domain_name'] = None
            kwargs['project_name'] = None
            kwargs['project_domain_name'] = None
            kwargs['project_id'] = None
            kwargs['trust_id'] = trust_id

        auth = loading.load_auth_from_conf_options(
            CONF,
            'keystone_authtoken',
            **kwargs
        )
        sess = loading.load_session_from_conf_options(
            CONF,
            'keystone',
            auth=auth
        )

        return ks_client.Client(session=sess)
