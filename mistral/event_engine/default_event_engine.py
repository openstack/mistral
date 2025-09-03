# Copyright 2016 Catalyst IT Ltd
# Copyright 2017 - Brocade Communications Systems, Inc.
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
import fnmatch
import json
import os
import queue
import threading

from oslo_config import cfg
from oslo_log import log as logging

from mistral import context as auth_ctx
from mistral.db.v2 import api as db_api
from mistral.event_engine import base
from mistral import exceptions
from mistral import expressions
from mistral import messaging as mistral_messaging
from mistral.rpc import clients as rpc
from mistral.services import security
from mistral.utils import safe_yaml


LOG = logging.getLogger(__name__)
CONF = cfg.CONF


DEFAULT_PROPERTIES = {
    'service': '<% $.publisher %>',
    'project_id': '<% $.context.project_id %>',
    'user_id': '<% $.context.user_id %>',
    'timestamp': '<% $.timestamp %>'
}


class EventDefinition(object):
    def __init__(self, definition_cfg):
        self.cfg = definition_cfg

        try:
            self.event_types = self.cfg['event_types']
            self.properties = self.cfg['properties']
        except KeyError as err:
            raise exceptions.MistralException(
                "Required field %s not specified" % err.args[0]
            )

        if isinstance(self.event_types, str):
            self.event_types = [self.event_types]

    def match_type(self, event_type):
        for t in self.event_types:
            if fnmatch.fnmatch(event_type, t):
                return True

        return False

    def convert(self, event):
        return expressions.evaluate_recursively(self.properties, event)


class NotificationsConverter(object):
    def __init__(self):
        config_file = CONF.event_engine.event_definitions_cfg_file
        definition_cfg = []

        if os.path.exists(config_file):
            with open(config_file) as cf:
                config = cf.read()

            try:
                definition_cfg = safe_yaml.load(config)
            except safe_yaml.YAMLError as err:
                if hasattr(err, 'problem_mark'):
                    mark = err.problem_mark
                    errmsg = (
                        "Invalid YAML syntax in Definitions file "
                        "%(file)s at line: %(line)s, column: %(column)s."
                        % dict(file=config_file,
                               line=mark.line + 1,
                               column=mark.column + 1)
                    )
                else:
                    errmsg = (
                        "YAML error reading Definitions file %s" %
                        CONF.event_engine.event_definitions_cfg_file
                    )

                LOG.error(errmsg)

                raise exceptions.MistralError(
                    'Invalid event definition configuration file. %s' %
                    config_file
                )

        self.definitions = [EventDefinition(event_def)
                            for event_def in reversed(definition_cfg)]

    def get_event_definition(self, event_type):
        for d in self.definitions:
            if d.match_type(event_type):
                return d

        return None

    def convert(self, event_type, event):
        edef = self.get_event_definition(event_type)

        if edef is None:
            LOG.debug('No event definition found for type: %s, use default '
                      'settings instead.', event_type)

            return expressions.evaluate_recursively(DEFAULT_PROPERTIES, event)

        return edef.convert(event)


class DefaultEventEngine(base.EventEngine):
    """Event engine server.

    A separate service that is responsible for listening event notification
    and triggering workflows defined by end user.
    """
    def __init__(self):
        self.engine_client = rpc.get_engine_client()
        self.event_queue = queue.Queue()

        self._stopped = False
        self._thread = threading.Thread(target=self._loop)
        self._thread.daemon = True

        self.event_triggers_map = defaultdict(list)
        self.exchange_topic_events_map = defaultdict(set)
        self.exchange_topic_listener_map = {}

        self.lock = threading.Lock()

        LOG.debug('Loading notification definitions.')
        self.notification_converter = NotificationsConverter()

    def start(self):
        LOG.info('Starting event notification engine...')
        self._thread.start()
        self._start_listeners()

    def stop(self):
        self._stopped = True
        self._thread.join()
        for listener in self.exchange_topic_listener_map.values():
            listener.stop()
            listener.wait()

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

    def _start_listeners(self):
        triggers = db_api.get_event_triggers(insecure=True)

        LOG.info('Found %s event triggers.', len(triggers))

        for trigger in triggers:
            exchange_topic = (trigger.exchange, trigger.topic)
            self.exchange_topic_events_map[exchange_topic].add(trigger.event)

            trigger_info = trigger.to_dict()
            trigger_info['workflow_namespace'] = trigger.workflow.namespace
            self.event_triggers_map[trigger.event].append(trigger_info)

        for (ex_t, events) in self.exchange_topic_events_map.items():
            exchange, topic = ex_t
            self._add_event_listener(exchange, topic, events)

    def _start_workflow(self, triggers, event_params):
        """Start workflows defined in event triggers."""
        for t in triggers:
            LOG.info('Start to process event trigger: %s', t['id'])

            workflow_params = t.get('workflow_params', {})
            workflow_params.update({'event_params': event_params})

            # Setup context before schedule triggers.
            ctx = security.create_context(t['trust_id'], t['project_id'])
            auth_ctx.set_ctx(ctx)

            description = {
                "description": (
                    "Workflow execution created by event"
                    " trigger '(%s)'." % t['id']
                ),
                "triggered_by": {
                    "type": "event_trigger",
                    "id": t['id'],
                    "name": t['name']
                }
            }

            try:
                self.engine_client.start_workflow(
                    t['workflow_id'],
                    t['workflow_namespace'],
                    None,
                    t['workflow_input'],
                    description=json.dumps(description),
                    **workflow_params
                )
            except Exception as e:
                LOG.exception("Failed to process event trigger %s, "
                              "error: %s", t['id'], str(e))
            finally:
                auth_ctx.set_ctx(None)

    def _loop(self, *args, **kwargs):
        """Process notification events.

        This function is called in a thread.
        """
        while not self._stopped:
            try:
                # Get from queue (nowait)
                # It may raise a queue.Empty if there is nothing in queue
                # but thanks to while loop we will continue getting until
                # the thread got stopped.
                event = self.event_queue.get_nowait()
                context = event.get('context')
                event_type = event.get('event_type')

                # NOTE(kong): Use lock here to protect event_triggers_map
                # variable from being updated outside the thread.
                with self.lock:
                    if event_type in self.event_triggers_map:
                        triggers = self.event_triggers_map[event_type]

                        # There may be more projects registered the same event.
                        project_ids = [t['project_id'] for t in triggers]

                        any_public = any(
                            [t['scope'] == 'public' for t in triggers]
                        )

                        # Skip the event doesn't belong to any event trigger
                        # owner.
                        if (not any_public and CONF.pecan.auth_enable and
                                context.get('project_id', '')
                                not in project_ids):
                            self.event_queue.task_done()
                            continue

                        # Need to choose what trigger(s) should be called
                        # exactly.
                        triggers_to_call = []
                        for t in triggers:
                            project_trigger = (
                                t['project_id'] == context.get('project_id')
                            )
                            public_trigger = t['scope'] == 'public'
                            if project_trigger or public_trigger:
                                triggers_to_call.append(t)

                        LOG.debug('Start to handle event: %s, %d trigger(s) '
                                  'registered.', event_type, len(triggers))

                        event_params = self.notification_converter.convert(
                            event_type,
                            event
                        )

                        self._start_workflow(triggers_to_call, event_params)
                self.event_queue.task_done()
            except queue.Empty:
                pass

    def process_notification_event(self, notification):
        """Callback function by event handler.

        Just put notification into a queue.
        """
        LOG.debug("Putting notification event to event queue.")

        self.event_queue.put(notification)

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
