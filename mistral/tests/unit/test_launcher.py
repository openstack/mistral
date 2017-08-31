# Copyright 2017 - Brocade Communications Systems, Inc.
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

import eventlet
import mock
import pecan.testing

from oslo_config import cfg

from mistral.api import service as api_service
from mistral.cmd import launch
from mistral.tests.unit import base


class ServiceLauncherTest(base.DbTestCase):

    def setUp(self):
        super(ServiceLauncherTest, self).setUp()
        launch.reset_server_managers()

    @mock.patch('mistral.api.app.setup_app')
    @mock.patch.object(api_service.wsgi, 'Server')
    def test_launch_all(self, wsgi_server, mock_app):
        mock_app.return_value = pecan.testing.load_test_app({
            'app': {
                'root': cfg.CONF.pecan.root,
                'modules': cfg.CONF.pecan.modules,
                'debug': cfg.CONF.pecan.debug,
                'auth_enable': cfg.CONF.pecan.auth_enable,
                'disable_cron_trigger_thread': True
            }
        })

        eventlet.spawn(launch.launch_any, launch.LAUNCH_OPTIONS.keys())

        for i in range(0, 50):
            svr_proc_mgr = launch.get_server_process_manager()
            svr_thrd_mgr = launch.get_server_thread_manager()

            if svr_proc_mgr and svr_thrd_mgr:
                break

            eventlet.sleep(0.1)

        self.assertIsNotNone(svr_proc_mgr)
        self.assertIsNotNone(svr_thrd_mgr)

        api_server = api_service.WSGIService('mistral_api')
        api_workers = api_server.workers

        self.assertEqual(len(svr_proc_mgr.children.keys()), api_workers)
        self.assertEqual(len(svr_thrd_mgr.services.services), 3)

    @mock.patch('mistral.api.app.setup_app')
    @mock.patch.object(api_service.wsgi, 'Server')
    def test_launch_process(self, wsgi_server, mock_app):
        mock_app.return_value = pecan.testing.load_test_app({
            'app': {
                'root': cfg.CONF.pecan.root,
                'modules': cfg.CONF.pecan.modules,
                'debug': cfg.CONF.pecan.debug,
                'auth_enable': cfg.CONF.pecan.auth_enable,
                'disable_cron_trigger_thread': True
            }
        })

        eventlet.spawn(launch.launch_any, ['api'])

        for i in range(0, 50):
            svr_proc_mgr = launch.get_server_process_manager()

            if svr_proc_mgr:
                break

            eventlet.sleep(0.1)

        svr_thrd_mgr = launch.get_server_thread_manager()

        self.assertIsNotNone(svr_proc_mgr)
        self.assertIsNone(svr_thrd_mgr)

        api_server = api_service.WSGIService('mistral_api')
        api_workers = api_server.workers

        self.assertEqual(len(svr_proc_mgr.children.keys()), api_workers)

    def test_launch_thread(self):
        eventlet.spawn(launch.launch_any, ['engine'])

        for i in range(0, 50):
            svr_thrd_mgr = launch.get_server_thread_manager()

            if svr_thrd_mgr:
                break

            eventlet.sleep(0.1)

        svr_proc_mgr = launch.get_server_process_manager()

        self.assertIsNone(svr_proc_mgr)
        self.assertIsNotNone(svr_thrd_mgr)

        self.assertEqual(len(svr_thrd_mgr.services.services), 1)
