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

import contextlib
import json
import logging
import os
from os import path
import shutil
import six
import socket
import sys
import tempfile
import threading
import uuid

import eventlet
from eventlet import corolocal
from oslo_concurrency import processutils
import pkg_resources as pkg
import random

from mistral import exceptions as exc
from mistral import version


# Thread local storage.
_th_loc_storage = threading.local()


def generate_unicode_uuid():
    return six.text_type(str(uuid.uuid4()))


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
                           if args or kw else "")

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

    for k, v in six.iteritems(right):
        if k not in left:
            left[k] = v
        else:
            left_v = left[k]

            if isinstance(left_v, dict) and isinstance(v, dict):
                merge_dicts(left_v, v, overwrite=overwrite)
            elif overwrite:
                left[k] = v

    return left


def update_dict(left, right):
    """Updates left dict with content from right dict

    :param left: Left dict.
    :param right: Right dict.
    :return: the updated left dictionary.
    """

    if left is None:
        return right

    if right is None:
        return left

    left.update(right)

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


def cut_by_kb(data, kilobytes):
    if kilobytes <= 0:
        return cut(data)

    bytes_per_char = sys.getsizeof('s') - sys.getsizeof('')
    length = int(kilobytes * 1024 / bytes_per_char)

    return cut(data, length)


def iter_subclasses(cls, _seen=None):
    """Generator over all subclasses of a given class in depth first order."""

    if not isinstance(cls, type):
        raise TypeError('iter_subclasses must be called with new-style class'
                        ', not %.100r' % cls)
    _seen = _seen or set()

    try:
        subs = cls.__subclasses__()
    except TypeError:  # fails only when cls is type
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


def get_dict_from_string(input_string, delimiter=','):
    if not input_string:
        return {}

    raw_inputs = input_string.split(delimiter)

    inputs = []

    for raw in raw_inputs:
        input = raw.strip()
        name_value = input.split('=')

        if len(name_value) > 1:

            try:
                value = json.loads(name_value[1])
            except ValueError:
                value = name_value[1]

            inputs += [{name_value[0]: value}]
        else:
            inputs += [name_value[0]]

    return get_input_dict(inputs)


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


def get_process_identifier():
    """Gets current running process identifier."""

    return "%s_%s" % (socket.gethostname(), os.getpid())


@contextlib.contextmanager
def tempdir(**kwargs):
    argdict = kwargs.copy()

    if 'dir' not in argdict:
        argdict['dir'] = '/tmp/'

    tmpdir = tempfile.mkdtemp(**argdict)

    try:
        yield tmpdir
    finally:
        try:
            shutil.rmtree(tmpdir)
        except OSError as e:
            raise exc.DataAccessException(
                "Failed to delete temp dir %(dir)s (reason: %(reason)s)" %
                {'dir': tmpdir, 'reason': e}
            )


def save_text_to(text, file_path, overwrite=False):
    if os.path.exists(file_path) and not overwrite:
        raise exc.DataAccessException(
            "Cannot save data to file. File %s already exists."
        )

    with open(file_path, 'w') as f:
        f.write(text)


def generate_key_pair(key_length=2048):
    """Create RSA key pair with specified number of bits in key.

    Returns tuple of private and public keys.
    """
    with tempdir() as tmpdir:
        keyfile = os.path.join(tmpdir, 'tempkey')
        args = [
            'ssh-keygen',
            '-q',  # quiet
            '-N', '',  # w/o passphrase
            '-t', 'rsa',  # create key of rsa type
            '-f', keyfile,  # filename of the key file
            '-C', 'Generated-by-Mistral'  # key comment
        ]

        if key_length is not None:
            args.extend(['-b', key_length])

        processutils.execute(*args)

        if not os.path.exists(keyfile):
            raise exc.DataAccessException(
                "Private key file hasn't been created"
            )

        private_key = open(keyfile).read()
        public_key_path = keyfile + '.pub'

        if not os.path.exists(public_key_path):
            raise exc.DataAccessException(
                "Public key file hasn't been created"
            )
        public_key = open(public_key_path).read()

        return private_key, public_key
