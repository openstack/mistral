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

import functools

from oslo_config import cfg
from oslo_log import log
from oslo_utils import importutils

from keystoneclient.auth import identity
from keystoneclient import httpclient

barbicanclient = importutils.try_import('barbicanclient.client')
ceilometerclient = importutils.try_import('ceilometerclient.v2.client')
cinderclient = importutils.try_import('cinderclient.v2.client')
designateclient = importutils.try_import('designateclient.v1')
glanceclient = importutils.try_import('glanceclient.v2.client')
heatclient = importutils.try_import('heatclient.v1.client')
keystoneclient = importutils.try_import('keystoneclient.v3.client')
ironic_inspector_client = importutils.try_import('ironic_inspector_client.v1')
ironicclient = importutils.try_import('ironicclient.v1.client')
magnumclient = importutils.try_import('magnumclient.v1.client')
mistralclient = importutils.try_import('mistralclient.api.v2.client')
muranoclient = importutils.try_import('muranoclient.v1.client')
neutronclient = importutils.try_import('neutronclient.v2_0.client')
novaclient = importutils.try_import('novaclient.client')
swift_client = importutils.try_import('swiftclient.client')
tackerclient = importutils.try_import('tackerclient.v1_0.client')
troveclient = importutils.try_import('troveclient.v1.client')
zaqarclient = importutils.try_import('zaqarclient.queues.v2.client')

from mistral.actions.openstack import base
from mistral import context
from mistral.utils import inspect_utils
from mistral.utils.openstack import keystone as keystone_utils


LOG = log.getLogger(__name__)

CONF = cfg.CONF


