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

import os

import jwt
from oslo_config import cfg
from oslo_log import log as logging
import pprint
import requests
from six.moves import urllib

from mistral._i18n import _
from mistral import auth
from mistral import exceptions as exc


LOG = logging.getLogger(__name__)

CONF = cfg.CONF


class KeycloakAuthHandler(auth.AuthHandler):

    def authenticate(self, req):
        certfile = CONF.keycloak_oidc.certfile
        keyfile = CONF.keycloak_oidc.keyfile
        cafile = CONF.keycloak_oidc.cafile or self.get_system_ca_file()
        insecure = CONF.keycloak_oidc.insecure

        if 'X-Auth-Token' not in req.headers:
            msg = _("Auth token must be provided in 'X-Auth-Token' header.")
            LOG.error(msg)
            raise exc.UnauthorizedException(message=msg)
        access_token = req.headers.get('X-Auth-Token')

        try:
            decoded = jwt.decode(access_token, algorithms=['RS256'],
                                 verify=False)
        except Exception:
            msg = _("Token can't be decoded because of wrong format.")
            LOG.error(msg)
            raise exc.UnauthorizedException(message=msg)

        # Get user realm from parsed token
        # Format is "iss": "http://<host>:<port>/auth/realms/<realm_name>",
        __, __, realm_name = decoded['iss'].strip().rpartition('/realms/')

        # Get roles from from parsed token
        roles = ','.join(decoded['realm_access']['roles']) \
            if 'realm_access' in decoded else ''

        # NOTE(rakhmerov): There's a special endpoint for introspecting
        # access tokens described in OpenID Connect specification but it's
        # available in KeyCloak starting only with version 1.8.Final so we have
        # to use user info endpoint which also takes exactly one parameter
        # (access token) and replies with error if token is invalid.
        user_info_endpoint = (
            "%s/realms/%s/protocol/openid-connect/userinfo" %
            (CONF.keycloak_oidc.auth_url, realm_name)
        )

        verify = None
        if urllib.parse.urlparse(user_info_endpoint).scheme == "https":
            verify = False if insecure else cafile

        cert = (certfile, keyfile) if certfile and keyfile else None

        try:
            resp = requests.get(
                user_info_endpoint,
                headers={"Authorization": "Bearer %s" % access_token},
                verify=verify,
                cert=cert
            )
        except requests.ConnectionError:
            msg = _("Can't connect to keycloak server with address '%s'."
                    ) % CONF.keycloak_oidc.auth_url
            LOG.error(msg)
            raise exc.MistralException(message=msg)

        resp.raise_for_status()

        LOG.debug(
            "HTTP response from OIDC provider: %s",
            pprint.pformat(resp.json())
        )

        req.headers["X-Identity-Status"] = "Confirmed"
        req.headers["X-Project-Id"] = realm_name
        req.headers["X-Roles"] = roles

    @staticmethod
    def get_system_ca_file():
        """Return path to system default CA file."""
        # Standard CA file locations for Debian/Ubuntu, RedHat/Fedora,
        # Suse, FreeBSD/OpenBSD, MacOSX, and the bundled ca
        ca_path = ['/etc/ssl/certs/ca-certificates.crt',
                   '/etc/pki/tls/certs/ca-bundle.crt',
                   '/etc/ssl/ca-bundle.pem',
                   '/etc/ssl/cert.pem',
                   '/System/Library/OpenSSL/certs/cacert.pem',
                   requests.certs.where()]
        for ca in ca_path:
            LOG.debug("Looking for ca file %s", ca)
            if os.path.exists(ca):
                LOG.debug("Using ca file %s", ca)
                return ca
        LOG.warning("System ca file could not be found.")
