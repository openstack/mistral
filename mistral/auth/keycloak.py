# Copyright 2016 - Brocade Communications Systems, Inc.
# Modified in 2025 by NetCracker Technology Corp.
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

import os

from cachetools import cached
from cachetools import LRUCache
import json
import jwt
from jwt import algorithms as jwt_algos
from oslo_config import cfg
from oslo_log import log as logging
import pprint
import re
import requests
import threading
from urllib import parse

from mistral._i18n import _
from mistral import auth
from mistral import exceptions as exc


LOG = logging.getLogger(__name__)

_PEM_CACHE = {}
_PEM_CACHE_LOCK = threading.RLock()

CONF = cfg.CONF
TOKEN_HEADER_KEY = 'Authorization'
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


class KeycloakAuthHandler(auth.AuthHandler):
    def authenticate(self, req):
        headers = req.headers
        access_token = extract_token_from_header(headers)
        try:
            decoded = jwt.decode(
                access_token,
                algorithms=['RS256'],
                options={"verify_signature": False}
            )
        except Exception as e:
            msg = _("Token can't be decoded because of wrong format %s")\
                % str(e)

            LOG.error(msg)

            raise exc.UnauthorizedException(message=msg)

        # Get user realm from parsed token
        # Format is "iss": "http://<host>:<port>/auth/realms/<realm_name>",
        __, __, realm_name = decoded['iss'].strip().rpartition('/realms/')
        audience = decoded.get('aud')

        # Get roles from parsed token
        roles = ','.join(decoded['realm_access']['roles']) \
            if 'realm_access' in decoded else ''

        public_key = self.get_public_key(realm_name)

        keycloak_iss = None

        if CONF.keycloak_oidc.keycloak_iss:
            keycloak_iss = CONF.keycloak_oidc.keycloak_iss % realm_name

        try:
            jwt.decode(
                access_token,
                public_key,
                audience=audience,
                issuer=keycloak_iss,
                algorithms=['RS256']
            )
        except Exception:
            LOG.exception('The request access token is invalid.')

            raise exc.UnauthorizedException()

        req.headers["X-Identity-Status"] = "Confirmed"
        req.headers["X-Project-Id"] = realm_name
        req.headers["X-Roles"] = roles

    @staticmethod
    def get_system_ca_file():
        """Return path to system default CA file."""
        # Standard CA file locations for Debian/Ubuntu, RedHat/Fedora,
        # Suse, FreeBSD/OpenBSD, MacOSX, and the bundled ca.
        ca_path = [
            '/etc/ssl/certs/ca-certificates.crt',
            '/etc/pki/tls/certs/ca-bundle.crt',
            '/etc/ssl/ca-bundle.pem',
            '/etc/ssl/cert.pem',
            '/System/Library/OpenSSL/certs/cacert.pem',
            requests.certs.where()
        ]

        for ca in ca_path:
            LOG.debug("Looking for ca file %s", ca)

            if os.path.exists(ca):
                LOG.debug("Using ca file %s", ca)

                return ca

        LOG.warning("System ca file could not be found.")

    @cached(LRUCache(maxsize=32))
    def get_public_key(self, realm_name):
        keycloak_key_url = (
            cfg.CONF.oauth2.idp_url + "/auth" +
            CONF.keycloak_oidc.public_cert_url % realm_name
        )

        response_json = self.send_request_to_auth_server(keycloak_key_url)

        keys = response_json.get('keys')

        if not keys:
            raise exc.MistralException(
                'Unexpected response structure from the keycloak server.'
            )

        public_key = jwt_algos.RSAAlgorithm.from_jwk(
            json.dumps(keys[0])
        )

        return public_key

    def send_request_to_auth_server(self, url, access_token=None):
        certfile = CONF.keycloak_oidc.certfile
        keyfile = CONF.keycloak_oidc.keyfile
        cafile = CONF.keycloak_oidc.cafile or self.get_system_ca_file()
        insecure = CONF.keycloak_oidc.insecure

        verify = None

        if parse.urlparse(url).scheme == "https":
            verify = False if insecure else cafile

        cert = (certfile, keyfile) if certfile and keyfile else None

        headers = {}

        if access_token:
            headers["Authorization"] = "Bearer %s" % access_token

        try:
            resp = requests.get(
                url,
                headers=headers,
                verify=verify,
                cert=cert
            )
        except requests.ConnectionError:
            msg = _(
                "Can't connect to the keycloak server with address '%s'."
            ) % url

            LOG.exception(msg)

            raise exc.MistralException(message=msg)

        if resp.status_code == 401:
            LOG.warning(
                "HTTP response from OIDC provider:"
                " [%s] with WWW-Authenticate: [%s]",
                pprint.pformat(resp.text),
                resp.headers.get("WWW-Authenticate")
            )
        else:
            LOG.debug(
                "HTTP response from the OIDC provider: %s",
                pprint.pformat(resp.json())
            )

        resp.raise_for_status()

        return resp.json()
