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
from tempest.lib import decorators
from tempest.lib import exceptions

from mistral_tempest_tests.tests import base


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

    @decorators.attr(type='smoke')
    @decorators.idempotent_id('c53b44dd-59b3-4a4b-b22a-21abb4cecea0')
    def test_get_list_cron_triggers(self):
        resp, body = self.client.get_list_obj('cron_triggers')

        self.assertEqual(200, resp.status)
        self.assertEmpty(body['cron_triggers'])

    @decorators.attr(type='sanity')
    @decorators.idempotent_id('fbc641fa-8704-45b3-b259-136eb956394c')
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

    @decorators.attr(type='sanity')
    @decorators.idempotent_id('b8b9102e-b323-492f-af41-4f5368971e36')
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

    @decorators.attr(type='sanity')
    @decorators.idempotent_id('5224359b-3c31-4fe7-a4eb-dc9da843137e')
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

    @decorators.attr(type='sanity')
    @decorators.idempotent_id('967da6e3-f9a2-430a-9390-0d73f2143aba')
    def test_get_cron_trigger(self):
        tr_name = 'trigger'
        self.client.create_cron_trigger(
            tr_name, self.wf_name, None, '5 * * * *')

        resp, body = self.client.get_object('cron_triggers', tr_name)

        self.assertEqual(200, resp.status)
        self.assertEqual(tr_name, body['name'])

    @decorators.attr(type='negative')
    @decorators.idempotent_id('d0e4d894-9a50-4919-a008-a9f255b6b6a3')
    def test_create_cron_trigger_nonexistent_wf(self):
        self.assertRaises(exceptions.NotFound,
                          self.client.create_cron_trigger,
                          'trigger', 'nonexist', None, '5 * * * *')

    @decorators.attr(type='negative')
    @decorators.idempotent_id('83f0d420-fd3c-4e75-87b1-854cefb28bda')
    def test_create_cron_trigger_invalid_count(self):
        self.assertRaises(exceptions.BadRequest,
                          self.client.create_cron_trigger,
                          'trigger', 'nonexist', None, '5 * * * *', None, "q")

    @decorators.attr(type='negative')
    @decorators.idempotent_id('4190e0af-3c64-4f57-a0b8-d9d3d41fd323')
    def test_create_cron_trigger_negative_count(self):
        self.assertRaises(exceptions.BadRequest,
                          self.client.create_cron_trigger,
                          'trigger', 'nonexist', None, '5 * * * *', None, -1)

    @decorators.attr(type='negative')
    @decorators.idempotent_id('210c37e8-990e-4260-b3b3-93f254e6a4d7')
    def test_create_cron_trigger_invalid_first_date(self):
        self.assertRaises(exceptions.BadRequest,
                          self.client.create_cron_trigger,
                          'trigger', 'nonexist', None, '5 * * * *', "q")

    @decorators.attr(type='negative')
    @decorators.idempotent_id('17990a39-8f66-4748-8ba5-ca87befbb198')
    def test_create_cron_trigger_count_only(self):
        self.assertRaises(exceptions.BadRequest,
                          self.client.create_cron_trigger,
                          'trigger', 'nonexist', None, None, None, "42")

    @decorators.attr(type='negative')
    @decorators.idempotent_id('029e0a1e-2252-4a37-b9bd-cfbe407c6ade')
    def test_create_cron_trigger_date_and_count_without_pattern(self):
        self.assertRaises(exceptions.BadRequest,
                          self.client.create_cron_trigger,
                          'trigger', 'nonexist', None, None,
                          "4242-12-25 13:37", "42")

    @decorators.attr(type='negative')
    @decorators.idempotent_id('54650d60-ec17-44b7-8732-2183852789ae')
    def test_get_nonexistent_cron_trigger(self):
        self.assertRaises(exceptions.NotFound,
                          self.client.get_object,
                          'cron_triggers', 'trigger')

    @decorators.attr(type='negative')
    @decorators.idempotent_id('c663599e-5cd7-49ff-9c0f-f82a5bcc5fdb')
    def test_delete_nonexistent_trigger(self):
        self.assertRaises(exceptions.NotFound,
                          self.client.delete_obj,
                          'cron_triggers', 'trigger')

    @decorators.attr(type='negative')
    @decorators.idempotent_id('d1328d2b-5dc2-4521-93ec-d734d5fb4df7')
    def test_create_two_cron_triggers_with_same_name(self):
        tr_name = 'trigger'
        self.client.create_cron_trigger(
            tr_name, self.wf_name, None, '5 * * * *')
        self.assertRaises(exceptions.Conflict,
                          self.client.create_cron_trigger,
                          tr_name, self.wf_name, None, '5 * * * *')

    @decorators.attr(type='negative')
    @decorators.idempotent_id('3e51fc44-ce38-4653-9e4e-08b077a1dbc5')
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

    @decorators.attr(type='negative')
    @decorators.idempotent_id('6f3c08f3-9498-410e-a44b-4f9c6c971405')
    def test_invalid_cron_pattern_not_enough_params(self):
        self.assertRaises(exceptions.BadRequest,
                          self.client.create_cron_trigger,
                          'trigger', self.wf_name, None, '5 *')

    @decorators.attr(type='negative')
    @decorators.idempotent_id('26cb52e7-1ef3-45a2-a870-1baec2382c55')
    def test_invalid_cron_pattern_out_of_range(self):
        self.assertRaises(exceptions.BadRequest,
                          self.client.create_cron_trigger,
                          'trigger', self.wf_name, None, '88 * * * *')
