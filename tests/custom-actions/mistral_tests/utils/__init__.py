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

import datetime
import functools
import json
import logging
import os
import socket
import threading

from oslo_utils import timeutils
from oslo_utils import uuidutils

# Thread local storage.
_th_loc_storage = threading.local()
ACTION_TASK_TYPE = 'ACTION'
WORKFLOW_TASK_TYPE = 'WORKFLOW'


def generate_unicode_uuid():
    return uuidutils.generate_uuid()


def is_valid_uuid(uuid_string):
    return uuidutils.is_uuid_like(uuid_string)


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
        new_len = len(res) + len(k)

        is_str = isinstance(key, str)

        if is_str:
            new_len += 2

        if new_len >= length:
            res += "'%s..." % k[:length - new_len] if is_str else "%s..." % k

            break
        else:
            res += "'%s'" % k if is_str else k
            res += ": "

        # Processing value.
        new_len = len(res) + len(v)

        is_str = isinstance(value, str)

        if is_str:
            new_len += 2

        if new_len >= length:
            res += "'%s..." % v[:length - new_len] if is_str else "%s..." % v

            break
        else:
            res += "'%s'" % v if is_str else v
            res += ', ' if idx < len(d) - 1 else '}'

        if len(res) >= length:
            res += '...'

            break

        idx += 1

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

        if new_len >= length:
            res += "'%s..." % s[:length - new_len] if is_str else "%s..." % s

            break
        else:
            res += "'%s'" % s if is_str else s
            res += ', ' if idx < len(l) - 1 else ']'

    return res


def cut_string(s, length=100):
    if len(s) > length:
        return "%s..." % s[:length]

    return s


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


class NotDefined(object):
    """Marker of an empty value.

    In a number of cases None can't be used to express the semantics of
    a not defined value because None is just a normal value rather than
    a value set to denote that it's not defined. This class can be used
    in such cases instead of None.
    """

    pass


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


def utc_now_sec():
    """Returns current time and drops microseconds."""

    return timeutils.utcnow().replace(microsecond=0)


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
