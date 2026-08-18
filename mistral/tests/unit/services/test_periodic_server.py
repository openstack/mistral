# Copyright 2026 - OVHcloud.
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

from mistral.services import periodic
from mistral.services import periodic_server
from mistral.tests.unit import base


class PeriodicServerTest(base.DbTestCase):
    def test_start_stop(self):
        server = periodic_server.get_oslo_service()

        server.start()

        try:
            self.assertEqual(1, len(periodic._periodic_tasks))
        finally:
            server.stop()

        self.assertEqual(0, len(periodic._periodic_tasks))

    def test_start_with_cron_triggers_disabled(self):
        self.override_config('enabled', False, group='cron_trigger')

        server = periodic_server.get_oslo_service()

        server.start()

        try:
            self.assertEqual(0, len(periodic._periodic_tasks))
        finally:
            server.stop()