class NovaAction(base.OpenStackAction):
    def _create_client(self):
        ctx = context.ctx()

        LOG.debug("Nova action security context: %s" % ctx)

        keystone_endpoint = keystone_utils.get_keystone_endpoint_v2()
        nova_endpoint = keystone_utils.get_endpoint_for_project('nova')

        client = novaclient.Client(
            2,
            username=None,
            api_key=None,
            endpoint_type=CONF.os_actions_endpoint_type,
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

    @classmethod
    def _get_fake_client(cls):
        return novaclient.Client(2)


class GlanceAction(base.OpenStackAction):

    @classmethod
    def _get_client_class(cls):
        return glanceclient.Client

    def _create_client(self):
        ctx = context.ctx()

        LOG.debug("Glance action security context: %s" % ctx)

        glance_endpoint = keystone_utils.get_endpoint_for_project('glance')

        return self._get_client_class()(
            glance_endpoint.url,
            region_name=glance_endpoint.region,
            token=ctx.auth_token
        )

    @classmethod
    def _get_fake_client(cls):
        return cls._get_client_class()("fake_endpoint")


class KeystoneAction(base.OpenStackAction):

    @classmethod
    def _get_client_class(cls):
        return keystoneclient.Client

    def _create_client(self):
        ctx = context.ctx()

        LOG.debug("Keystone action security context: %s" % ctx)

        # TODO(akovi) cacert is deprecated in favor of session
        # TODO(akovi) this piece of code should be refactored
        # TODO(akovi) to follow the new guide lines
        kwargs = {
            'token': ctx.auth_token,
            'auth_url': ctx.auth_uri,
            'project_id': ctx.project_id,
            'cacert': ctx.auth_cacert,
        }

        # In case of trust-scoped token explicitly pass endpoint parameter.
        if (ctx.is_trust_scoped
                or keystone_utils.is_token_trust_scoped(ctx.auth_token)):
            kwargs['endpoint'] = ctx.auth_uri

        client = self._get_client_class()(**kwargs)

        client.management_url = ctx.auth_uri

        return client

    @classmethod
    def _get_fake_client(cls):
        # Here we need to replace httpclient authenticate method temporarily
        authenticate = httpclient.HTTPClient.authenticate

        httpclient.HTTPClient.authenticate = lambda x: True
        fake_client = cls._get_client_class()()

        # Once we get fake client, return back authenticate method
        httpclient.HTTPClient.authenticate = authenticate

        return fake_client


class CeilometerAction(base.OpenStackAction):

    @classmethod
    def _get_client_class(cls):
        return ceilometerclient.Client

    def _create_client(self):
        ctx = context.ctx()

        LOG.debug("Ceilometer action security context: %s" % ctx)

        ceilometer_endpoint = keystone_utils.get_endpoint_for_project(
            'ceilometer'
        )

        endpoint_url = keystone_utils.format_url(
            ceilometer_endpoint.url,
            {'tenant_id': ctx.project_id}
        )

        return self._get_client_class()(
            endpoint_url,
            region_name=ceilometer_endpoint.region,
            token=ctx.auth_token,
            username=ctx.user_name
        )

    @classmethod
    def _get_fake_client(cls):
        return cls._get_client_class()("")


class HeatAction(base.OpenStackAction):

    @classmethod
    def _get_client_class(cls):
        return heatclient.Client

    def _create_client(self):
        ctx = context.ctx()

        LOG.debug("Heat action security context: %s" % ctx)

        heat_endpoint = keystone_utils.get_endpoint_for_project('heat')

        endpoint_url = keystone_utils.format_url(
            heat_endpoint.url,
            {
                'tenant_id': ctx.project_id,
                'project_id': ctx.project_id
            }
        )

        return self._get_client_class()(
            endpoint_url,
            region_name=heat_endpoint.region,
            token=ctx.auth_token,
            username=ctx.user_name
        )

    @classmethod
    def _get_fake_client(cls):
        return cls._get_client_class()("")


class NeutronAction(base.OpenStackAction):

    @classmethod
    def _get_client_class(cls):
        return neutronclient.Client

    def _create_client(self):
        ctx = context.ctx()

        LOG.debug("Neutron action security context: %s" % ctx)

        neutron_endpoint = keystone_utils.get_endpoint_for_project('neutron')

        return self._get_client_class()(
            endpoint_url=neutron_endpoint.url,
            region_name=neutron_endpoint.region,
            token=ctx.auth_token,
            auth_url=ctx.auth_uri
        )


class CinderAction(base.OpenStackAction):

    @classmethod
    def _get_client_class(cls):
        return cinderclient.Client

    def _create_client(self):
        ctx = context.ctx()

        LOG.debug("Cinder action security context: %s" % ctx)

        cinder_endpoint = keystone_utils.get_endpoint_for_project(
            service_type='volumev2'
        )

        cinder_url = keystone_utils.format_url(
            cinder_endpoint.url,
            {
                'tenant_id': ctx.project_id,
                'project_id': ctx.project_id
            }
        )

        client = self._get_client_class()(
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
        return cls._get_client_class()()


class MistralAction(base.OpenStackAction):

    @classmethod
    def _get_client_class(cls):
        return mistralclient.Client

    def _create_client(self):
        ctx = context.ctx()

        LOG.debug("Mistral action security context: %s" % ctx)

        # Check for trust scope token. This may occur if the action is
        # called from a workflow triggered by a Mistral cron trigger.
        if ctx.is_trust_scoped:
            auth_url = None
            mistral_endpoint = keystone_utils.get_endpoint_for_project(
                'mistral'
            )
            mistral_url = mistral_endpoint.url
        else:
            keystone_endpoint = keystone_utils.get_keystone_endpoint_v2()
            auth_url = keystone_endpoint.url
            mistral_url = None

        return self._get_client_class()(
            mistral_url=mistral_url,
            auth_token=ctx.auth_token,
            project_id=ctx.project_id,
            user_id=ctx.user_id,
            auth_url=auth_url
        )

    @classmethod
    def _get_fake_client(cls):
        return cls._get_client_class()()


class TroveAction(base.OpenStackAction):

    @classmethod
    def _get_client_class(cls):
        return troveclient.Client

    def _create_client(self):
        ctx = context.ctx()

        LOG.debug("Trove action security context: %s" % ctx)

        trove_endpoint = keystone_utils.get_endpoint_for_project(
            service_type='database'
        )

        trove_url = keystone_utils.format_url(
            trove_endpoint.url,
            {'tenant_id': ctx.project_id}
        )

        client = self._get_client_class()(
            ctx.user_name,
            ctx.auth_token,
            project_id=ctx.project_id,
            auth_url=trove_url,
            region_name=trove_endpoint.region
        )

        client.client.auth_token = ctx.auth_token
        client.client.management_url = trove_url

        return client

    @classmethod
    def _get_fake_client(cls):
        return cls._get_client_class()("fake_user", "fake_passwd")


class IronicAction(base.OpenStackAction):

    @classmethod
    def _get_client_class(cls):
        return ironicclient.Client

    def _create_client(self):
        ctx = context.ctx()

        LOG.debug("Ironic action security context: %s" % ctx)

        ironic_endpoint = keystone_utils.get_endpoint_for_project('ironic')

        return self._get_client_class()(
            ironic_endpoint.url,
            token=ctx.auth_token,
            region_name=ironic_endpoint.region
        )

    @classmethod
    def _get_fake_client(cls):
        return cls._get_client_class()("http://127.0.0.1:6385/")


class BaremetalIntrospectionAction(base.OpenStackAction):

    @classmethod
    def _get_client_class(cls):
        return ironic_inspector_client.ClientV1

    @classmethod
    def _get_fake_client(cls):
        try:
            # ironic-inspector client tries to get and validate it's own
            # version when created. This might require checking the keystone
            # catalog if the ironic-inspector server is not listening on the
            # localhost IP address. Thus, we get a session for this case.
            sess = keystone_utils.get_admin_session()

            return cls._get_client_class()(session=sess)
        except Exception as e:
            LOG.warning("There was an error trying to create the "
                        "ironic-inspector client using a session: %s" % str(e))
            # If it's not possible to establish a keystone session, attempt to
            # create a client without it. This should fall back to where the
            # ironic-inspector client tries to get it's own version on the
            # default IP address.
            LOG.debug("Attempting to create the ironic-inspector client "
                      "without a session.")

            return cls._get_client_class()()

    def _create_client(self):
        ctx = context.ctx()

        LOG.debug("Baremetal introspection action security context: %s" % ctx)

        inspector_endpoint = keystone_utils.get_endpoint_for_project(
            service_type='baremetal-introspection'
        )

        return self._get_client_class()(
            api_version=1,
            inspector_url=inspector_endpoint.url,
            auth_token=ctx.auth_token,
        )


class SwiftAction(base.OpenStackAction):

    @classmethod
    def _get_client_class(cls):
        return swift_client.Connection

    def _create_client(self):
        ctx = context.ctx()

        LOG.debug("Swift action security context: %s" % ctx)

        swift_endpoint = keystone_utils.get_endpoint_for_project('swift')

        kwargs = {
            'preauthurl': swift_endpoint.url % {'tenant_id': ctx.project_id},
            'preauthtoken': ctx.auth_token
        }

        return self._get_client_class()(**kwargs)


class ZaqarAction(base.OpenStackAction):

    @classmethod
    def _get_client_class(cls):
        return zaqarclient.Client

    def _create_client(self):
        ctx = context.ctx()

        LOG.debug("Zaqar action security context: %s" % ctx)

        zaqar_endpoint = keystone_utils.get_endpoint_for_project(
            service_type='messaging')
        keystone_endpoint = keystone_utils.get_keystone_endpoint_v2()

        opts = {
            'os_auth_token': ctx.auth_token,
            'os_auth_url': keystone_endpoint.url,
            'os_project_id': ctx.project_id,
        }
        auth_opts = {'backend': 'keystone', 'options': opts}
        conf = {'auth_opts': auth_opts}

        return self._get_client_class()(zaqar_endpoint.url, conf=conf)

    @classmethod
    def _get_fake_client(cls):
        return cls._get_client_class()("")

    @classmethod
    def _get_client_method(cls, client):
        method = getattr(cls, cls.client_method_name)

        # We can't use partial as it's not supported by getargspec
        @functools.wraps(method)
        def wrap(*args, **kwargs):
            return method(client, *args, **kwargs)

        args = inspect_utils.get_arg_list_as_str(method)
        # Remove client
        wrap.__arguments__ = args.split(', ', 1)[1]

        return wrap

    @staticmethod
    def queue_messages(client, queue_name, **params):
        """Gets a list of messages from the queue.

        :param queue_name: Name of the target queue.
        :type queue_name: `six.string_type`

        :param params: Filters to use for getting messages.
        :type params: **kwargs dict

        :returns: List of messages.
        :rtype: `list`
        """
        queue = client.queue(queue_name)

        return queue.messages(**params)

    @staticmethod
    def queue_post(client, queue_name, messages):
        """Posts one or more messages to a queue.

        :param queue_name: Name of the target queue.
        :type queue_name: `six.string_type`

        :param messages: One or more messages to post.
        :type messages: `list` or `dict`

        :returns: A dict with the result of this operation.
        :rtype: `dict`
        """
        queue = client.queue(queue_name)

        return queue.post(messages)

    @staticmethod
    def queue_pop(client, queue_name, count=1):
        """Pop `count` messages from the queue.

        :param queue_name: Name of the target queue.
        :type queue_name: `six.string_type`

        :param count: Number of messages to pop.
        :type count: int

        :returns: List of messages.
        :rtype: `list`
        """
        queue = client.queue(queue_name)

        return queue.pop(count)


class BarbicanAction(base.OpenStackAction):

    @classmethod
    def _get_client_class(cls):
        return barbicanclient.Client

    def _create_client(self):
        ctx = context.ctx()

        LOG.debug("Barbican action security context: %s" % ctx)

        barbican_endpoint = keystone_utils.get_endpoint_for_project('barbican')
        keystone_endpoint = keystone_utils.get_keystone_endpoint_v2()

        auth = identity.v2.Token(
            auth_url=keystone_endpoint.url,
            tenant_name=ctx.user_name,
            token=ctx.auth_token,
            tenant_id=ctx.project_id
        )

        return self._get_client_class()(
            project_id=ctx.project_id,
            endpoint=barbican_endpoint.url,
            auth=auth
        )

    @classmethod
    def _get_fake_client(cls):
        return cls._get_client_class()(
            project_id="1",
            endpoint="http://127.0.0.1:9311"
        )

    @classmethod
    def _get_client_method(cls, client):
        if cls.client_method_name != "secrets_store":
            return super(BarbicanAction, cls)._get_client_method(client)

        method = getattr(cls, cls.client_method_name)

        @functools.wraps(method)
        def wrap(*args, **kwargs):
            return method(client, *args, **kwargs)

        args = inspect_utils.get_arg_list_as_str(method)

        # Remove client.
        wrap.__arguments__ = args.split(', ', 1)[1]

        return wrap

    @staticmethod
    def secrets_store(client,
                      name=None,
                      payload=None,
                      algorithm=None,
                      bit_length=None,
                      secret_type=None,
                      mode=None, expiration=None):
        """Create and Store a secret in Barbican.

        :param name: A friendly name for the Secret
        :type name: string

        :param payload: The unencrypted secret data
        :type payload: string

        :param algorithm: The algorithm associated with this secret key
        :type algorithm: string

        :param bit_length: The bit length of this secret key
        :type bit_length: int

        :param secret_type: The secret type for this secret key
        :type secret_type: string

         :param mode: The algorithm mode used with this secret keybit_length:
        :type mode: string

        :param expiration: The expiration time of the secret in ISO 8601 format
        :type expiration: string

        :returns: A new Secret object
        :rtype: class:`barbicanclient.secrets.Secret'
        """

        entity = client.secrets.create(
            name,
            payload,
            algorithm,
            bit_length,
            secret_type,
            mode,
            expiration
        )

        entity.store()

        return entity._get_formatted_entity()


class DesignateAction(base.OpenStackAction):

    @classmethod
    def _get_client_class(cls):
        return designateclient.Client

    def _create_client(self):
        ctx = context.ctx()

        LOG.debug("Designate action security context: %s" % ctx)

        designate_endpoint = keystone_utils.get_endpoint_for_project(
            service_type='dns'
        )

        designate_url = keystone_utils.format_url(
            designate_endpoint.url,
            {'tenant_id': ctx.project_id}
        )

        client = self._get_client_class()(
            endpoint=designate_url,
            tenant_id=ctx.project_id,
            auth_url=ctx.auth_uri,
            region_name=designate_endpoint.region,
            service_type='dns'
        )

        client.client.auth_token = ctx.auth_token
        client.client.management_url = designate_url

        return client

    @classmethod
    def _get_fake_client(cls):
        return cls._get_client_class()()


class MagnumAction(base.OpenStackAction):

    @classmethod
    def _get_client_class(cls):
        return magnumclient.Client

    def _create_client(self):
        ctx = context.ctx()

        LOG.debug("Magnum action security context: %s" % ctx)

        keystone_endpoint = keystone_utils.get_keystone_endpoint_v2()
        auth_url = keystone_endpoint.url
        magnum_url = keystone_utils.get_endpoint_for_project('magnum').url

        return self._get_client_class()(
            magnum_url=magnum_url,
            auth_token=ctx.auth_token,
            project_id=ctx.project_id,
            user_id=ctx.user_id,
            auth_url=auth_url
        )

    @classmethod
    def _get_fake_client(cls):
        return cls._get_client_class()(auth_url='X', magnum_url='X')


class MuranoAction(base.OpenStackAction):

    @classmethod
    def _get_client_class(cls):
        return muranoclient.Client

    def _create_client(self):
        ctx = context.ctx()

        LOG.debug("Murano action security context: %s" % ctx)

        keystone_endpoint = keystone_utils.get_keystone_endpoint_v2()
        murano_endpoint = keystone_utils.get_endpoint_for_project('murano')

        return self._get_client_class()(
            endpoint=murano_endpoint.url,
            token=ctx.auth_token,
            tenant=ctx.project_id,
            region_name=murano_endpoint.region,
            auth_url=keystone_endpoint.url
        )

    @classmethod
    def _get_fake_client(cls):
        return cls._get_client_class()("http://127.0.0.1:8082/")


class TackerAction(base.OpenStackAction):

    @classmethod
    def _get_client_class(cls):
        return tackerclient.Client

    def _create_client(self):
        ctx = context.ctx()

        LOG.debug("Tacker action security context: %s" % ctx)

        keystone_endpoint = keystone_utils.get_keystone_endpoint_v2()
        tacker_endpoint = keystone_utils.get_endpoint_for_project('tacker')

        return self._get_client_class()(
            endpoint_url=tacker_endpoint.url,
            token=ctx.auth_token,
            tenant_id=ctx.project_id,
            region_name=tacker_endpoint.region,
            auth_url=keystone_endpoint.url
        )

    @classmethod
    def _get_fake_client(cls):
        return cls._get_client_class()()
