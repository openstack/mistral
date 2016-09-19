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

from keystoneclient.v3 import client as keystone_client
import logging
from oslo_config import cfg
import oslo_messaging as messaging
from oslo_serialization import jsonutils
from osprofiler import profiler
import pecan
from pecan import hooks
import pprint
import requests

from mistral import exceptions as exc
from mistral import utils


LOG = logging.getLogger(__name__)


CONF = cfg.CONF

_CTX_THREAD_LOCAL_NAME = "MISTRAL_APP_CTX_THREAD_LOCAL"
ALLOWED_WITHOUT_AUTH = ['/', '/v2/']


class BaseContext(object):
    """Container for context variables."""

    _elements = set()

    def __init__(self, __mapping=None, **kwargs):
        if __mapping is None:
            self.__values = dict(**kwargs)
        else:
            if isinstance(__mapping, BaseContext):
                __mapping = __mapping.__values
            self.__values = dict(__mapping)
            self.__values.update(**kwargs)

        bad_keys = set(self.__values) - self._elements

        if bad_keys:
            raise TypeError("Only %s keys are supported. %s given" %
                            (tuple(self._elements), tuple(bad_keys)))

    def __getattr__(self, name):
        try:
            return self.__values[name]
        except KeyError:
            if name in self._elements:
                return None
            else:
                raise AttributeError(name)

    def to_dict(self):
        return self.__values


class MistralContext(BaseContext):
    # Use set([...]) since set literals are not supported in Python 2.6.
    _elements = set([
        "auth_uri",
        "auth_cacert",
        "user_id",
        "project_id",
        "auth_token",
        "service_catalog",
        "user_name",
        "project_name",
        "roles",
        "is_admin",
        "is_trust_scoped",
        "redelivered",
        "expires_at",
        "trust_id",
    ])

    def __repr__(self):
        return "MistralContext %s" % self.to_dict()


def has_ctx():
    return utils.has_thread_local(_CTX_THREAD_LOCAL_NAME)


def ctx():
    if not has_ctx():
        raise exc.ApplicationContextNotFoundException()

    return utils.get_thread_local(_CTX_THREAD_LOCAL_NAME)


def set_ctx(new_ctx):
    utils.set_thread_local(_CTX_THREAD_LOCAL_NAME, new_ctx)


def context_from_headers_and_env(headers, env):
    params = _extract_auth_params_from_headers(headers)
    auth_cacert = params['auth_cacert']
    auth_token = params['auth_token']
    auth_uri = params['auth_uri']
    project_id = params['project_id']
    user_id = params['user_id']
    user_name = params['user_name']

    token_info = env.get('keystone.token_info')

    return MistralContext(
        auth_uri=auth_uri,
        auth_cacert=auth_cacert,
        user_id=user_id,
        project_id=project_id,
        auth_token=auth_token,
        service_catalog=headers.get('X-Service-Catalog'),
        user_name=user_name,
        project_name=headers.get('X-Project-Name'),
        roles=headers.get('X-Roles', "").split(","),
        is_trust_scoped=False,
        expires_at=token_info['token']['expires_at'] if token_info else None,
    )


def _extract_auth_params_from_headers(headers):
    if headers.get("X-Target-Auth-Uri"):
        params = {
            # TODO(akovi): Target cert not handled yet
            'auth_cacert': None,
            'auth_token': headers.get('X-Target-Auth-Token'),
            'auth_uri': headers.get('X-Target-Auth-Uri'),
            'project_id': headers.get('X-Target-Project-Id'),
            'user_id': headers.get('X-Target-User-Id'),
            'user_name': headers.get('X-Target-User-Name'),
        }
        if not params['auth_token']:
            raise (exc.MistralException(
                'Target auth URI (X-Target-Auth-Uri) target auth token '
                '(X-Target-Auth-Token) must be present'))
    else:
        params = {
            'auth_cacert': CONF.keystone_authtoken.cafile,
            'auth_token': headers.get('X-Auth-Token'),
            'auth_uri': CONF.keystone_authtoken.auth_uri,
            'project_id': headers.get('X-Project-Id'),
            'user_id': headers.get('X-User-Id'),
            'user_name': headers.get('X-User-Name'),
        }
    return params


