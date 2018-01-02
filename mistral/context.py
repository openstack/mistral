# Copyright 2013 - Mirantis, Inc.
# Copyright 2016 - Brocade Communications Systems, Inc.
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

import base64

from mistral_lib.actions import context as lib_ctx
from oslo_config import cfg
from oslo_context import context as oslo_context
import oslo_messaging as messaging
from oslo_serialization import jsonutils
from osprofiler import profiler
import pecan
from pecan import hooks

from mistral import auth
from mistral import exceptions as exc
from mistral import serialization
from mistral import utils

CONF = cfg.CONF
_CTX_THREAD_LOCAL_NAME = "MISTRAL_APP_CTX_THREAD_LOCAL"
ALLOWED_WITHOUT_AUTH = ['/', '/v2/']


class MistralContext(oslo_context.RequestContext):
    def __init__(self, auth_uri=None, auth_cacert=None, insecure=False,
                 service_catalog=None, region_name=None, is_trust_scoped=False,
                 redelivered=False, expires_at=None, trust_id=None,
                 is_target=False, **kwargs):
        self.auth_uri = auth_uri
        self.auth_cacert = auth_cacert
        self.insecure = insecure
        self.service_catalog = service_catalog
        self.region_name = region_name
        self.is_trust_scoped = is_trust_scoped
        self.redelivered = redelivered
        self.expires_at = expires_at
        self.trust_id = trust_id
        self.is_target = is_target

        # We still use Mistral thread local variable. Maybe could consider
        # using the variable provided by oslo_context in future.
        super(MistralContext, self).__init__(overwrite=False, **kwargs)

    def to_dict(self):
        """Return a dictionary of context attributes."""
        ctx_dict = super(MistralContext, self).to_dict()
        ctx_dict.update(
            {
                'user_name': self.user_name,
                'project_name': self.project_name,
                'domain_name': self.domain_name,
                'user_domain_name': self.user_domain_name,
                'project_domain_name': self.project_domain_name,
                'auth_uri': self.auth_uri,
                'auth_cacert': self.auth_cacert,
                'insecure': self.insecure,
                'service_catalog': self.service_catalog,
                'region_name': self.region_name,
                'is_trust_scoped': self.is_trust_scoped,
                'redelivered': self.redelivered,
                'expires_at': self.expires_at,
                'trust_id': self.trust_id,
                'is_target': self.is_target,
            }
        )

        return ctx_dict

    @classmethod
    def from_dict(cls, values, **kwargs):
        """Construct a context object from a provided dictionary."""
        kwargs.setdefault('auth_uri', values.get('auth_uri'))
        kwargs.setdefault('auth_cacert', values.get('auth_cacert'))
        kwargs.setdefault('insecure', values.get('insecure', False))
        kwargs.setdefault('service_catalog', values.get('service_catalog'))
        kwargs.setdefault('region_name', values.get('region_name'))
        kwargs.setdefault(
            'is_trust_scoped', values.get('is_trust_scoped', False)
        )
        kwargs.setdefault('redelivered', values.get('redelivered', False))
        kwargs.setdefault('expires_at', values.get('expires_at'))
        kwargs.setdefault('trust_id', values.get('trust_id'))
        kwargs.setdefault('is_target', values.get('is_target', False))

        return super(MistralContext, cls).from_dict(values, **kwargs)

    @classmethod
    def from_environ(cls, headers, env):
        kwargs = _extract_mistral_auth_params(headers)

        token_info = env.get('keystone.token_info', {})
        if not kwargs['is_target']:
            kwargs['service_catalog'] = token_info.get('token', {})
        kwargs['expires_at'] = (token_info['token']['expires_at']
                                if token_info else None)

        context = super(MistralContext, cls).from_environ(env, **kwargs)
        context.is_admin = True if 'admin' in context.roles else False

        return context


def has_ctx():
    return utils.has_thread_local(_CTX_THREAD_LOCAL_NAME)


def ctx():
    if not has_ctx():
        raise exc.ApplicationContextNotFoundException()

    return utils.get_thread_local(_CTX_THREAD_LOCAL_NAME)


def set_ctx(new_ctx):
    utils.set_thread_local(_CTX_THREAD_LOCAL_NAME, new_ctx)


