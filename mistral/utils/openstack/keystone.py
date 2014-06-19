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
from oslo.config import cfg

from mistral import context

CONF = cfg.CONF


def client():
    ctx = context.ctx()
    auth_url = CONF.keystone_authtoken.auth_uri

    keystone = ks_client.Client(username=ctx.user_name,
                                token=ctx.auth_token,
                                tenant_id=ctx.project_id,
                                auth_url=auth_url)
    keystone.management_url = auth_url

    return keystone


def _admin_client(trust_id=None, project_name=None):
    auth_url = CONF.keystone_authtoken.auth_uri

    client = ks_client.Client(username=CONF.keystone_authtoken.admin_user,
                              password=CONF.keystone_authtoken.admin_password,
                              project_name=project_name,
                              auth_url=auth_url,
                              trust_id=trust_id)
    client.management_url = auth_url

    return client


def client_for_admin(project_name):
    return _admin_client(project_name=project_name)


def client_for_trusts(trust_id):
    return _admin_client(trust_id=trust_id)