def context_from_config():
    keystone = keystone_client.Client(
        username=CONF.keystone_authtoken.admin_user,
        password=CONF.keystone_authtoken.admin_password,
        tenant_name=CONF.keystone_authtoken.admin_tenant_name,
        auth_url=CONF.keystone_authtoken.auth_uri,
        is_trust_scoped=False,
    )

    keystone.authenticate()

    return MistralContext(
        user_id=keystone.user_id,
        project_id=keystone.project_id,
        auth_token=keystone.auth_token,
        project_name=CONF.keystone_authtoken.admin_tenant_name,
        user_name=CONF.keystone_authtoken.admin_user,
        is_trust_scoped=False,
    )


class JsonPayloadSerializer(messaging.NoOpSerializer):
    @staticmethod
    def serialize_entity(context, entity):
        return jsonutils.to_primitive(entity, convert_instances=True)


class RpcContextSerializer(messaging.Serializer):
    def __init__(self, base=None):
        self._base = base or messaging.NoOpSerializer()

    def serialize_entity(self, context, entity):
        if not self._base:
            return entity

        return self._base.serialize_entity(context, entity)

    def deserialize_entity(self, context, entity):
        if not self._base:
            return entity

        return self._base.deserialize_entity(context, entity)

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

        ctx = MistralContext(**context)
        set_ctx(ctx)

        return ctx


class AuthHook(hooks.PecanHook):
    def before(self, state):
        if state.request.path in ALLOWED_WITHOUT_AUTH:
            return

        if not CONF.pecan.auth_enable:
            return

        try:
            if CONF.auth_type == 'keystone':
                authenticate_with_keystone(state.request)
            elif CONF.auth_type == 'keycloak-oidc':
                authenticate_with_keycloak(state.request)
        except Exception as e:
            msg = "Failed to validate access token: %s" % str(e)

            pecan.abort(
                status_code=401,
                detail=msg,
                headers={'Server-Error-Message': msg}
            )


def authenticate_with_keystone(req):
    # Note(nmakhotkin): Since we have deferred authentication,
    # need to check for auth manually (check for corresponding
    # headers according to keystonemiddleware docs.
    identity_status = req.headers.get('X-Identity-Status')
    service_identity_status = req.headers.get('X-Service-Identity-Status')

    if (identity_status == 'Confirmed' or
            service_identity_status == 'Confirmed'):
        return

    if req.headers.get('X-Auth-Token'):
        msg = 'Auth token is invalid: %s' % req.headers['X-Auth-Token']
    else:
        msg = 'Authentication required'

    raise exc.UnauthorizedException(msg)


def authenticate_with_keycloak(req):
    realm_name = req.headers.get('X-Project-Id')

    # NOTE(rakhmerov): There's a special endpoint for introspecting
    # access tokens described in OpenID Connect specification but it's
    # available in KeyCloak starting only with version 1.8.Final so we have
    # to use user info endpoint which also takes exactly one parameter
    # (access token) and replies with error if token is invalid.
    user_info_endpoint = (
        "%s/realms/%s/protocol/openid-connect/userinfo" %
        (CONF.keycloak_oidc.auth_url, realm_name)
    )

    access_token = req.headers.get('X-Auth-Token')

    resp = requests.get(
        user_info_endpoint,
        headers={"Authorization": "Bearer %s" % access_token},
        verify=not CONF.keycloak_oidc.insecure
    )

    resp.raise_for_status()

    LOG.debug(
        "HTTP response from OIDC provider: %s" %
        pprint.pformat(resp.json())
    )


class ContextHook(hooks.PecanHook):
    def before(self, state):
        set_ctx(context_from_headers_and_env(
            state.request.headers,
            state.request.environ
        ))

    def after(self, state):
        set_ctx(None)
