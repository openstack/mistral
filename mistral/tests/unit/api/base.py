# Copyright 2013 - Mirantis, Inc.
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

import mock
import pecan
import pecan.testing
from webtest import app as webtest_app

from mistral.api import app as pecan_app
from mistral.services import periodic
from mistral.tests.unit import base
from mistral.tests.unit.mstrlfixtures import policy_fixtures


class APITest(base.DbTestCase):

    def setUp(self):
        super(APITest, self).setUp()

        self.override_config('auth_enable', False, group='pecan')
        self.override_config('enabled', False, group='cron_trigger')

        self.app = pecan.testing.load_test_app(
            dict(pecan_app.get_pecan_config())
        )

        # Adding cron trigger thread clean up explicitly in case if
        # new tests will provide an alternative configuration for pecan
        # application.
        self.addCleanup(periodic.stop_all_periodic_tasks)

        # Make sure the api get the correct context.
        self.patch_ctx = mock.patch(
            'mistral.context.MistralContext.from_environ'
        )
        self.mock_ctx = self.patch_ctx.start()
        self.mock_ctx.return_value = self.ctx
        self.addCleanup(self.patch_ctx.stop)

        self.policy = self.useFixture(policy_fixtures.PolicyFixture())

    def assertNotFound(self, url):
        try:
            self.app.get(url, headers={'Accept': 'application/json'})
        except webtest_app.AppError as error:
            self.assertIn('Bad response: 404 Not Found', str(error))

            return

        self.fail('Expected 404 Not found but got OK')

    def assertUnauthorized(self, url):
        try:
            self.app.get(url, headers={'Accept': 'application/json'})
        except webtest_app.AppError as error:
            self.assertIn('Bad response: 401 Unauthorized', str(error))

            return

        self.fail('Expected 401 Unauthorized but got OK')
