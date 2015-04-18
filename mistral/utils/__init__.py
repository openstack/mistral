# -*- coding: utf-8 -*-
#
# Copyright 2013 - Mirantis, Inc.
# Copyright 2015 - Huawei Technologies Co. Ltd
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
import os
from os import path
import threading
import uuid

import eventlet
from eventlet import corolocal
import pkg_resources as pkg
import random


from mistral import version


# Thread local storage.
_th_loc_storage = threading.local()


def generate_unicode_uuid():
    return unicode(str(uuid.uuid4()))


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
            gl_storage = _th_loc_storage.greenlet_locals[
                corolocal.get_ident()] = {}

        gl_storage[var_name] = val


def log_exec(logger, level=logging.DEBUG):
    """Decorator for logging function execution.
        By default, target function execution is logged with DEBUG level.
    """

    def _decorator(func):
        def _logged(*args, **kw):
            params_repr = ("[args=%s, kw=%s]" % (str(args), str(kw))
                           if len(args) > 0 or len(kw) > 0 else "")

            func_repr = ("Called method [name=%s, doc='%s', params=%s]" %
                         (func.__name__, func.__doc__, params_repr))

            logger.log(level, func_repr)

            return func(*args, **kw)

        _logged.__doc__ = func.__doc__

        return _logged

    return _decorator


def merge_dicts(left, right, overwrite=True):
    """Merges two dictionaries.

    Values of right dictionary recursively get merged into left dictionary.
    :param left: Left dictionary.
    :param right: Right dictionary.
    :param overwrite: If False, left value will not be overwritten if exists.
    """

    if left is None:
        return right

    if right is None:
        return left

    for k, v in right.iteritems():
        if k not in left:
            left[k] = v
        else:
            left_v = left[k]

            if isinstance(left_v, dict) and isinstance(v, dict):
                merge_dicts(left_v, v, overwrite=overwrite)
            elif overwrite:
                left[k] = v

    return left


def get_file_list(directory):
    base_path = pkg.resource_filename(
        version.version_info.package,
        directory
    )

    return [path.join(base_path, f) for f in os.listdir(base_path)
            if path.isfile(path.join(base_path, f))]


def cut(data, length=100):
    if not data:
        return data

    string = str(data)

    if len(string) > length:
        return "%s..." % string[:length]
    else:
        return string


def iter_subclasses(cls, _seen=None):
    """Generator over all subclasses of a given class in depth first order."""

    if not isinstance(cls, type):
        raise TypeError('iter_subclasses must be called with new-style class'
                        ', not %.100r' % cls)
    _seen = _seen or set()

    try:
        subs = cls.__subclasses__()
    except TypeError:   # fails only when cls is type
        subs = cls.__subclasses__(cls)

    for sub in subs:
        if sub not in _seen:
            _seen.add(sub)
            yield sub
            for _sub in iter_subclasses(sub, _seen):
                yield _sub


def random_sleep(limit=1):
    """Sleeps for a random period of time not exceeding the given limit.

    Mostly intended to be used by tests to emulate race conditions.

    :param limit: Float number of seconds that a sleep period must not exceed.
    """

    seconds = random.Random().randint(0, limit * 1000) * 0.001

    print("Sleep: %s sec..." % seconds)

    eventlet.sleep(seconds)


class NotDefined(object):
    """This class is just a marker of input params without value."""

    pass


def get_input_dict(inputs):
    """Transform input list to dictionary.

    Ensure every input param has a default value(it will be a NotDefined
    object if it's not provided).
    """
    input_dict = {}
    for x in inputs:
        if isinstance(x, dict):
            input_dict.update(x)
        else:
            # NOTE(xylan): we put a NotDefined class here as the value of
            # param without value specified, to distinguish from the valid
            # values such as None, ''(empty string), etc.
            input_dict[x] = NotDefined

    return input_dict
