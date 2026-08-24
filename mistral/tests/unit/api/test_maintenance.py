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

from mistral.tests.unit.api import base
from mistral.tests.unit import base as unit_base


class TestMaintenanceController(base.APITest):
    """Checks that the maintenance endpoint is admin-only.

    Pausing maintenance is a cluster-wide operation that pauses running
    executions across all projects, and reading the status exposes
    cluster-wide operational state, so both GET and PUT /maintenance
    must be restricted to administrators (policies 'maintenance:get'
    and 'maintenance:update').
    """

    @mock.patch('mistral.db.v2.api.get_maintenance_status')
    @mock.patch('mistral.context.MistralContext.from_environ')
    def test_get_status_admin_allowed(self, mock_context, mock_get):
        mock_context.return_value = unit_base.get_context(admin=True)
        mock_get.return_value = 'RUNNING'

        resp = self.app.get('/maintenance')

        self.assertEqual(200, resp.status_int)
        self.assertEqual('RUNNING', resp.json['status'])

    @mock.patch('mistral.db.v2.api.get_maintenance_status')
    def test_get_status_non_admin_forbidden(self, mock_get):
        # The default request context is a non-admin user.
        resp = self.app.get('/maintenance', expect_errors=True)

        self.assertEqual(403, resp.status_int)
        # The maintenance state must not have been read.
        self.assertFalse(mock_get.called)

    @mock.patch('mistral.services.maintenance.change_maintenance_mode')
    @mock.patch('mistral.context.MistralContext.from_environ')
    def test_put_status_admin_allowed(self, mock_context, mock_change):
        mock_context.return_value = unit_base.get_context(admin=True)
        mock_change.return_value = 'PAUSED'

        resp = self.app.put_json('/maintenance', {'status': 'PAUSED'})

        self.assertEqual(200, resp.status_int)
        self.assertEqual('PAUSED', resp.json['status'])
        mock_change.assert_called_once_with('PAUSED')

    @mock.patch('mistral.services.maintenance.change_maintenance_mode')
    def test_put_status_non_admin_forbidden(self, mock_change):
        # The default request context is a non-admin user.
        resp = self.app.put_json(
            '/maintenance',
            {'status': 'PAUSED'},
            expect_errors=True
        )

        self.assertEqual(403, resp.status_int)
        # The maintenance state must not have been touched.
        self.assertFalse(mock_change.called)
