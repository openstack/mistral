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
import inspect
import os
import shutil
import tempfile
import threading

from oslo_concurrency import processutils
from oslo_serialization import jsonutils

from mistral_lib.utils import inspect_utils

from mistral import exceptions as exc
from mistral import expressions as expr


# Thread local storage.
_th_loc_storage = threading.local()


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


def to_json_str(obj):
    """Serializes an object into a JSON string.

    :param obj: Object to serialize.
    :return: JSON string.
    """

    if obj is None:
        return None

    def _fallback(value):
        if inspect.isgenerator(value):
            result = list(value)

            # The result of the generator call may be again not primitive
            # so we need to call "to_primitive" again with the same fallback
            # function. Note that the endless recursion here is not a problem
            # because "to_primitive" limits the depth for custom classes,
            # if they are present in the object graph being traversed.
            return jsonutils.to_primitive(
                result,
                convert_instances=True,
                fallback=_fallback
            )

        return value

    # We need to convert the root of the given object graph into
    # a primitive by hand so that we also enable conversion of
    # object of custom classes into primitives. Otherwise, they are
    # ignored by the "json" lib.
    return jsonutils.dumps(
        jsonutils.to_primitive(obj, convert_instances=True, fallback=_fallback)
    )


def from_json_str(json_str):
    """Reconstructs an object from a JSON string.

    :param json_str: A JSON string.
    :return: Deserialized object.
    """

    if json_str is None:
        return None

    return jsonutils.loads(json_str)


def evaluate_object_fields(obj, ctx):
    """Evaluates all expressions recursively contained in the object fields.

    Some of the given object fields may be strings or data structures that
    contain YAQL/Jinja expressions. The method evaluates them and updates
    the corresponding object fields with the evaluated values.

    :param obj: The object to inspect.
    :param ctx: Expression context.
    """
    fields = inspect_utils.get_public_fields(obj)

    evaluated_fields = expr.evaluate_recursively(fields, ctx)

    for k, v in evaluated_fields.items():
        setattr(obj, k, v)
