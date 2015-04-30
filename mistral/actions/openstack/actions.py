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

import inspect

from cinderclient.v1 import client as cinderclient
from glanceclient.v2 import client as glanceclient
from heatclient.v1 import client as heatclient
from keystoneclient import httpclient
from keystoneclient.v3 import client as keystoneclient
from neutronclient.v2_0 import client as neutronclient
from novaclient.v2 import client as novaclient
from oslo.config import cfg

from mistral.actions.openstack import base
from mistral import context
from mistral import exceptions as exc
from mistral.openstack.common import log
from mistral.utils.openstack import keystone as keystone_utils


LOG = log.getLogger(__name__)

CONF = cfg.CONF


class NovaAction(base.OpenStackAction):
    _client_class = novaclient.Client

    def _get_client(self):
        ctx = context.ctx()

        LOG.debug("Nova action security context: %s" % ctx)

        keystone_endpoint = keystone_utils.get_keystone_endpoint_v2()
        nova_endpoint = keystone_utils.get_endpoint_for_project('nova')

        client = self._client_class(
            username=None,
            api_key=None,
            endpoint_type='publicURL',
            service_type='compute',
            auth_token=ctx.auth_token,
            tenant_id=ctx.project_id,
            region_name=keystone_endpoint.region,
            auth_url=keystone_endpoint.url
        )

        client.client.management_url = keystone_utils.format_url(
            nova_endpoint.url,
            {'tenant_id': ctx.project_id}
        )

        return client


class GlanceAction(base.OpenStackAction):
    _client_class = glanceclient.Client

    def _get_client(self):
        ctx = context.ctx()

        LOG.debug("Glance action security context: %s" % ctx)

        glance_endpoint = keystone_utils.get_endpoint_for_project('glance')

        return self._client_class(
            glance_endpoint.url,
            region_name=glance_endpoint.region,
            token=ctx.auth_token
        )

    @classmethod
    def _get_fake_client(cls):
        return cls._client_class("")


class KeystoneAction(base.OpenStackAction):
    _client_class = keystoneclient.Client

    def _get_client(self):
        ctx = context.ctx()

        LOG.debug("Keystone action security context: %s" % ctx)

        kwargs = {
            'token': ctx.auth_token,
            'auth_url': CONF.keystone_authtoken.auth_uri,
            'project_id': ctx.project_id,
            'cacert': CONF.keystone_authtoken.cafile,
        }

        # In case of trust-scoped token explicitly pass endpoint parameter.
        if (ctx.is_trust_scoped
                or keystone_utils.is_token_trust_scoped(ctx.auth_token)):
            kwargs['endpoint'] = CONF.keystone_authtoken.auth_uri

        client = self._client_class(**kwargs)

        client.management_url = CONF.keystone_authtoken.auth_uri

        return client

    @classmethod
    def _get_fake_client(cls):
        # Here we need to replace httpclient authenticate method temporarily
        authenticate = httpclient.HTTPClient.authenticate

        httpclient.HTTPClient.authenticate = lambda x: True
        fake_client = cls._client_class()

        # Once we get fake client, return back authenticate method
        httpclient.HTTPClient.authenticate = authenticate

        return fake_client


class HeatAction(base.OpenStackAction):
    _client_class = heatclient.Client

    def _get_client(self):
        ctx = context.ctx()

        LOG.debug("Heat action security context: %s" % ctx)

        heat_endpoint = keystone_utils.get_endpoint_for_project('heat')

        endpoint_url = keystone_utils.format_url(
            heat_endpoint.url,
            {'tenant_id': ctx.project_id}
        )

        return self._client_class(
            endpoint_url,
            region_name=heat_endpoint.region,
            token=ctx.auth_token,
            username=ctx.user_name
        )

    @classmethod
    def _get_fake_client(cls):
        return cls._client_class("")

    def run(self):
        try:
            method = self._get_client_method(self._get_client())
            result = method(**self._kwargs_for_run)
            if inspect.isgenerator(result):
                return [v for v in result]
            return result
        except Exception as e:
            raise exc.ActionException("%s failed: %s"
                                      % (self.__class__.__name__, e))


class NeutronAction(base.OpenStackAction):
    _client_class = neutronclient.Client

    def _get_client(self):
        ctx = context.ctx()

        LOG.debug("Neutron action security context: %s" % ctx)

        neutron_endpoint = keystone_utils.get_endpoint_for_project('neutron')

        return self._client_class(
            endpoint_url=neutron_endpoint.url,
            region_name=neutron_endpoint.region,
            token=ctx.auth_token,
            auth_url=CONF.keystone_authtoken.auth_uri
        )


class CinderAction(base.OpenStackAction):
    _client_class = cinderclient.Client

    def _get_client(self):
        ctx = context.ctx()

        LOG.debug("Cinder action security context: %s" % ctx)

        cinder_endpoint = keystone_utils.get_endpoint_for_project(
            service_type='volume'
        )

        cinder_url = keystone_utils.format_url(
            cinder_endpoint.url,
            {'tenant_id': ctx.project_id}
        )

        client = self._client_class(
            ctx.user_name,
            ctx.auth_token,
            project_id=ctx.project_id,
            auth_url=cinder_url,
            region_name=cinder_endpoint.region
        )

        client.client.auth_token = ctx.auth_token
        client.client.management_url = cinder_url

        return client

    @classmethod
    def _get_fake_client(cls):
        return cls._client_class()
