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

import logging
import threading

from eventlet import corolocal

# Thread local storage.
_th_loc_storage = threading.local()


def _get_greenlet_local_storage():
    greenlet_id = corolocal.get_ident()

    greenlet_locals = getattr(_th_loc_storage, "greenlet_locals", None)

    if not greenlet_locals:
        greenlet_locals = {}
        _th_loc_storage.greenlet_locals = greenlet_locals

    if greenlet_id in greenlet_locals:
        return greenlet_locals[greenlet_id]
    else:
        return None


def has_thread_local(var_name):
    gl_storage = _get_greenlet_local_storage()
    return gl_storage and var_name in gl_storage


def get_thread_local(var_name):
    if not has_thread_local(var_name):
        return None

    return _get_greenlet_local_storage()[var_name]


def set_thread_local(var_name, val):
    if not val and has_thread_local(var_name):
        gl_storage = _get_greenlet_local_storage()

        # Delete variable from greenlet local storage.
        if gl_storage:
            del gl_storage[var_name]

        # Delete the entire greenlet local storage from thread local storage.
        if gl_storage and len(gl_storage) == 0:
            del _th_loc_storage.greenlet_locals[corolocal.get_ident()]

    if val:
        gl_storage = _get_greenlet_local_storage()
        if not gl_storage:
            gl_storage =\
                _th_loc_storage.greenlet_locals[corolocal.get_ident()] = {}

        gl_storage[var_name] = val


def log_exec(logger, level=logging.INFO):
    """Decorator for logging function execution.
        By default, target function execution is logged with INFO level.
    """

    def _decorator(func):
        def _logged(*args, **kw):
            params_repr = "[args=%s, kw=%s]" % (str(args), str(kw)) \
                if len(args) > 0 or len(kw) > 0 else ""

            func_repr = "Called method [name=%s, doc='%s', params=%s]" % \
                        (func.__name__, func.__doc__, params_repr)

            logger.log(level, func_repr)

            return func(*args, **kw)

        _logged.__doc__ = func.__doc__

        return _logged

    return _decorator
