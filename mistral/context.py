# -*- coding: utf-8 -*-
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

from pecan.hooks import PecanHook

import eventlet

from mistral.openstack.common import log as logging
from mistral import utils
from mistral import exceptions as exc

LOG = logging.getLogger(__name__)

#TODO(rakhmerov): refactor all threadlocal things with mistral.utils

_CTX_THREAD_LOCAL_NAME = "MISTRAL_APP_CTX_THREAD_LOCAL"


class BaseContext(object):
    """Container for context variables"""

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
    _elements = set([
        "user_id",
        "project_id",
        "auth_token",
        "service_catalog",
        "user_name",
        "project_name",
        "roles",
        "is_admin",
    ])


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
        LOG.exception("Thread '%s' fails with exception: '%s'"
                      % (thread_desc, e))
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
        roles=headers.get('X-Roles', "").split(",")
    )


class ContextHook(PecanHook):
    def before(self, state):
        request_ctx = context_from_headers(state.request.headers).to_dict()
        set_ctx(request_ctx)

    def after(self, state):
        set_ctx(None)
