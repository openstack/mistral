# Copyright 2025 - NetCracker Technology Corp.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import base64
import re
import struct
import threading

import cachetools
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicNumbers
from cryptography.hazmat.primitives import serialization
import jwt
from oslo_config import cfg
from oslo_log import log as logging
import six

from mistral import auth
from mistral import exceptions as exc


LOG = logging.getLogger(__name__)

_PEM_CACHE = {}
_PEM_CACHE_LOCK = threading.RLock()

TOKEN_HEADER_KEY = 'Authorization'
AUTH_TOKEN_KEY = 'nc_token_key'
AUTH_HEADER_PATTERN = re.compile(r'^\w+\s(.*)$')


def extract_token_from_header(headers):
    header_with_token = headers.get(TOKEN_HEADER_KEY)

    if not header_with_token:
        token = headers.get('X-Auth-Token')

        if token:
            return token

        raise exc.UnauthorizedException(
            message='There is no token in headers(X-Auth-Token,Authorization)')

    header_pattern_match = AUTH_HEADER_PATTERN.match(header_with_token)
    if header_pattern_match is None:
        raise exc.UnauthorizedException('Does not match pattern ' +
                                        AUTH_HEADER_PATTERN.pattern)

    groups = header_pattern_match.groups()

    if len(groups) != 1:
        raise exc.UnauthorizedException(
            'Not found the token in the header. '
            'Authorization header: {}'.format(header_with_token)
        )

    return groups[0]


def intarr2long(arr):
    return int(''.join(["%02x" % byte for byte in arr]), 16)


def base64_to_long(data):
    if isinstance(data, six.text_type):
        data = data.encode("ascii")

    # urlsafe_b64decode will happily convert b64encoded data
    _d = base64.urlsafe_b64decode(bytes(data) + b'==')

    return intarr2long(struct.unpack('%sB' % len(_d), _d))


@cachetools.cached(_PEM_CACHE, lock=_PEM_CACHE_LOCK)
def get_pem():
    exponent = cfg.CONF.oauth2.jwk_exp
    modulus = cfg.CONF.oauth2.jwk_mod

    rsa_public_numbers = RSAPublicNumbers(
        base64_to_long(exponent),
        base64_to_long(modulus)
    )

    public_key = rsa_public_numbers.public_key(default_backend())

    return public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )


class MitreidAuthHandler(auth.AuthHandler):

    def __init__(self):
        super(MitreidAuthHandler, self).__init__()

    def authenticate(self, req):
        headers = req.headers
        token = extract_token_from_header(headers)
        pem = get_pem()
        token = jwt.decode(token, key=pem, algorithms='RS256')
        tenant = token.get("tenant-id")

        if not tenant:
            raise exc.MistralException("{} is not found in token")

        headers['X-Project-Id'] = tenant
        headers['X-Identity-Status'] = "Confirmed"

# WITHOUT LIMITING THE FOREGOING, COPYING, REPRODUCTION, REDISTRIBUTION,
# REVERSE ENGINEERING, DISASSEMBLY, DECOMPILATION OR MODIFICATION
# OF THE SOFTWARE IS EXPRESSLY PROHIBITED, UNLESS SUCH COPYING,
# REPRODUCTION, REDISTRIBUTION, REVERSE ENGINEERING, DISASSEMBLY,
# DECOMPILATION OR MODIFICATION IS EXPRESSLY PERMITTED BY THE LICENSE
# AGREEMENT WITH NETCRACKER.

# THIS SOFTWARE IS WARRANTED, IF AT ALL, ONLY AS EXPRESSLY PROVIDED IN
# THE TERMS OF THE LICENSE AGREEMENT, EXCEPT AS WARRANTED IN THE
# LICENSE AGREEMENT, NETCRACKER HEREBY DISCLAIMS ALL WARRANTIES AND
# CONDITIONS WITH REGARD TO THE SOFTWARE, WHETHER EXPRESS, IMPLIED
# OR STATUTORY, INCLUDING WITHOUT LIMITATION ALL WARRANTIES AND
# CONDITIONS OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE,
# TITLE AND NON - INFRINGEMENT.

# Copyright(c) 1995 - 2017 NetCracker Technology Corp.

# All Rights Reserved.
