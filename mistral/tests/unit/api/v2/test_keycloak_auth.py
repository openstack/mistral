# Copyright 2017 - Nokia Networks
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
import json

from cryptography.hazmat.primitives.asymmetric import rsa
import jwt
import pecan
import pecan.testing
import requests
import requests_mock
from unittest import mock

import webob

from mistral.api import app as pecan_app
from mistral.auth import keycloak
from mistral import context
from mistral.db.v2 import api as db_api
from mistral.db.v2.sqlalchemy import models
from mistral import exceptions as exc
from mistral.services import periodic
from mistral.tests.unit import base
from mistral.tests.unit.mstrlfixtures import policy_fixtures

KEYCLOAK_JSON = {
    "keys": [
        {
            "kid": "FJ86GcF3jTbNLOco4NvZkUCIUmfYCqoqtOQeMfbhNlE",
            "kty": "RSA",
            "alg": "RS256",
            "use": "sig",
            "n": "q1awrk7QK24Gmcy9Yb4dMbS-ZnO6",
            "e": "AQAB"
        }
    ]
}

WF_DEFINITION = """
---
version: '2.0'
flow:
  type: direct
  input:
    - param1
  tasks:
    task1:
      action: std.echo output="Hi"
"""

WF_DB = models.WorkflowDefinition(
    id='123e4567-e89b-12d3-a456-426655440000',
    name='flow',
    definition=WF_DEFINITION,
    created_at=datetime.datetime(1970, 1, 1),
    updated_at=datetime.datetime(1970, 1, 1),
    spec={'input': ['param1']}
)

WF = {
    'id': '123e4567-e89b-12d3-a456-426655440000',
    'name': 'flow',
    'definition': WF_DEFINITION,
    'created_at': '1970-01-01 00:00:00',
    'updated_at': '1970-01-01 00:00:00',
    'input': 'param1',
    'interface': {"input": ["param1"], "output": []}
}


MOCK_WF = mock.MagicMock(return_value=WF_DB)

# Set up config options.
AUTH_URL = 'https://my.keycloak.com:8443/auth'
REALM_NAME = 'my_realm'

USER_INFO_ENDPOINT = (
    "%s/realms/%s/protocol/openid-connect/userinfo" % (AUTH_URL, REALM_NAME)
)

USER_CLAIMS = {
    "sub": "248289761001",
    "name": "Jane Doe",
    "given_name": "Jane",
    "family_name": "Doe",
    "preferred_username": "j.doe",
    "email": "janedoe@example.com",
    "picture": "http://example.com/janedoe/me.jpg"
}

WWW_AUTHENTICATE_HEADER = {'WWW-Authenticate': 'unauthorized reason is ...'}

PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
ATTACKER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _sign(roles, key=PRIVATE_KEY, realm=REALM_NAME):
    claims = {
        "sub": "248289761001",
        "aud": "openstack",
        "iss": "http://localhost:8080/auth/realms/%s" % realm,
        "realm_access": {"roles": roles}
    }

    return jwt.encode(claims, key, algorithm='RS256')


