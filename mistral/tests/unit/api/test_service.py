# Copyright 2016 NEC Corporation. All rights reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from unittest import mock

from oslo_concurrency import processutils
from oslo_config import cfg
from oslo_service import sslutils

from mistral.api import service
from mistral.tests.unit import base

CONF = cfg.CONF


class TestWSGIService(base.BaseTest):
    def setUp(self):
        super(TestWSGIService, self).setUp()
        self.override_config('enabled', False, group='cron_trigger')
        sslutils.register_opts(CONF)
        self.server = mock.Mock()

    @mock.patch.object(processutils, 'get_worker_count', lambda: 2)
    @mock.patch.object(service.wsgi, 'Server')
    def test_workers_set_default(self, wsgi_server):
        service_name = "mistral_api"
        with mock.patch('mistral.api.app.setup_app'):
            test_service = service.WSGIService(service_name)
            self.assertEqual(1, test_service.workers)
            wsgi_server.assert_called_once_with(
                bind_addr=('0.0.0.0', 8989),
                wsgi_app=test_service.app,
                server_name=service_name,
            )

    def test_workers_set_correct_setting(self):
        # NOTE(amorin) since we moved to cheroot, we can't start more than
        # one worker, so, no matter what the setting will be set to,
        # mistral will start only one worker
        self.override_config('api_workers', 8, group='api')

        with mock.patch('mistral.api.app.setup_app'):
            test_service = service.WSGIService("mistral_api")

            self.assertEqual(1, test_service.workers)

    @mock.patch.object(processutils, 'get_worker_count', lambda: 3)
    def test_workers_set_zero_setting(self):
        self.override_config('api_workers', 0, group='api')

        with mock.patch('mistral.api.app.setup_app'):
            test_service = service.WSGIService("mistral_api")

            self.assertEqual(1, test_service.workers)

    @mock.patch.object(service.wsgi, 'Server')
    @mock.patch('mistral.api.service.cheroot_ssl.BuiltinSSLAdapter',
                autospec=True)
    @mock.patch('mistral.api.service.validate_cert_paths',
                autospec=True)
    @mock.patch('oslo_service.sslutils.is_enabled', return_value=True,
                autospec=True)
    def test_wsgi_service_with_ssl_enabled(self, mock_is_enabled,
                                           mock_validate_tls,
                                           mock_ssl_adapter,
                                           wsgi_server):
        wsgi_server.return_value = self.server
        self.override_config('enable_ssl_api', True, group='api')
        self.override_config('cert_file', '/path/to/cert', group='ssl')
        self.override_config('key_file', '/path/to/key', group='ssl')

        service_name = 'mistral_api'

        with mock.patch('mistral.api.app.setup_app'):
            test_service = service.WSGIService(service_name)

            wsgi_server.assert_called_once_with(
                server_name=service_name,
                wsgi_app=test_service.app,
                bind_addr=('0.0.0.0', 8989)
            )

            mock_ssl_adapter.assert_called_once_with(
                certificate='/path/to/cert',
                private_key='/path/to/key'
            )
            self.assertIsNotNone(self.server.ssl_adapter)
