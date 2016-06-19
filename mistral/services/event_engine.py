# Copyright 2016 Catalyst IT Ltd
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from collections import defaultdict
import threading

from oslo_config import cfg
from oslo_log import log as logging
from oslo_service import threadgroup
import six

from mistral import context as auth_ctx
from mistral import coordination
from mistral.db.v2 import api as db_api
from mistral import messaging as mistral_messaging
from mistral.services import security

LOG = logging.getLogger(__name__)
CONF = cfg.CONF

# Event queue event constants.
EVENT_CONTEXT = 'context'
EVENT_TYPE = 'type'
EVENT_PAYLOAD = 'payload'
EVENT_METADATA = 'metadata'


class EventEngine(coordination.Service):
    """Event engine server.

    A separate service that is responsible for listening event notification
    and trigger workflows defined by end user.
    """
    def __init__(self, engine_client):
        coordination.Service.__init__(self, 'event_engine_group')

        self.engine_client = engine_client
        self.event_queue = six.moves.queue.Queue()
        self.handler_tg = threadgroup.ThreadGroup()

        self.event_triggers_map = defaultdict(list)
        self.exchange_topic_events_map = defaultdict(set)
        self.exchange_topic_listener_map = {}

        self.lock = threading.Lock()

        self._start_handler()
        self._start_listeners()

    def _get_endpoint_cls(self, events):
        """Create a messaging endpoint class.

        The endpoint implements the method named like the priority, and only
        handle the notification match the NotificationFilter rule set into the
        filter_rule attribute of the endpoint.
        """
        # Handle each priority of notification messages.
        event_priorities = ['audit', 'critical', 'debug', 'error', 'info']
        attrs = dict.fromkeys(
            event_priorities,
            mistral_messaging.handle_event
        )
        attrs['event_types'] = events

        endpoint_cls = type(
            'MistralNotificationEndpoint',
            (mistral_messaging.NotificationEndpoint,),
            attrs,
        )

        return endpoint_cls

    def _add_event_listener(self, exchange, topic, events):
        """Add or update event listener for specified exchange, topic.

        Create a new event listener for the event trigger if no existing
        listener relates to (exchange, topic).

        Or, restart existing event listener with updated events.
        """
        key = (exchange, topic)

        if key in self.exchange_topic_listener_map:
            listener = self.exchange_topic_listener_map[key]
            listener.stop()
            listener.wait()

        endpoint = self._get_endpoint_cls(events)(self)

        LOG.debug("Starting to listen to AMQP. exchange: %s, topic: %s",
                  exchange, topic)

        listener = mistral_messaging.start_listener(
            CONF,
            exchange,
            topic,
            [endpoint]
        )

        self.exchange_topic_listener_map[key] = listener

    def stop_all_listeners(self):
        for listener in six.itervalues(self.exchange_topic_listener_map):
            listener.stop()
            listener.wait()

    def _start_listeners(self):
        triggers = db_api.get_event_triggers(insecure=True)

        LOG.info('Find %s event triggers.', len(triggers))

        for trigger in triggers:
            exchange_topic = (trigger.exchange, trigger.topic)
            self.exchange_topic_events_map[exchange_topic].add(trigger.event)

            trigger_info = trigger.to_dict()
            self.event_triggers_map[trigger.event].append(trigger_info)

        for (ex_t, events) in six.iteritems(self.exchange_topic_events_map):
            exchange, topic = ex_t
            self._add_event_listener(exchange, topic, events)

    def _start_workflow(self, triggers, payload, metadata):
        """Start workflows defined in event triggers."""
        for t in triggers:
            LOG.info('Start to process event trigger: %s', t['id'])

            workflow_params = t.get('workflow_params', {})
            workflow_params.update(
                {'event_payload': payload, 'event_metadata': metadata}
            )

            # Setup context before schedule triggers.
            ctx = security.create_context(t['trust_id'], t['project_id'])
            auth_ctx.set_ctx(ctx)

            try:
                self.engine_client.start_workflow(
                    t['workflow_id'],
                    t['workflow_input'],
                    description="Workflow execution created by event "
                                "trigger %s." % t['id'],
                    **workflow_params
                )
            except Exception as e:
                LOG.exception("Failed to process event trigger %s, "
                              "error: %s", t['id'], str(e))
            finally:
                auth_ctx.set_ctx(None)

    def _process_event_queue(self, *args, **kwargs):
        """Process notification events.

        This function is called in a thread.
        """
        while True:
            event = self.event_queue.get()

            context = event.get(EVENT_CONTEXT)
            event_type = event.get(EVENT_TYPE)
            payload = event.get(EVENT_PAYLOAD)
            metadata = event.get(EVENT_METADATA)

            # NOTE(kong): Use lock here to protect event_triggers_map variable
            # from being updated outside the thread.
            with self.lock:
                if event_type in self.event_triggers_map:
                    triggers = self.event_triggers_map[event_type]

                    # There may be more projects registered the same event.
                    project_ids = [t['project_id'] for t in triggers]

                    # Skip the event doesn't belong to any event trigger owner.
                    if (CONF.pecan.auth_enable and
                            context.get('project_id', '') not in project_ids):
                        self.event_queue.task_done()
                        continue

                    LOG.debug('Start to handle event: %s, %d trigger(s) '
                              'registered.', event_type, len(triggers))

                    self._start_workflow(triggers, payload, metadata)

            self.event_queue.task_done()

    def _start_handler(self):
        """Starts event queue handler in a thread group."""
        LOG.info('Starting event notification task...')

        self.handler_tg.add_thread(self._process_event_queue)

    def process_notification_event(self, context, event_type, payload,
                                   metadata):
        """Callback funtion by event handler.

        Just put notification into a queue.
        """
        event = {
            EVENT_CONTEXT: context,
            EVENT_TYPE: event_type,
            EVENT_PAYLOAD: payload,
            EVENT_METADATA: metadata
        }

        LOG.debug("Adding notification event to event queue: %s", event)

        self.event_queue.put(event)

    def create_event_trigger(self, trigger, events):
        """An endpoint method for creating event trigger.

        When creating an event trigger in API layer, we need to create a new
        listener or update an existing listener.

        :param trigger: a dict containing event trigger information.
        :param events: a list of events binding to the (exchange, topic) of
                       the event trigger.
        """
        with self.lock:
            ids = [t['id'] for t in self.event_triggers_map[trigger['event']]]

            if trigger['id'] not in ids:
                self.event_triggers_map[trigger['event']].append(trigger)

        self._add_event_listener(trigger['exchange'], trigger['topic'], events)

    def update_event_trigger(self, trigger):
        """An endpoint method for updating event trigger.

        Because only workflow related information is allowed to be updated, we
        only need to update event_triggers_map(in a synchronous way).

        :param trigger: a dict containing event trigger information.
        """
        assert trigger['event'] in self.event_triggers_map

        with self.lock:
            for t in self.event_triggers_map[trigger['event']]:
                if trigger['id'] == t['id']:
                    t.update(trigger)

    def delete_event_trigger(self, trigger, events):
        """An endpoint method for deleting event trigger.

        If there is no event binding to (exchange, topic) after deletion, we
        need to delete the related listener. Otherwise, we need to restart
        that listener.

        :param trigger: a dict containing event trigger information.
        :param events: a list of events binding to the (exchange, topic) of
                       the event trigger.
        """
        assert trigger['event'] in self.event_triggers_map

        with self.lock:
            for t in self.event_triggers_map[trigger['event']]:
                if t['id'] == trigger['id']:
                    self.event_triggers_map[trigger['event']].remove(t)
                    break

            if not self.event_triggers_map[trigger['event']]:
                del self.event_triggers_map[trigger['event']]

        if not events:
            key = (trigger['exchange'], trigger['topic'])

            listener = self.exchange_topic_listener_map[key]
            listener.stop()
            listener.wait()

            del self.exchange_topic_listener_map[key]

            LOG.info(
                'Deleted listener for exchange: %s, topic: %s',
                trigger['exchange'],
                trigger['topic']
            )

            return

        self._add_event_listener(trigger['exchange'], trigger['topic'], events)
