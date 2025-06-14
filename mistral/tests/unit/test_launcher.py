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

import threading
import time

from oslo_config import cfg

from mistral.cmd import launch
from mistral.scheduler import base as sched_base
from mistral.tests.unit import base

CONF = cfg.CONF


class ServiceLauncherTest(base.DbTestCase):
    def setUp(self):
        super(ServiceLauncherTest, self).setUp()

        self.override_config('enabled', False, group='cron_trigger')
        self.override_config('api_workers', 2, group='api')
        # Set the transport to 'fake' for executor process
        CONF.set_default('transport_url', 'fake:/')

        launch.reset_server_managers()
        sched_base.destroy_system_scheduler()

    def test_launch_one_process(self):
        threading.Thread(target=launch.launch_any,
                         args=(['api'],)).start()

        for i in range(0, 50):
            svr_proc_mgr = launch.get_server_process_manager()

            if svr_proc_mgr:
                break

            time.sleep(0.1)

        self.assertIsNotNone(svr_proc_mgr)
        self._await(lambda: len(svr_proc_mgr.children.keys()) == 2)
        svr_proc_mgr.stop()

    def test_launch_multiple_processes(self):
        threading.Thread(target=launch.launch_any,
                         args=(['api', 'executor'],)).start()

        for i in range(0, 50):
            svr_proc_mgr = launch.get_server_process_manager()

            if svr_proc_mgr:
                break

            time.sleep(0.1)

        self.assertIsNotNone(svr_proc_mgr)

        # API x 2 + executor = 3
        self._await(lambda: len(svr_proc_mgr.children.keys()) == 3)

        svr_proc_mgr.stop()
