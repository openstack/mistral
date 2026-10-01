# Copyright 2026 - CERN
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

from keystoneauth1 import loading as ks_loading
from oslo_config import cfg

from mistral.tests.unit import base
from mistral.utils.openstack import keystone


@mock.patch.object(keystone, 'ks_client')
@mock.patch.object(keystone, 'loading')
class AdminClientTest(base.BaseTest):
    def setUp(self):
        super(AdminClientTest, self).setUp()

        self.override_config('auth_type', 'password', 'keystone_authtoken')

        # auth_url is registered by the auth plugin at runtime.
        cfg.CONF.register_opts(
            ks_loading.get_auth_plugin_conf_options('password'),
            group='keystone_authtoken'
        )

    def test_client_for_trusts_uses_auth_url(self, m_loading, m_ks):
        self.override_config('auth_url', 'https://keystone.example/v3',
                             'keystone_authtoken')

        keystone.client_for_trusts('trust-id')

        m_ks.Client.assert_called_once_with(
            session=m_loading.load_session_from_conf_options.return_value,
            endpoint_override='https://keystone.example/v3'
        )

    def test_client_for_trusts_appends_v3(self, m_loading, m_ks):
        self.override_config('auth_url', 'https://keystone.example/',
                             'keystone_authtoken')

        keystone.client_for_trusts('trust-id')

        m_ks.Client.assert_called_once_with(
            session=m_loading.load_session_from_conf_options.return_value,
            endpoint_override='https://keystone.example/v3'
        )
