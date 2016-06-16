# Copyright 2016 NEC Corporation. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from oslo_concurrency.fixture import lockutils
from oslo_log import log as logging
from tempest.lib import exceptions
from tempest import test

from mistral_tempest_tests.tests import base


LOG = logging.getLogger(__name__)


class CronTriggerTestsV2(base.TestCase):

    _service = 'workflowv2'

    def setUp(self):
        super(CronTriggerTestsV2, self).setUp()
        self.useFixture(lockutils.LockFixture('mistral-workflow'))
        _, body = self.client.create_workflow('wf_v2.yaml')
        self.wf_name = body['workflows'][0]['name']

    def tearDown(self):

        for tr in self.client.triggers:
            self.client.delete_obj('cron_triggers', tr)
        self.client.triggers = []

        for wf in self.client.workflows:
            self.client.delete_obj('workflows', wf)
        self.client.workflows = []

        super(CronTriggerTestsV2, self).tearDown()

    @test.attr(type='smoke')
    def test_get_list_cron_triggers(self):
        resp, body = self.client.get_list_obj('cron_triggers')

        self.assertEqual(200, resp.status)
        self.assertEqual([], body['cron_triggers'])

    @test.attr(type='sanity')
    def test_create_and_delete_cron_triggers(self):
        tr_name = 'trigger'

        resp, body = self.client.create_cron_trigger(
            tr_name, self.wf_name, None, '5 * * * *')
        self.assertEqual(201, resp.status)
        self.assertEqual(tr_name, body['name'])

        resp, body = self.client.get_list_obj('cron_triggers')
        self.assertEqual(200, resp.status)

        trs_names = [tr['name'] for tr in body['cron_triggers']]
        self.assertIn(tr_name, trs_names)

        self.client.delete_obj('cron_triggers', tr_name)
        self.client.triggers.remove(tr_name)

        _, body = self.client.get_list_obj('cron_triggers')

        trs_names = [tr['name'] for tr in body['cron_triggers']]
        self.assertNotIn(tr_name, trs_names)

    @test.attr(type='sanity')
    def test_create_and_delete_oneshot_cron_triggers(self):
        tr_name = 'trigger'

        resp, body = self.client.create_cron_trigger(
            tr_name, self.wf_name, None, None, "4242-12-25 13:37")
        self.assertEqual(201, resp.status)
        self.assertEqual(tr_name, body['name'])
        self.assertEqual("4242-12-25 13:37:00", body['next_execution_time'])

        resp, body = self.client.get_list_obj('cron_triggers')
        self.assertEqual(200, resp.status)

        trs_names = [tr['name'] for tr in body['cron_triggers']]
        self.assertIn(tr_name, trs_names)

        self.client.delete_obj('cron_triggers', tr_name)
        self.client.triggers.remove(tr_name)

        _, body = self.client.get_list_obj('cron_triggers')

        trs_names = [tr['name'] for tr in body['cron_triggers']]
        self.assertNotIn(tr_name, trs_names)

    @test.attr(type='sanity')
    def test_create_two_cron_triggers_for_one_wf(self):
        tr_name_1 = 'trigger1'
        tr_name_2 = 'trigger2'

        resp, body = self.client.create_cron_trigger(
            tr_name_1, self.wf_name, None, '5 * * * *')
        self.assertEqual(201, resp.status)
        self.assertEqual(tr_name_1, body['name'])

        resp, body = self.client.create_cron_trigger(
            tr_name_2, self.wf_name, None, '15 * * * *')
        self.assertEqual(201, resp.status)
        self.assertEqual(tr_name_2, body['name'])

        resp, body = self.client.get_list_obj('cron_triggers')
        self.assertEqual(200, resp.status)

        trs_names = [tr['name'] for tr in body['cron_triggers']]
        self.assertIn(tr_name_1, trs_names)
        self.assertIn(tr_name_2, trs_names)

    @test.attr(type='sanity')
    def test_get_cron_trigger(self):
        tr_name = 'trigger'
        self.client.create_cron_trigger(
            tr_name, self.wf_name, None, '5 * * * *')

        resp, body = self.client.get_object('cron_triggers', tr_name)

        self.assertEqual(200, resp.status)
        self.assertEqual(tr_name, body['name'])

    @test.attr(type='negative')
    def test_create_cron_trigger_nonexistent_wf(self):
        self.assertRaises(exceptions.NotFound,
                          self.client.create_cron_trigger,
                          'trigger', 'nonexist', None, '5 * * * *')

    @test.attr(type='negative')
    def test_create_cron_trigger_invalid_count(self):
        self.assertRaises(exceptions.BadRequest,
                          self.client.create_cron_trigger,
                          'trigger', 'nonexist', None, '5 * * * *', None, "q")

    @test.attr(type='negative')
    def test_create_cron_trigger_negative_count(self):
        self.assertRaises(exceptions.BadRequest,
                          self.client.create_cron_trigger,
                          'trigger', 'nonexist', None, '5 * * * *', None, -1)

    @test.attr(type='negative')
    def test_create_cron_trigger_invalid_first_date(self):
        self.assertRaises(exceptions.BadRequest,
                          self.client.create_cron_trigger,
                          'trigger', 'nonexist', None, '5 * * * *', "q")

    @test.attr(type='negative')
    def test_create_cron_trigger_count_only(self):
        self.assertRaises(exceptions.BadRequest,
                          self.client.create_cron_trigger,
                          'trigger', 'nonexist', None, None, None, "42")

    @test.attr(type='negative')
    def test_create_cron_trigger_date_and_count_without_pattern(self):
        self.assertRaises(exceptions.BadRequest,
                          self.client.create_cron_trigger,
                          'trigger', 'nonexist', None, None,
                          "4242-12-25 13:37", "42")

    @test.attr(type='negative')
    def test_get_nonexistent_cron_trigger(self):
        self.assertRaises(exceptions.NotFound,
                          self.client.get_object,
                          'cron_triggers', 'trigger')

    @test.attr(type='negative')
    def test_delete_nonexistent_trigger(self):
        self.assertRaises(exceptions.NotFound,
                          self.client.delete_obj,
                          'cron_triggers', 'trigger')

    @test.attr(type='negative')
    def test_create_two_cron_triggers_with_same_name(self):
        tr_name = 'trigger'
        self.client.create_cron_trigger(
            tr_name, self.wf_name, None, '5 * * * *')
        self.assertRaises(exceptions.Conflict,
                          self.client.create_cron_trigger,
                          tr_name, self.wf_name, None, '5 * * * *')

    @test.attr(type='negative')
    def test_create_two_cron_triggers_with_same_pattern(self):
        self.client.create_cron_trigger(
            'trigger1',
            self.wf_name,
            None,
            '5 * * * *',
            "4242-12-25 13:37",
            "42"
        )
        self.assertRaises(
            exceptions.Conflict,
            self.client.create_cron_trigger,
            'trigger2',
            self.wf_name,
            None,
            '5 * * * *',
            "4242-12-25 13:37",
            "42"
        )

    @test.attr(type='negative')
    def test_invalid_cron_pattern_not_enough_params(self):
        self.assertRaises(exceptions.BadRequest,
                          self.client.create_cron_trigger,
                          'trigger', self.wf_name, None, '5 *')

    @test.attr(type='negative')
    def test_invalid_cron_pattern_out_of_range(self):
        self.assertRaises(exceptions.BadRequest,
                          self.client.create_cron_trigger,
                          'trigger', self.wf_name, None, '88 * * * *')