class TestKeyCloakOIDCAuth(base.BaseTest):
    def setUp(self):
        super(TestKeyCloakOIDCAuth, self).setUp()

        self.override_config('auth_url', AUTH_URL, group='keycloak_oidc')

        self.auth_handler = keycloak.KeycloakAuthHandler()

    def _build_request(self, token):
        req = webob.Request.blank("/")

        req.headers["x-auth-token"] = token
        req.get_response = lambda app: None

        return req

    @mock.patch("requests.get")
    def test_header_parsing(self, mocked_get):
        self.override_config(
            'user_info_endpoint_url',
            'https://127.0.0.1:9080',
            'keycloak_oidc'
        )

        token = {
            "iss": "http://localhost:8080/auth/realms/my_realm",
            "realm_access": {
                "roles": ["role1", "role2"]
            }
        }

        mocked_resp = mock.Mock()
        mocked_resp.status_code = 200
        mocked_resp.json.return_value = KEYCLOAK_JSON

        mocked_get.return_value = mocked_resp

        req = self._build_request(token)

        with mock.patch("jwt.decode", return_value=token):
            self.auth_handler.authenticate(req)

        self.assertEqual("Confirmed", req.headers["X-Identity-Status"])
        self.assertEqual("my_realm", req.headers["X-Project-Id"])
        self.assertEqual("role1,role2", req.headers["X-Roles"])
        self.assertEqual(1, mocked_get.call_count)

    def test_no_auth_token(self):
        req = webob.Request.blank("/")

        self.assertRaises(
            exc.UnauthorizedException,
            self.auth_handler.authenticate,
            req
        )

    @mock.patch("requests.get")
    def test_no_realm_roles(self, mocked_get):
        token = {
            "aud": "openstack",
            "iss": "http://localhost:8080/auth/realms/my_realm",
        }

        mocked_resp = mock.Mock()

        mocked_resp.status_code = 200
        mocked_resp.json.return_value = KEYCLOAK_JSON

        mocked_get.return_value = mocked_resp

        req = self._build_request(token)

        with mock.patch("jwt.decode", return_value=token):
            self.auth_handler.authenticate(req)

        self.assertEqual("Confirmed", req.headers["X-Identity-Status"])
        self.assertEqual("my_realm", req.headers["X-Project-Id"])
        self.assertEqual("", req.headers["X-Roles"])

    def test_wrong_token_format(self):
        req = self._build_request(token="WRONG_FORMAT_TOKEN")

        self.assertRaises(
            exc.UnauthorizedException,
            self.auth_handler.authenticate,
            req
        )

    @requests_mock.Mocker()
    def test_server_unauthorized(self, req_mock):
        self.override_config(
            'user_info_endpoint_url',
            'https://127.0.0.1:9080',
            'keycloak_oidc'
        )

        token = {
            "aud": "openstack",
            "iss": "http://localhost:8080/auth/realms/my_realm",
        }

        # Imitate failure response from KeyCloak.
        req_mock.get(
            'https://127.0.0.1:9080',
            status_code=401,
            reason='Access token is invalid',
            headers=WWW_AUTHENTICATE_HEADER
        )

        req = self._build_request(token)

        with mock.patch("jwt.decode", return_value=token):
            try:
                self.auth_handler.authenticate(req)
            except requests.exceptions.HTTPError as e:
                self.assertIn(
                    "401 Client Error: Access token is invalid for url",
                    str(e)
                )
                self.assertEqual(
                    'unauthorized reason is ...',
                    e.response.headers.get('WWW-Authenticate')
                )
            else:
                raise Exception("Test is broken")

    @mock.patch("requests.get")
    def test_connection_error(self, mocked_get):
        token = {
            "aud": "openstack",
            "iss": "http://localhost:8080/auth/realms/my_realm",
            "realm_access": {
                "roles": ["role1", "role2"]
            }
        }

        mocked_get.side_effect = requests.ConnectionError

        req = self._build_request(token)

        with mock.patch("jwt.decode", return_value=token):
            self.assertRaises(
                exc.MistralException,
                self.auth_handler.authenticate,
                req
            )

    def _authenticate_signed(self, token, headers=None):
        req = self._build_request(token)

        for name, value in (headers or {}).items():
            req.headers[name] = value

        with mock.patch.object(
                keycloak.KeycloakAuthHandler,
                'get_public_key',
                return_value=PRIVATE_KEY.public_key()):
            self.auth_handler.authenticate(req)

        return req

    def test_verified_token(self):
        req = self._authenticate_signed(_sign(["role1", "admin"]))

        self.assertEqual("Confirmed", req.headers["X-Identity-Status"])
        self.assertEqual(REALM_NAME, req.headers["X-Project-Id"])
        self.assertEqual("role1,admin", req.headers["X-Roles"])
        self.assertEqual("248289761001", req.headers["X-User-Id"])
        self.assertTrue(req.environ["mistral.is_admin"])

    def test_forged_token_cannot_set_admin(self):
        req = self._build_request(_sign(["admin"], key=ATTACKER_KEY))

        with mock.patch.object(
                keycloak.KeycloakAuthHandler,
                'get_public_key',
                return_value=PRIVATE_KEY.public_key()):
            self.assertRaises(
                exc.UnauthorizedException,
                self.auth_handler.authenticate,
                req
            )

        self.assertNotIn("mistral.is_admin", req.environ)
        self.assertNotIn("X-Roles", req.headers)
        self.assertNotIn("X-Identity-Status", req.headers)

    def test_admin_role_option(self):
        self.override_config('admin_role', 'mistral-admin', 'keycloak_oidc')

        req = self._authenticate_signed(_sign(["admin"]))

        self.assertFalse(req.environ["mistral.is_admin"])

        req = self._authenticate_signed(_sign(["mistral-admin"]))

        self.assertTrue(req.environ["mistral.is_admin"])

    def test_admin_role_disabled(self):
        self.override_config('admin_role', '', 'keycloak_oidc')

        req = self._authenticate_signed(_sign(["admin"]))

        self.assertFalse(req.environ["mistral.is_admin"])

    def test_admin_realm_option(self):
        self.override_config('admin_realm', 'master', 'keycloak_oidc')

        req = self._authenticate_signed(_sign(["admin"]))

        self.assertFalse(req.environ["mistral.is_admin"])

        req = self._authenticate_signed(_sign(["admin"], realm='master'))

        self.assertTrue(req.environ["mistral.is_admin"])

    def test_spoofed_identity_headers_removed(self):
        req = self._authenticate_signed(
            _sign(["role1"]),
            headers={
                "X-User-Id": "spoofed",
                "X-User-Name": "spoofed",
                "X-Tenant-Id": "spoofed",
                "X-Service-Roles": "admin",
                "X-Is-Admin-Project": "True"
            }
        )

        self.assertEqual("248289761001", req.headers["X-User-Id"])
        self.assertNotIn("X-User-Name", req.headers)
        self.assertNotIn("X-Tenant-Id", req.headers)
        self.assertNotIn("X-Service-Roles", req.headers)
        self.assertNotIn("X-Is-Admin-Project", req.headers)
        self.assertFalse(req.environ["mistral.is_admin"])

    @mock.patch("requests.get")
    def test_user_info_endpoint_sets_admin(self, mocked_get):
        self.override_config(
            'user_info_endpoint_url',
            'https://127.0.0.1:9080',
            'keycloak_oidc'
        )

        mocked_resp = mock.Mock()
        mocked_resp.status_code = 200
        mocked_resp.json.return_value = USER_CLAIMS

        mocked_get.return_value = mocked_resp

        req = self._build_request(_sign(["admin"], key=ATTACKER_KEY))

        self.auth_handler.authenticate(req)

        self.assertEqual(1, mocked_get.call_count)
        self.assertEqual("admin", req.headers["X-Roles"])
        self.assertTrue(req.environ["mistral.is_admin"])

    @mock.patch("requests.get")
    def test_user_info_endpoint_rejects_token(self, mocked_get):
        self.override_config(
            'user_info_endpoint_url',
            'https://127.0.0.1:9080',
            'keycloak_oidc'
        )

        mocked_resp = mock.Mock()
        mocked_resp.status_code = 401
        mocked_resp.raise_for_status.side_effect = requests.HTTPError

        mocked_get.return_value = mocked_resp

        req = self._build_request(_sign(["admin"], key=ATTACKER_KEY))

        self.assertRaises(
            requests.HTTPError,
            self.auth_handler.authenticate,
            req
        )

        self.assertNotIn("mistral.is_admin", req.environ)


