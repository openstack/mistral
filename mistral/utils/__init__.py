# Copyright 2013 - Mirantis, Inc.
# Copyright 2015 - Huawei Technologies Co. Ltd
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

import contextlib
import datetime
import functools
import json
import os
from os import path
import shutil
import socket
import string
import sys
import tempfile
import threading

import eventlet
from eventlet import corolocal
from oslo_concurrency import processutils
from oslo_log import log as logging
from oslo_utils import timeutils
from oslo_utils import uuidutils
import pkg_resources as pkg
import random

from mistral import exceptions as exc


# Thread local storage.
_th_loc_storage = threading.local()

# TODO(rakhmerov): these two constants are misplaced. Utility methods
# should not be Mistral specific. They should be generic enough so to
# be moved to any other project w/o changes.
ACTION_TASK_TYPE = 'ACTION'
WORKFLOW_TASK_TYPE = 'WORKFLOW'


def generate_unicode_uuid():
    return uuidutils.generate_uuid()


def is_valid_uuid(uuid_string):
    return uuidutils.is_uuid_like(uuid_string)


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
    if val is None and has_thread_local(var_name):
        gl_storage = _get_greenlet_local_storage()

        # Delete variable from greenlet local storage.
        if gl_storage:
            del gl_storage[var_name]

        # Delete the entire greenlet local storage from thread local storage.
        if gl_storage and len(gl_storage) == 0:
            del _th_loc_storage.greenlet_locals[corolocal.get_ident()]

    if val is not None:
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
        @functools.wraps(func)
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

    for k, v in right.items():
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
    base_path = pkg.resource_filename("mistral", directory)

    return [path.join(base_path, f) for f in os.listdir(base_path)
            if path.isfile(path.join(base_path, f))]


def cut_dict(d, length=100):
    """Removes dictionary entries according to the given length.

    This method removes a number of entries, if needed, so that a
    string representation would fit into the given length.
    The intention of this method is to optimize truncation of string
    representation for dictionaries where the exact precision is not
    critically important. Otherwise, we'd always have to convert a dict
    into a string first and then shrink it to a needed size which will
    increase memory footprint and reduce performance in case of large
    dictionaries (i.e. tens of thousands entries).
    Note that the method, due to complexity of the algorithm, has some
    non-zero precision which depends on exact keys and values placed into
    the dict. So for some dicts their reduced string representations will
    be only approximately equal to the given value (up to around several
    chars difference).

    :param d: A dictionary.
    :param length: A length limiting the dictionary string representation.
    :return: A dictionary which is a subset of the given dictionary.
    """

    if not isinstance(d, dict):
        raise ValueError("A dictionary is expected, got: %s" % type(d))

    res = "{"

    idx = 0

    for key, value in d.items():
        k = str(key)
        v = str(value)

        # Processing key.
        new_len = len(k)

        is_str = isinstance(key, str)

        if is_str:
            new_len += 2    # Account for the quotation marks

        if 0 <= length <= new_len + len(res):
            res += "'%s" % k if is_str else k
            break
        else:
            res += "'%s'" % k if is_str else k

        res += ": "

        # Processing value.
        new_len = len(v)

        is_str = isinstance(value, str)

        if is_str:
            new_len += 2

        if 0 <= length <= new_len + len(res):
            res += "'%s" % v if is_str else v
            break
        else:
            res += "'%s'" % v if is_str else v

        res += ', ' if idx < len(d) - 1 else '}'

        idx += 1

    if 0 <= length <= len(res) and res[length - 1] is not '}':
        res = res[:length - 3] + '...'

    return res


def cut_list(l, length=100):
    if not isinstance(l, list):
        raise ValueError("A list is expected, got: %s" % type(l))

    res = '['

    for idx, item in enumerate(l):
        s = str(item)

        new_len = len(res) + len(s)

        is_str = isinstance(item, str)

        if is_str:
            new_len += 2

        if 0 <= length <= new_len:
            res += "'%s" % s if is_str else s
            break
        else:
            res += "'%s'" % s if is_str else s
        res += ', ' if idx < len(l) - 1 else ']'

    if 0 <= length <= len(res) and res[length - 1] is not ']':
        res = res[:length - 3] + '...'

    return res


def cut_string(s, length=100):
    if 0 <= length < len(s):
        return "%s..." % s[:length]

    return s


def cut(data, length=100):
    if not data:
        return data

    if isinstance(data, list):
        return cut_list(data, length=length)

    if isinstance(data, dict):
        return cut_dict(data, length=length)

    return cut_string(str(data), length=length)


def cut_by_kb(data, kilobytes):
    length = get_number_of_chars_from_kilobytes(kilobytes)
    return cut(data, length)


def cut_by_char(data, length):
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
    """Marker of an empty value.

    In a number of cases None can't be used to express the semantics of
    a not defined value because None is just a normal value rather than
    a value set to denote that it's not defined. This class can be used
    in such cases instead of None.
    """

    pass


def get_number_of_chars_from_kilobytes(kilobytes):
    bytes_per_char = sys.getsizeof('s') - sys.getsizeof('')
    total_number_of_chars = int(kilobytes * 1024 / bytes_per_char)
    return total_number_of_chars


def get_dict_from_string(string, delimiter=','):
    if not string:
        return {}

    kv_dicts = []

    for kv_pair_str in string.split(delimiter):
        kv_str = kv_pair_str.strip()
        kv_list = kv_str.split('=')

        if len(kv_list) > 1:
            try:
                value = json.loads(kv_list[1])
            except ValueError:
                value = kv_list[1]

            kv_dicts += [{kv_list[0]: value}]
        else:
            kv_dicts += [kv_list[0]]

    return get_dict_from_entries(kv_dicts)


def get_dict_from_entries(entries):
    """Transforms a list of entries into dictionary.

    :param entries: A list of entries.
        If an entry is a dictionary the method simply updates the result
        dictionary with its content.
        If an entry is not a dict adds {entry, NotDefined} into the result.
    """

    result = {}

    for e in entries:
        if isinstance(e, dict):
            result.update(e)
        else:
            # NOTE(kong): we put NotDefined here as the value of
            # param without value specified, to distinguish from
            # the valid values such as None, ''(empty string), etc.
            result[e] = NotDefined

    return result


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


def utc_now_sec():
    """Returns current time and drops microseconds."""

    return drop_microseconds(timeutils.utcnow())


def drop_microseconds(date):
    """Drops microseconds and returns date."""
    return date.replace(microsecond=0)


def datetime_to_str(val, sep=' '):
    """Converts datetime value to string.

    If the given value is not an instance of datetime then the method
    returns the same value.

    :param val: datetime value.
    :param sep: Separator between date and time.
    :return: Datetime as a string.
    """
    if isinstance(val, datetime.datetime):
        return val.isoformat(sep)

    return val


def datetime_to_str_in_dict(d, key, sep=' '):
    """Converts datetime value in te given dict to string.

    :param d: A dictionary.
    :param key: The key for which we need to convert the value.
    :param sep: Separator between date and time.
    """
    val = d.get(key)

    if val is not None:
        d[key] = datetime_to_str(d[key], sep=sep)


def generate_string(length):
    """Returns random string.

    :param length: the length of returned string
    """

    return ''.join(random.choice(
        string.ascii_uppercase + string.digits)
        for _ in range(length)
    )
