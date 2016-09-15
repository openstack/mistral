# Copyright 2016 Catalyst IT Limited
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

from tempest.lib import exceptions
from tempest import test

from mistral_tempest_tests.tests import base

EXCHANGE = 'openstack'
EVENT_ENGINE_TOPIC = 'mistral_event_engine'
EVENT = 'fake.event'


class EventTriggerTestsV2(base.TestCase):
    """Test class for event engine function.

    NOTE: This test class doesn't fully test event engine functions, because
    we can not send real notifications to the internal message queue to
    trigger the specified workflows.

    So, before notification is supported in Mistral, we can only test the API
    functions.
    """

    _service = 'workflowv2'

    def setUp(self):
        super(EventTriggerTestsV2, self).setUp()
        _, body = self.client.create_workflow('wf_v2.yaml')
        self.wf_id = body['workflows'][0]['id']

    def tearDown(self):
        for tr in self.client.event_triggers:
            self.client.delete_obj('event_triggers', tr)
        self.client.event_triggers = []

        for wf in self.client.workflows:
            self.client.delete_obj('workflows', wf)
        self.client.workflows = []

        super(EventTriggerTestsV2, self).tearDown()

    @test.attr(type='sanity')
    def test_create_get_delete_event_trigger(self):
        name = 'my_event_trigger'

        resp, body = self.client.create_event_trigger(
            self.wf_id, EXCHANGE, EVENT_ENGINE_TOPIC, EVENT, name)

        trigger_id = body['id']

        self.assertEqual(201, resp.status)
        self.assertEqual(name, body['name'])

        resp, body = self.client.get_list_obj('event_triggers')
        self.assertEqual(200, resp.status)

        trs_names = [tr['name'] for tr in body['event_triggers']]
        self.assertIn(name, trs_names)

        self.client.delete_obj('event_triggers', trigger_id)
        self.client.event_triggers.remove(trigger_id)

        _, body = self.client.get_list_obj('event_triggers')

        trs_names = [tr['name'] for tr in body['event_triggers']]
        self.assertNotIn(name, trs_names)

    @test.attr(type='negative')
    def test_create_event_trigger_without_necessary_param(self):
        self.assertRaises(exceptions.BadRequest,
                          self.client.create_event_trigger,
                          self.wf_id, EXCHANGE, EVENT_ENGINE_TOPIC, '')

    @test.attr(type='negative')
    def test_create_event_trigger_with_nonexist_wf(self):
        self.assertRaises(exceptions.BadRequest,
                          self.client.create_event_trigger,
                          'nonexist', EXCHANGE, EVENT_ENGINE_TOPIC, EVENT)

    @test.attr(type='negative')
    def test_create_event_trigger_duplicate(self):
        name = 'my_event_trigger'

        self.client.create_event_trigger(
            self.wf_id, EXCHANGE, EVENT_ENGINE_TOPIC, EVENT, name)

        self.assertRaises(exceptions.Conflict,
                          self.client.create_event_trigger,
                          self.wf_id, EXCHANGE, EVENT_ENGINE_TOPIC, EVENT)

    @test.attr(type='negative')
    def test_get_nonexistent_event_trigger(self):
        fake_id = '123e4567-e89b-12d3-a456-426655440000'

        self.assertRaises(exceptions.NotFound,
                          self.client.get_object,
                          'event_triggers', fake_id)
