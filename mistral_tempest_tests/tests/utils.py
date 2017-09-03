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
import json
import os
import shutil
import tempfile

from oslo_concurrency import processutils


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
            raise OSError(
                "Failed to delete temp dir %(dir)s (reason: %(reason)s)" %
                {'dir': tmpdir, 'reason': e}
            )


def save_text_to(text, file_path, overwrite=False):
    if os.path.exists(file_path) and not overwrite:
        raise OSError(
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
            # raise exc.DataAccessException(
            #     "Private key file hasn't been created"
            # )
            raise OSError("Private key file hasn't been created")

        private_key = open(keyfile).read()
        public_key_path = keyfile + '.pub'

        if not os.path.exists(public_key_path):
            # raise exc.DataAccessException(
            #     "Public key file hasn't been created"
            # )
            raise OSError("Private key file hasn't been created")
        public_key = open(public_key_path).read()

        return private_key, public_key
