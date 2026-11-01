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

import datetime
from unittest import mock

from keystoneauth1 import exceptions as ks_exc
from oslo_utils import timeutils

from mistral import context
from mistral import exceptions as exc
from mistral.services import security
from mistral.tests.unit import base


class CreateTrustTest(base.BaseTest):
    @mock.patch.object(security, 'keystone')
    @mock.patch.object(security, 'auth_ctx')
    def test_create_trust_uses_ctx_user_id_as_trustor(self, m_ctx, m_ks):
        m_ctx.ctx.return_value = mock.Mock(
            user_id='real-user', roles=['member'], project_id='proj-1'
        )
        m_ks.client.return_value = mock.Mock(user_id='should-not-be-used')
        m_ks.client_for_admin.return_value.session.get_user_id.return_value = (
            'mistral-svc'
        )

        security.create_trust()

        m_ks.client.return_value.trusts.create.assert_called_once_with(
            trustor_user='real-user',
            trustee_user='mistral-svc',
            impersonation=True,
            role_names=['member'],
            project='proj-1',
        )

    @mock.patch.object(security, 'keystone')
    @mock.patch.object(security, 'auth_ctx')
    def test_create_trust_forbidden(self, m_ctx, m_ks):
        m_ctx.ctx.return_value = mock.Mock(
            user_id='real-user', roles=['member'], project_id='proj-1'
        )
        m_ks.client.return_value.trusts.create.side_effect = ks_exc.Forbidden()

        e = self.assertRaises(exc.NotAllowedException, security.create_trust)

        self.assertEqual(403, e.http_code)
        self.assertIn('allow_redelegation', str(e))


class ExecutionTrustTest(base.BaseTest):
    def setUp(self):
        super(ExecutionTrustTest, self).setUp()

        self.override_config('auth_enable', True, group='pecan')
        self.override_config('use_trusts', True, group='engine')

        self.ctx = context.MistralContext(
            user_id='user', project_id='proj', auth_token='token'
        )
        context.set_ctx(self.ctx)
        self.addCleanup(context.set_ctx, None)

    @mock.patch.object(security, 'create_trust')
    def test_add_execution_trust(self, m_create):
        m_create.return_value = mock.Mock(id='trust-1')

        security.add_execution_trust()

        self.assertEqual('trust-1', self.ctx.trust_id)
        self.assertTrue(self.ctx.is_trust_scoped)
        self.assertTrue(self.ctx.execution_trust)

    @mock.patch.object(security, 'create_trust')
    def test_add_execution_trust_disabled(self, m_create):
        self.override_config('use_trusts', False, group='engine')

        security.add_execution_trust()

        m_create.assert_not_called()
        self.assertIsNone(self.ctx.trust_id)

    @mock.patch.object(security, 'create_trust')
    def test_add_execution_trust_keeps_existing_trust(self, m_create):
        self.ctx.trust_id = 'cron-trust'

        security.add_execution_trust()

        m_create.assert_not_called()
        self.assertFalse(self.ctx.execution_trust)

    @mock.patch.object(security, 'create_trust')
    def test_add_execution_trust_failure_keeps_token(self, m_create):
        m_create.side_effect = exc.NotAllowedException('no')

        security.add_execution_trust()

        self.assertIsNone(self.ctx.trust_id)
        self.assertFalse(self.ctx.execution_trust)

    @mock.patch.object(security, 'delete_trust')
    def test_delete_execution_trust(self, m_delete):
        self.ctx.trust_id = 'trust-1'
        self.ctx.is_trust_scoped = True
        self.ctx.execution_trust = True

        security.delete_execution_trust()

        m_delete.assert_called_once_with('trust-1')
        self.assertIsNone(self.ctx.trust_id)

    @mock.patch.object(security, 'delete_trust')
    def test_delete_execution_trust_ignores_other_trusts(self, m_delete):
        self.ctx.trust_id = 'cron-trust'
        self.ctx.is_trust_scoped = True

        security.delete_execution_trust()

        m_delete.assert_not_called()


class RefreshContextTest(base.BaseTest):
    def setUp(self):
        super(RefreshContextTest, self).setUp()

        self.override_config('auth_enable', True, group='pecan')

    def _ctx(self, expires_in):
        expires_at = timeutils.utcnow() + datetime.timedelta(
            minutes=expires_in
        )

        return context.MistralContext(
            user_id='user',
            project_id='proj',
            auth_token='old',
            trust_id='trust-1',
            is_trust_scoped=True,
            expires_at=expires_at.isoformat(),
        )

    @mock.patch.object(security, 'create_context')
    def test_valid_token_is_kept(self, m_create):
        ctx = self._ctx(expires_in=30)

        self.assertEqual('old', security.refresh_context(ctx).auth_token)
        m_create.assert_not_called()

    @mock.patch.object(security, 'create_context')
    def test_expiring_token_is_renewed(self, m_create):
        m_create.return_value = context.MistralContext(
            user_id='trustee', auth_token='new', expires_at='2099-01-01'
        )
        ctx = self._ctx(expires_in=2)

        ctx = security.refresh_context(ctx)

        m_create.assert_called_once_with('trust-1', 'proj')
        self.assertEqual('new', ctx.auth_token)
        self.assertEqual('2099-01-01', ctx.expires_at)
        self.assertEqual('trust-1', ctx.trust_id)

    @mock.patch.object(security, 'create_context')
    def test_no_trust_no_refresh(self, m_create):
        ctx = self._ctx(expires_in=-10)
        ctx.trust_id = None

        self.assertEqual('old', security.refresh_context(ctx).auth_token)
        m_create.assert_not_called()

    @mock.patch.object(security, 'create_context')
    def test_rpc_deserialize_refreshes(self, m_create):
        m_create.return_value = context.MistralContext(
            user_id='trustee', auth_token='new', expires_at='2099-01-01'
        )
        serializer = context.RpcContextSerializer()
        ctx_dict = serializer.serialize_context(self._ctx(expires_in=1))

        ctx = serializer.deserialize_context(ctx_dict)

        self.assertEqual('new', ctx.auth_token)
        self.assertEqual('new', context.ctx().auth_token)
        context.set_ctx(None)
