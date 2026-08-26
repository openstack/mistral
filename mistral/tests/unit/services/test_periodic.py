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

from unittest import mock

from mistral.services import maintenance
from mistral.services import periodic
from mistral.tests.unit import base


class ProcessCronTriggersMaintenanceTest(base.BaseTest):
    """Cron triggers must not start workflows during maintenance.

    The API blocks workflow starts through the maintenance hook, but cron
    triggers start workflows via a direct RPC that bypasses it, so
    process_cron_triggers_v2() has to honor the maintenance state itself.
    """

    @mock.patch('mistral.services.periodic.triggers')
    @mock.patch('mistral.services.periodic.db_api_v2.get_maintenance_status')
    def _run(self, status, get_status, mock_triggers):
        get_status.return_value = status
        mock_triggers.get_next_cron_triggers.return_value = []

        periodic.process_cron_triggers_v2(None, None)

        return mock_triggers

    def test_skips_when_paused(self):
        mock_triggers = self._run(maintenance.PAUSED)
        mock_triggers.get_next_cron_triggers.assert_not_called()

    def test_skips_when_pausing(self):
        mock_triggers = self._run(maintenance.PAUSING)
        mock_triggers.get_next_cron_triggers.assert_not_called()

    def test_processes_when_running(self):
        mock_triggers = self._run(maintenance.RUNNING)
        mock_triggers.get_next_cron_triggers.assert_called_once()

    def test_processes_when_no_maintenance_row(self):
        # get_maintenance_status() returns None when maintenance was never
        # configured; cron processing must proceed normally.
        mock_triggers = self._run(None)
        mock_triggers.get_next_cron_triggers.assert_called_once()
