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

import mock
from oslo_concurrency import processutils
from oslo_config import cfg
import pecan

from mistral.api import service
from mistral.tests.unit import base


class TestWSGIService(base.BaseTest):
    @mock.patch('mistral.api.app.setup_app')
    @mock.patch.object(service.wsgi, 'Server')
    def test_workers_set_default(self, wsgi_server, mock_app):
        service_name = "mistral_api"
        mock_app.return_value = pecan.testing.load_test_app({
            'app': {
                'root': cfg.CONF.pecan.root,
                'modules': cfg.CONF.pecan.modules,
                'debug': cfg.CONF.pecan.debug,
                'auth_enable': cfg.CONF.pecan.auth_enable,
                'disable_cron_trigger_thread': True
            }
        })
        test_service = service.WSGIService(service_name)

        wsgi_server.assert_called_once_with(
            cfg.CONF,
            service_name,
            test_service.app,
            host='0.0.0.0',
            port=8989,
            use_ssl=False
        )

    @mock.patch('mistral.api.app.setup_app')
    @mock.patch.object(service.wsgi, 'Server')
    def test_workers_set_correct_setting(self, wsgi_server, mock_app):
        self.override_config('api_workers', 8, group='api')

        mock_app.return_value = pecan.testing.load_test_app({
            'app': {
                'root': cfg.CONF.pecan.root,
                'modules': cfg.CONF.pecan.modules,
                'debug': cfg.CONF.pecan.debug,
                'auth_enable': cfg.CONF.pecan.auth_enable,
                'disable_cron_trigger_thread': True
            }
        })
        test_service = service.WSGIService("mistral_api")

        self.assertEqual(8, test_service.workers)

    @mock.patch('mistral.api.app.setup_app')
    @mock.patch.object(service.wsgi, 'Server')
    def test_workers_set_zero_setting(self, wsgi_server, mock_app):
        self.override_config('api_workers', 0, group='api')

        mock_app.return_value = pecan.testing.load_test_app({
            'app': {
                'root': cfg.CONF.pecan.root,
                'modules': cfg.CONF.pecan.modules,
                'debug': cfg.CONF.pecan.debug,
                'auth_enable': cfg.CONF.pecan.auth_enable,
                'disable_cron_trigger_thread': True
            }
        })
        test_service = service.WSGIService("mistral_api")

        self.assertEqual(processutils.get_worker_count(), test_service.workers)

    @mock.patch('mistral.api.app.setup_app')
    @mock.patch.object(service.wsgi, 'Server')
    def test_wsgi_service_with_ssl_enabled(self, wsgi_server, mock_app):
        self.override_config('enable_ssl_api', True, group='api')

        mock_app.return_value = pecan.testing.load_test_app({
            'app': {
                'root': cfg.CONF.pecan.root,
                'modules': cfg.CONF.pecan.modules,
                'debug': cfg.CONF.pecan.debug,
                'auth_enable': cfg.CONF.pecan.auth_enable,
                'disable_cron_trigger_thread': True
            }
        })
        service_name = 'mistral_api'
        srv = service.WSGIService(service_name)

        wsgi_server.assert_called_once_with(
            cfg.CONF,
            service_name,
            srv.app,
            host='0.0.0.0',
            port=8989,
            use_ssl=True
        )
