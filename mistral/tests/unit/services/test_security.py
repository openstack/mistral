# Copyright 2026 - OVHcloud
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

from unittest import mock

from mistral.services import security
from mistral.tests.unit import base


class CreateTrustTest(base.BaseTest):
    @mock.patch.object(security, 'keystone')
    @mock.patch.object(security, 'auth_ctx')
    def test_create_trust_uses_ctx_user_id_as_trustor(self, m_ctx, m_ks):
        m_ctx.ctx.return_value = mock.Mock(
            user_id='real-user', roles=['member'], project_id='proj-1')
        m_ks.client.return_value = mock.Mock(user_id='should-not-be-used')
        m_ks.client_for_admin.return_value.session.get_user_id.return_value \
            = 'mistral-svc'

        security.create_trust()

        m_ks.client.return_value.trusts.create.assert_called_once_with(
            trustor_user='real-user',
            trustee_user='mistral-svc',
            impersonation=True,
            role_names=['member'],
            project='proj-1',
        )
