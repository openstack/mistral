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
import mock
import pecan
import pecan.testing
import requests
import requests_mock
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
    'input': 'param1'
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

    @requests_mock.Mocker()
    def test_header_parsing(self, req_mock):
        token = {
            "iss": "http://localhost:8080/auth/realms/my_realm",
            "realm_access": {
                "roles": ["role1", "role2"]
            }
        }

        # Imitate successful response from KeyCloak with user claims.
        req_mock.get(USER_INFO_ENDPOINT, json=USER_CLAIMS)

        req = self._build_request(token)

        with mock.patch("jwt.decode", return_value=token):
            self.auth_handler.authenticate(req)

        self.assertEqual("Confirmed", req.headers["X-Identity-Status"])
        self.assertEqual("my_realm", req.headers["X-Project-Id"])
        self.assertEqual("role1,role2", req.headers["X-Roles"])
        self.assertEqual(1, req_mock.call_count)

    def test_no_auth_token(self):
        req = webob.Request.blank("/")

        self.assertRaises(
            exc.UnauthorizedException,
            self.auth_handler.authenticate,
            req
        )

    @requests_mock.Mocker()
    def test_no_realm_roles(self, req_mock):
        token = {"iss": "http://localhost:8080/auth/realms/my_realm"}

        # Imitate successful response from KeyCloak with user claims.
        req_mock.get(USER_INFO_ENDPOINT, json=USER_CLAIMS)

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
        token = {
            "iss": "http://localhost:8080/auth/realms/my_realm",
        }

        # Imitate failure response from KeyCloak.
        req_mock.get(
            USER_INFO_ENDPOINT,
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

    @requests_mock.Mocker()
    def test_connection_error(self, req_mock):
        token = {"iss": "http://localhost:8080/auth/realms/my_realm"}

        req_mock.get(USER_INFO_ENDPOINT, exc=requests.ConnectionError)

        req = self._build_request(token)

        with mock.patch("jwt.decode", return_value=token):
            self.assertRaises(
                exc.MistralException,
                self.auth_handler.authenticate,
                req
            )


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

    @requests_mock.Mocker()
    @mock.patch.object(db_api, 'get_workflow_definition', MOCK_WF)
    def test_get_workflow_success_auth(self, req_mock):
        # Imitate successful response from KeyCloak with user claims.
        req_mock.get(USER_INFO_ENDPOINT, json=USER_CLAIMS)

        token = {
            "iss": "http://localhost:8080/auth/realms/%s" % REALM_NAME,
            "realm_access": {
                "roles": ["role1", "role2"]
            }
        }

        headers = {'X-Auth-Token': str(token)}

        with mock.patch("jwt.decode", return_value=token):
            resp = self.app.get('/v2/workflows/123', headers=headers)

        self.assertEqual(200, resp.status_code)
        self.assertDictEqual(WF, resp.json)

    @mock.patch("requests.get")
    @mock.patch.object(db_api, 'get_workflow_definition', MOCK_WF)
    def test_get_workflow_invalid_token_format(self, req_mock):
        # Imitate successful response from KeyCloak with user claims.
        req_mock.get(USER_INFO_ENDPOINT, json=USER_CLAIMS)

        token = {
            "iss": "http://localhost:8080/auth/realms/%s" % REALM_NAME,
            "realm_access": {
                "roles": ["role1", "role2"]
            }
        }

        headers = {'X-Auth-Token': str(token)}

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

    @requests_mock.Mocker()
    @mock.patch.object(db_api, 'get_workflow_definition', MOCK_WF)
    def test_get_workflow_failed_auth(self, req_mock):
        # Imitate failure response from KeyCloak.
        req_mock.get(
            USER_INFO_ENDPOINT,
            status_code=401,
            reason='Access token is invalid'
        )

        token = {
            "iss": "http://localhost:8080/auth/realms/%s" % REALM_NAME,
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
        self.assertIn('Failed to validate access token', resp.text)
        self.assertIn('Access token is invalid', resp.text)


class TestKeyCloakOIDCAuthApp(base.DbTestCase):
    """Test that Keycloak auth params were successfully passed to Context"""

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

    @requests_mock.Mocker()
    @mock.patch.object(db_api, 'get_workflow_definition', MOCK_WF)
    def test_params_transition(self, req_mock):
        req_mock.get(USER_INFO_ENDPOINT, json=USER_CLAIMS)

        token = {
            "iss": "http://localhost:8080/auth/realms/%s" % REALM_NAME,
            "realm_access": {
                "roles": ["role1", "role2"]
            }
        }

        headers = {
            'X-Auth-Token': str(token)
        }

        with mock.patch("jwt.decode", return_value=token):
            with mock.patch("mistral.context.set_ctx") as mocked_set_cxt:
                self.app.get('/v2/workflows/123', headers=headers)
                calls = mocked_set_cxt.call_args_list
                self.assertEqual(2, len(calls))

                # First positional argument of the first call ('before')
                ctx = calls[0][0][0]

                self.assertIsInstance(ctx, context.MistralContext)
                self.assertEqual('my_realm', ctx.project_id)
                self.assertEqual(["role1", "role2"], ctx.roles)

                # Second call of set_ctx ('after'), where we reset the context
                self.assertIsNone(calls[1][0][0])