class TestKeyCloakOIDCAuthScenarios(base.DbTestCase):
    def setUp(self):
        super(TestKeyCloakOIDCAuthScenarios, self).setUp()

        self.override_config('enabled', False, group='cron_trigger')
        self.override_config('auth_enable', True, group='pecan')
        self.override_config('auth_type', 'keycloak-oidc')
        self.override_config('auth_url', AUTH_URL, group='keycloak_oidc')

        self.app = pecan.testing.load_test_app(
            dict(pecan_app.get_pecan_config())
        )

        # Adding cron trigger thread clean up explicitly in case if
        # new tests will provide an alternative configuration for pecan
        # application.
        self.addCleanup(periodic.stop_all_periodic_tasks)

        # Make sure the api get the correct context.
        self.patch_ctx = mock.patch(
            'mistral.context.MistralContext.from_environ'
        )
        self.mock_ctx = self.patch_ctx.start()
        self.mock_ctx.return_value = self.ctx

        self.addCleanup(self.patch_ctx.stop)

        self.policy = self.useFixture(policy_fixtures.PolicyFixture())

    @mock.patch("requests.get")
    @mock.patch.object(db_api, 'get_workflow_definition', MOCK_WF)
    def test_get_workflow_success_auth(self, mocked_get):
        mocked_resp = mock.Mock()

        mocked_resp.status_code = 200
        mocked_resp.json.return_value = KEYCLOAK_JSON

        mocked_get.return_value = mocked_resp

        token = {
            "iss": "http://localhost:8080/auth/realms/%s" % REALM_NAME,
            "realm_access": {
                "roles": ["role1", "role2"]
            }
        }

        headers = {'X-Auth-Token': str(token)}

        with mock.patch("jwt.decode", return_value=token):
            resp = self.app.get('/v2/workflows/123', headers=headers)

        resp_json = resp.json
        resp_json['interface'] = json.loads(resp_json['interface'])

        self.assertEqual(200, resp.status_code)
        self.assertDictEqual(WF, resp_json)

    @mock.patch("requests.get")
    @mock.patch.object(db_api, 'get_workflow_definition', MOCK_WF)
    def test_get_workflow_invalid_token_format(self, mocked_get):
        token = 'WRONG_FORMAT_TOKEN'

        headers = {'X-Auth-Token': str(token)}

        # We don't mock jwt.decode so the test must fail.

        resp = self.app.get(
            '/v2/workflows/123',
            headers=headers,
            expect_errors=True
        )

        self.assertEqual(401, resp.status_code)
        self.assertEqual('401 Unauthorized', resp.status)
        self.assertIn('Failed to validate access token', resp.text)
        self.assertIn(
            "Token can't be decoded because of wrong format",
            resp.text
        )

    @mock.patch("requests.get")
    @mock.patch.object(db_api, 'get_workflow_definition', MOCK_WF)
    def test_get_workflow_failed_auth(self, mocked_get):
        mocked_resp = mock.Mock()

        mocked_resp.status_code = 200
        mocked_resp.json.return_value = KEYCLOAK_JSON

        mocked_get.return_value = mocked_resp

        # A token without an issuer (iss).
        token = {
            "realm_access": {
                "roles": ["role1", "role2"]
            }
        }

        headers = {'X-Auth-Token': str(token)}

        with mock.patch("jwt.decode", return_value=token):
            resp = self.app.get(
                '/v2/workflows/123',
                headers=headers,
                expect_errors=True
            )

        self.assertEqual(401, resp.status_code)
        self.assertEqual('401 Unauthorized', resp.status)
        self.assertIn("Failed to validate access token: 'iss'", resp.text)


