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

from oslo_config import cfg
from oslo_log import log as logging
import pprint
import requests

from mistral import auth


LOG = logging.getLogger(__name__)

CONF = cfg.CONF


class KeycloakAuthHandler(auth.AuthHandler):

    def authenticate(self, req):
        realm_name = req.headers.get('X-Project-Id')

        # NOTE(rakhmerov): There's a special endpoint for introspecting
        # access tokens described in OpenID Connect specification but it's
        # available in KeyCloak starting only with version 1.8.Final so we have
        # to use user info endpoint which also takes exactly one parameter
        # (access token) and replies with error if token is invalid.
        user_info_endpoint = (
            "%s/realms/%s/protocol/openid-connect/userinfo" %
            (CONF.keycloak_oidc.auth_url, realm_name)
        )

        access_token = req.headers.get('X-Auth-Token')

        resp = requests.get(
            user_info_endpoint,
            headers={"Authorization": "Bearer %s" % access_token},
            verify=not CONF.keycloak_oidc.insecure
        )

        resp.raise_for_status()

        LOG.debug(
            "HTTP response from OIDC provider: %s" %
            pprint.pformat(resp.json())
        )
