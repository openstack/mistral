# -*- coding: utf-8 -*-
#
# Copyright 2013 - Mirantis, Inc.
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
from oslo_config import cfg
import pecan
import pecan.testing
import requests_mock

from mistral.db.v2 import api as db_api
from mistral.db.v2.sqlalchemy import models
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


class TestKeyCloakOIDCAuth(base.DbTestCase):
    def setUp(self):
        super(TestKeyCloakOIDCAuth, self).setUp()

        cfg.CONF.set_default('auth_enable', True, group='pecan')
        cfg.CONF.set_default('auth_type', 'keycloak-oidc')
        cfg.CONF.set_default('auth_url', AUTH_URL, group='keycloak_oidc')

        pecan_opts = cfg.CONF.pecan

        self.app = pecan.testing.load_test_app({
            'app': {
                'root': pecan_opts.root,
                'modules': pecan_opts.modules,
                'debug': pecan_opts.debug,
                'auth_enable': True,
                'disable_cron_trigger_thread': True
            }
        })

        self.addCleanup(pecan.set_config, {}, overwrite=True)
        self.addCleanup(
            cfg.CONF.set_default,
            'auth_enable',
            False,
            group='pecan'
        )
        self.addCleanup(cfg.CONF.set_default, 'auth_type', 'keystone')

        # Adding cron trigger thread clean up explicitly in case if
        # new tests will provide an alternative configuration for pecan
        # application.
        self.addCleanup(periodic.stop_all_periodic_tasks)

        # Make sure the api get the correct context.
        self.patch_ctx = mock.patch(
            'mistral.context.context_from_headers_and_env'
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

        headers = {
            'X-Auth-Token': 'cvbcvbasrtqlwkjasdfasdf',
            'X-Project-Id': REALM_NAME
        }

        resp = self.app.get('/v2/workflows/123', headers=headers)

        self.assertEqual(200, resp.status_code)
        self.assertDictEqual(WF, resp.json)

    @requests_mock.Mocker()
    @mock.patch.object(db_api, 'get_workflow_definition', MOCK_WF)
    def test_get_workflow_failed_auth(self, req_mock):
        # Imitate failure response from KeyCloak.
        req_mock.get(
            USER_INFO_ENDPOINT,
            status_code=401,
            reason='Access token is invalid'
        )

        headers = {
            'X-Auth-Token': 'cvbcvbasrtqlwkjasdfasdf',
            'X-Project-Id': REALM_NAME
        }

        resp = self.app.get(
            '/v2/workflows/123',
            headers=headers,
            expect_errors=True
        )

        self.assertEqual(401, resp.status_code)
        self.assertEqual('401 Unauthorized', resp.status)
        self.assertIn('Failed to validate access token', resp.text)
        self.assertIn('Access token is invalid', resp.text)