class TestKeyCloakOIDCAuthApp(base.DbTestCase):
    """Test that Keycloak auth params get passed to the security context."""

    def setUp(self):
        super(TestKeyCloakOIDCAuthApp, self).setUp()

        self.override_config('enabled', False, group='cron_trigger')
        self.override_config('auth_enable', True, group='pecan')
        self.override_config('auth_type', 'keycloak-oidc')
        self.override_config('auth_url', AUTH_URL, group='keycloak_oidc')

        self.app = pecan.testing.load_test_app(
            dict(pecan_app.get_pecan_config())
        )

        # Adding cron trigger thread clean up explicitly in case if
        # new tests will provide an alternative configuration for pecan
        # application.
        self.addCleanup(periodic.stop_all_periodic_tasks)

        self.policy = self.useFixture(policy_fixtures.PolicyFixture())

    @mock.patch("requests.get")
    @mock.patch.object(db_api, 'get_workflow_definition', MOCK_WF)
    def test_params_transition(self, mocked_get):
        mocked_resp = mock.Mock()

        mocked_resp.status_code = 200
        mocked_resp.json.return_value = KEYCLOAK_JSON

        mocked_get.return_value = mocked_resp

        token = {
            "iss": "http://localhost:8080/auth/realms/%s" % REALM_NAME,
            "realm_access": {
                "roles": ["role1", "role2"]
            }
        }

        headers = {'X-Auth-Token': str(token)}

        with mock.patch("jwt.decode", return_value=token):
            with mock.patch("mistral.context.set_ctx") as mocked_set_cxt:
                self.app.get('/v2/workflows/123', headers=headers)

                calls = mocked_set_cxt.call_args_list

                self.assertEqual(2, len(calls))

                # First positional argument of the first call ('before').
                ctx = calls[0][0][0]

                self.assertIsInstance(ctx, context.MistralContext)
                self.assertEqual('my_realm', ctx.project_id)
                self.assertEqual(["role1", "role2"], ctx.roles)

                # Second call of set_ctx ('after'), where we reset the context.
                self.assertIsNone(calls[1][0][0])

    @mock.patch.object(db_api, 'get_workflow_definition', MOCK_WF)
    def test_admin_role_not_granted_by_other_role(self):
        self.override_config('admin_role', 'mistral-admin', 'keycloak_oidc')

        headers = {'X-Auth-Token': _sign(["admin"])}

        with mock.patch.object(
                keycloak.KeycloakAuthHandler,
                'get_public_key',
                return_value=PRIVATE_KEY.public_key()):
            with mock.patch("mistral.context.set_ctx") as mocked_set_cxt:
                self.app.get('/v2/workflows/123', headers=headers)

                ctx = mocked_set_cxt.call_args_list[0][0][0]

                self.assertEqual(["admin"], ctx.roles)
                self.assertFalse(ctx.is_admin)

    @mock.patch.object(db_api, 'get_workflow_definition', MOCK_WF)
    def test_admin_role_granted(self):
        self.override_config('admin_role', 'mistral-admin', 'keycloak_oidc')

        headers = {'X-Auth-Token': _sign(["mistral-admin"])}

        with mock.patch.object(
                keycloak.KeycloakAuthHandler,
                'get_public_key',
                return_value=PRIVATE_KEY.public_key()):
            with mock.patch("mistral.context.set_ctx") as mocked_set_cxt:
                self.app.get('/v2/workflows/123', headers=headers)

                ctx = mocked_set_cxt.call_args_list[0][0][0]

                self.assertTrue(ctx.is_admin)
