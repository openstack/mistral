# Copyright 2016 Catalyst IT Ltd
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

import time

import mock
from oslo_config import cfg

from mistral.db.v2.sqlalchemy import api as db_api
from mistral.services import event_engine
from mistral.services import workflows
from mistral.tests.unit import base

WORKFLOW_LIST = """
---
version: '2.0'

my_wf:
  type: direct

  tasks:
    task1:
      action: std.echo output='Hi!'
"""

EXCHANGE_TOPIC = ('openstack', 'notification')
EVENT_TYPE = 'compute.instance.create.start'

EVENT_TRIGGER = {
    'name': 'trigger1',
    'workflow_id': '',
    'workflow_input': {},
    'workflow_params': {},
    'exchange': 'openstack',
    'topic': 'notification',
    'event': EVENT_TYPE,
}

cfg.CONF.set_default('auth_enable', False, group='pecan')


class EventEngineTest(base.DbTestCase):
    def setUp(self):
        super(EventEngineTest, self).setUp()

        self.wf = workflows.create_workflows(WORKFLOW_LIST)[0]
        EVENT_TRIGGER['workflow_id'] = self.wf.id

    def test_event_engine_start_with_no_triggers(self):
        e_engine = event_engine.EventEngine(mock.Mock())
        self.addCleanup(e_engine.handler_tg.stop)

        self.assertEqual(0, len(e_engine.event_triggers_map))
        self.assertEqual(0, len(e_engine.exchange_topic_events_map))
        self.assertEqual(0, len(e_engine.exchange_topic_listener_map))

    @mock.patch('mistral.messaging.start_listener')
    def test_event_engine_start_with_triggers(self, mock_start):
        trigger = db_api.create_event_trigger(EVENT_TRIGGER)

        e_engine = event_engine.EventEngine(mock.MagicMock())
        self.addCleanup(e_engine.handler_tg.stop)

        self.assertEqual(1, len(e_engine.exchange_topic_events_map))
        self.assertEqual(
            EVENT_TYPE,
            list(e_engine.exchange_topic_events_map[EXCHANGE_TOPIC])[0]
        )
        self.assertEqual(1, len(e_engine.event_triggers_map))
        self.assertEqual(1, len(e_engine.event_triggers_map[EVENT_TYPE]))
        self._assert_dict_contains_subset(
            trigger.to_dict(),
            e_engine.event_triggers_map[EVENT_TYPE][0]
        )
        self.assertEqual(1, len(e_engine.exchange_topic_listener_map))

    @mock.patch('mistral.messaging.start_listener')
    def test_process_event_queue(self, mock_start):
        db_api.create_event_trigger(EVENT_TRIGGER)

        client = mock.MagicMock()
        e_engine = event_engine.EventEngine(client)
        self.addCleanup(e_engine.handler_tg.stop)

        event = {
            'event_type': EVENT_TYPE,
            'payload': {},
            'publisher': 'fake_publisher',
            'timestamp': '',
            'context': {'project_id': 'fake_project', 'user_id': 'fake_user'},
        }

        with mock.patch.object(e_engine, 'engine_client') as client_mock:
            e_engine.event_queue.put(event)
            time.sleep(1)

            self.assertEqual(1, client_mock.start_workflow.call_count)

            args, kwargs = client_mock.start_workflow.call_args

            self.assertEqual((EVENT_TRIGGER['workflow_id'], {}), args)
            self.assertDictEqual(
                {
                    'service': 'fake_publisher',
                    'project_id': 'fake_project',
                    'user_id': 'fake_user',
                    'timestamp': ''
                },
                kwargs['event_params']
            )


class NotificationsConverterTest(base.BaseTest):
    def test_convert(self):
        definition_cfg = [
            {
                'event_types': EVENT_TYPE,
                'properties': {'resource_id': '<% $.payload.instance_id %>'}
            }
        ]

        converter = event_engine.NotificationsConverter()
        converter.definitions = [event_engine.EventDefinition(event_def)
                                 for event_def in reversed(definition_cfg)]

        notification = {
            'event_type': EVENT_TYPE,
            'payload': {'instance_id': '12345'},
            'publisher': 'fake_publisher',
            'timestamp': '',
            'context': {'project_id': 'fake_project', 'user_id': 'fake_user'}
        }

        event = converter.convert(EVENT_TYPE, notification)

        self.assertDictEqual(
            {'resource_id': '12345'},
            event
        )

    def test_convert_event_type_not_defined(self):
        definition_cfg = [
            {
                'event_types': EVENT_TYPE,
                'properties': {'resource_id': '<% $.payload.instance_id %>'}
            }
        ]

        converter = event_engine.NotificationsConverter()
        converter.definitions = [event_engine.EventDefinition(event_def)
                                 for event_def in reversed(definition_cfg)]

        notification = {
            'event_type': 'fake_event',
            'payload': {'instance_id': '12345'},
            'publisher': 'fake_publisher',
            'timestamp': '',
            'context': {'project_id': 'fake_project', 'user_id': 'fake_user'}
        }

        event = converter.convert('fake_event', notification)

        self.assertDictEqual(
            {
                'service': 'fake_publisher',
                'project_id': 'fake_project',
                'user_id': 'fake_user',
                'timestamp': ''
            },
            event
        )