def _extract_mistral_auth_params(headers):
    service_catalog = None

    if headers.get("X-Target-Auth-Uri"):
        params = {
            # TODO(akovi): Target cert not handled yet
            'auth_cacert': None,
            'insecure': headers.get('X-Target-Insecure', False),
            'auth_token': headers.get('X-Target-Auth-Token'),
            'auth_uri': headers.get('X-Target-Auth-Uri'),
            'tenant': headers.get('X-Target-Project-Id'),
            'user': headers.get('X-Target-User-Id'),
            'user_name': headers.get('X-Target-User-Name'),
            'region_name': headers.get('X-Target-Region-Name'),
            'is_target': True
        }
        if not params['auth_token']:
            raise (exc.MistralException(
                'Target auth URI (X-Target-Auth-Uri) target auth token '
                '(X-Target-Auth-Token) must be present'))

        # It's possible that target service catalog is not provided, in this
        # case, Mistral needs to get target service catalog dynamically when
        # talking to target openstack deployment later on.
        service_catalog = _extract_service_catalog_from_headers(
            headers
        )
    else:
        params = {
            'auth_uri': CONF.keystone_authtoken.auth_uri,
            'auth_cacert': CONF.keystone_authtoken.cafile,
            'insecure': False,
            'region_name': headers.get('X-Region-Name'),
            'is_target': False
        }

    params['service_catalog'] = service_catalog

    return params


def _extract_service_catalog_from_headers(headers):
    target_service_catalog_header = headers.get(
        'X-Target-Service-Catalog')
    if target_service_catalog_header:
        decoded_catalog = base64.b64decode(
            target_service_catalog_header).decode()
        return jsonutils.loads(decoded_catalog)
    else:
        return None


class RpcContextSerializer(messaging.Serializer):
    def __init__(self, entity_serializer=None):
        self.entity_serializer = (
            entity_serializer or serialization.get_polymorphic_serializer()
        )

    def serialize_entity(self, context, entity):
        if not self.entity_serializer:
            return entity

        return self.entity_serializer.serialize(entity)

    def deserialize_entity(self, context, entity):
        if not self.entity_serializer:
            return entity

        return self.entity_serializer.deserialize(entity)

    def serialize_context(self, context):
        ctx = context.to_dict()

        pfr = profiler.get()

        if pfr:
            ctx['trace_info'] = {
                "hmac_key": pfr.hmac_key,
                "base_id": pfr.get_base_id(),
                "parent_id": pfr.get_id()
            }

        return ctx

    def deserialize_context(self, context):
        trace_info = context.pop('trace_info', None)

        if trace_info:
            profiler.init(**trace_info)

        ctx = MistralContext.from_dict(context)
        set_ctx(ctx)

        return ctx


class AuthHook(hooks.PecanHook):
    def before(self, state):
        if state.request.path in ALLOWED_WITHOUT_AUTH:
            return

        if not CONF.pecan.auth_enable:
            return

        try:
            auth_handler = auth.get_auth_handler()
            auth_handler.authenticate(state.request)
        except Exception as e:
            msg = "Failed to validate access token: %s" % str(e)

            pecan.abort(
                status_code=401,
                detail=msg,
                headers={'Server-Error-Message': msg}
            )


class ContextHook(hooks.PecanHook):
    def before(self, state):
        context = MistralContext.from_environ(
            state.request.headers, state.request.environ
        )

        set_ctx(context)

    def after(self, state):
        set_ctx(None)


def create_action_context(execution_ctx):

    context = ctx()

    security_ctx = lib_ctx.SecurityContext(
        auth_cacert=context.auth_cacert,
        auth_token=context.auth_token,
        auth_uri=context.auth_uri,
        expires_at=context.expires_at,
        insecure=context.insecure,
        is_target=context.is_target,
        is_trust_scoped=context.is_trust_scoped,
        project_id=context.project_id,
        project_name=context.project_name,
        user_name=context.user_name,
        redelivered=context.redelivered,
        region_name=context.region_name,
        service_catalog=context.service_catalog,
        trust_id=context.trust_id,
    )

    ex_ctx = lib_ctx.ExecutionContext(**execution_ctx)

    return lib_ctx.ActionContext(security_ctx, ex_ctx)
