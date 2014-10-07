# -*- coding: utf-8 -*-
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
import uuid

from keystonemiddleware import auth_token
import mock
from oslo.config import cfg
import pecan
import pecan.testing

from mistral.db.v1 import api as db_api
from mistral.db.v1.sqlalchemy import models
from mistral.openstack.common import timeutils
from mistral.tests.unit.api import base


WORKBOOKS = [
    {
        u'name': u'my_workbook',
        u'description': u'My cool Mistral workbook',
        u'scope': None,
        u'tags': [u'deployment', u'demo']
    }
]


PKI_TOKEN_VERIFIED = {
    'token': {
        'methods': ['password'],
        'roles': [{'id': uuid.uuid4().hex,
                   'name': 'admin'}],
        'expires_at': timeutils.isotime(datetime.datetime.utcnow() +
                                        datetime.timedelta(seconds=60)),
        'project': {
            'domain': {'id': 'default', 'name': 'Default'},
            'id': uuid.uuid4().hex,
            'name': 'Mistral'
        },
        'catalog': [],
        'extras': {},
        'user': {
            'domain': {'id': 'default', 'name': 'Default'},
            'id': uuid.uuid4().hex,
            'name': 'admin'
        },
        'issued_at': timeutils.isotime()
    }
}


def get_mock_workbook(values):
    wb = models.Workbook()
    wb.update(values)
    return wb


class TestKeystoneMiddleware(base.FunctionalTest):
    """Test that the keystone middleware AuthProtocol is executed
    when enabled.
    """

    def setUp(self):
        super(TestKeystoneMiddleware, self).setUp()
        cfg.CONF.set_default('auth_enable', True, group='pecan')
        self.app = pecan.testing.load_test_app({
            'app': {
                'root': cfg.CONF.pecan.root,
                'modules': cfg.CONF.pecan.modules,
                'debug': cfg.CONF.pecan.debug,
                'auth_enable': cfg.CONF.pecan.auth_enable
            }
        })

    @mock.patch.object(
        auth_token.AuthProtocol, '_get_user_token_from_header',
        mock.MagicMock(return_value=''))
    @mock.patch.object(
        auth_token.AuthProtocol, '_validate_token',
        mock.MagicMock(return_value=PKI_TOKEN_VERIFIED))
    @mock.patch.object(
        db_api, "workbook_get",
        mock.MagicMock(return_value=get_mock_workbook(WORKBOOKS[0])))
    def test_auth_succeed(self):
        resp = self.app.get('/v1/workbooks/my_workbook')
        self.assertEqual(resp.status_int, 200)
        self.assertDictEqual(WORKBOOKS[0], resp.json)

    @mock.patch.object(
        auth_token.AuthProtocol, '_get_user_token_from_header',
        mock.MagicMock(return_value=''))
    @mock.patch.object(
        db_api, "workbook_get",
        mock.MagicMock(return_value=get_mock_workbook(WORKBOOKS[0])))
    def test_auth_fail(self):
        # 401 unauthorized response is expected because the method
        # _validate_user_token is not mocked in this test.
        self.assertUnauthorized('/v1/workbooks/my_workbook')
