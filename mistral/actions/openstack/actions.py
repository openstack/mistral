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

from glanceclient.v2 import client as glanceclient
from keystoneclient.v3 import client as keystoneclient
from novaclient.v1_1 import client as novaclient
from oslo.config import cfg

from mistral.actions.openstack import base
from mistral import context
from mistral.utils.openstack import keystone as keystone_utils


CONF = cfg.CONF


class NovaAction(base.OpenStackAction):
    _client_class = novaclient.Client

    def _get_client(self):
        ctx = context.ctx()
        auth_url = keystone_utils.get_keystone_url_v2()

        return self._client_class(username=ctx.user_name,
                                  auth_token=ctx.auth_token,
                                  tenant_id=ctx.project_id,
                                  auth_url=auth_url)


class GlanceAction(base.OpenStackAction):
    _client_class = glanceclient.Client

    def _get_client(self):
        ctx = context.ctx()
        endpoint_url = keystone_utils.get_endpoint_for_project('glance')

        return self._client_class(endpoint_url, token=ctx.auth_token)


class KeystoneAction(base.OpenStackAction):
    _client_class = keystoneclient.Client

    def _get_client(self):
        ctx = context.ctx()
        auth_url = CONF.keystone_authtoken.auth_uri

        return self._client_class(token=ctx.auth_token,
                                  auth_url=auth_url)
