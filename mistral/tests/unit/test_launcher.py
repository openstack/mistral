# Copyright 2017 - Brocade Communications Systems, Inc.
# Copyright 2018 - Extreme Networks, Inc.
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

from oslo_config import cfg
from oslo_service import service

from mistral.cmd import launch
from mistral.tests.unit import base

CONF = cfg.CONF


class ServiceLauncherTest(base.DbTestCase):
    def setUp(self):
        super(ServiceLauncherTest, self).setUp()
        self.override_config('enabled', False, group='cron_trigger')
        self.override_config('api_workers', 2, group='api')
        # Set the transport to 'fake' for executor process
        CONF.set_default('transport_url', 'fake:/')

    @mock.patch.object(service.ProcessLauncher, 'launch_service')
    @mock.patch.object(service.ProcessLauncher, 'wait')
    def test_launch_one_process(self, mock_wait, mock_launch_service):
        # Launch API
        launch.launch_any(['api'])

        # Make sure we tried to start a service
        mock_launch_service.assert_called_once_with(mock.ANY, workers=2)
        mock_wait.assert_called_once_with()

    @mock.patch.object(service.ProcessLauncher, 'launch_service')
    @mock.patch.object(service.ProcessLauncher, 'wait')
    def test_launch_multiple_processes(self, mock_wait, mock_launch_service):
        # Launch API and executor
        launch.launch_any(['api', 'executor'])

        # Make sure we tried to start 2 services
        mock_launch_service.call_count = 2
        mock_wait.call_count = 2
