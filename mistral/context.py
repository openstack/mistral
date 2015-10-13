#
# Copyright 2013 - Mirantis, Inc.
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

import eventlet
from keystoneclient.v3 import client as keystone_client
from oslo_config import cfg
import oslo_messaging as messaging
from oslo_serialization import jsonutils
import pecan
from pecan import hooks

from mistral import exceptions as exc
from mistral import utils


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
        "user_id",
        "project_id",
        "auth_token",
        "service_catalog",
        "user_name",
        "project_name",
        "roles",
        "is_admin",
        "is_trust_scoped",
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


def _wrapper(context, thread_desc, thread_group, func, *args, **kwargs):
    try:
        set_ctx(context)
        func(*args, **kwargs)
    except Exception as e:
        if thread_group and not thread_group.exc:
            thread_group.exc = e
            thread_group.failed_thread = thread_desc
    finally:
        if thread_group:
            thread_group._on_thread_exit()

        set_ctx(None)


def spawn(thread_description, func, *args, **kwargs):
    eventlet.spawn(_wrapper, ctx().clone(), thread_description,
                   None, func, *args, **kwargs)


def context_from_headers(headers):
    return MistralContext(
        user_id=headers.get('X-User-Id'),
        project_id=headers.get('X-Project-Id'),
        auth_token=headers.get('X-Auth-Token'),
        service_catalog=headers.get('X-Service-Catalog'),
        user_name=headers.get('X-User-Name'),
        project_name=headers.get('X-Project-Name'),
        roles=headers.get('X-Roles', "").split(","),
        is_trust_scoped=False,
    )


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
        return context.to_dict()

    def deserialize_context(self, context):
        ctx = MistralContext(**context)
        set_ctx(ctx)

        return ctx


class AuthHook(hooks.PecanHook):
    def before(self, state):
        if state.request.path in ALLOWED_WITHOUT_AUTH:
            return

        if CONF.pecan.auth_enable:
            # Note(nmakhotkin): Since we have deferred authentication,
            # need to check for auth manually (check for corresponding
            # headers according to keystonemiddleware docs.
            identity_status = state.request.headers.get('X-Identity-Status')
            service_identity_status = state.request.headers.get(
                'X-Service-Identity-Status'
            )

            if (identity_status == 'Confirmed'
                    or service_identity_status == 'Confirmed'):
                return

            if state.request.headers.get('X-Auth-Token'):
                msg = ("Auth token is invalid: %s"
                       % state.request.headers['X-Auth-Token'])
            else:
                msg = 'Authentication required'

            pecan.abort(
                status_code=401,
                detail=msg,
                headers={'Server-Error-Message': msg}
            )


class ContextHook(hooks.PecanHook):
    def before(self, state):
        set_ctx(context_from_headers(state.request.headers))

    def after(self, state):
        set_ctx(None)
