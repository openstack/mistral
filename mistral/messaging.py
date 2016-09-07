# Copyright 2016 - IBM Corp.
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
"""
This module contains common structures and functions that help to handle
AMQP messages based on olso.messaging framework.
"""

import abc
import socket

from oslo_log import log as logging
import oslo_messaging
from oslo_messaging.notify import dispatcher
from oslo_messaging.notify import listener
from oslo_messaging import target
from oslo_messaging import transport
from oslo_utils import timeutils
import six

LOG = logging.getLogger(__name__)


def handle_event(self, ctxt, publisher_id, event_type, payload, metadata):
    """Callback function of each priority of notification messages.

    The function is used to construct endpoint class dynamically when starting
    listener in event engine service.

    After the class is created, 'self' param will make sense.

    :param ctxt: the notification context dict
    :param publisher_id: always describes where notification is sent from, for
                         example: 'compute.host1'
    :param event_type: describes the event, for example:
                       'compute.create_instance'
    :param payload: the notification payload
    :param metadata: the notification metadata, is always a mapping containing
                     a unique message_id and a timestamp.
    """
    LOG.debug('Received notification. publisher_id: %s, event_type: %s, '
              'payload: %s, metadata: %s.', publisher_id, event_type, payload,
              metadata)

    notification = {
        'event_type': event_type,
        'payload': payload,
        'publisher': publisher_id,
        'timestamp': metadata.get('timestamp',
                                  ctxt.get('timestamp', timeutils.utcnow())),
        'context': ctxt
    }

    self.event_engine.process_notification_event(notification)

    return dispatcher.NotificationResult.HANDLED


@six.add_metaclass(abc.ABCMeta)
class NotificationEndpoint(object):
    """Message listener endpoint.

    Only handle notifications that match the NotificationFilter rule set into
    the filter_rule attribute of the endpoint.
    """
    event_types = []

    def __init__(self, event_engine):
        self.event_engine = event_engine

        self.filter_rule = oslo_messaging.NotificationFilter(
            event_type='|'.join(self.event_types))


def get_pool_name(exchange):
    """Get pool name.

    Get the pool name for the listener, it will be formatted as
    'mistral-exchange-hostname'

    :param exchange: exchange name
    """
    pool_name = 'mistral-%s-%s' % (exchange, socket.gethostname())

    LOG.debug("Listener pool name is %s", pool_name)

    return pool_name


def start_listener(conf, exchange, topic, endpoints):
    """Starts up a notification listener."""
    trans = transport.get_transport(conf)
    targets = [target.Target(exchange=exchange, topic=topic)]
    pool_name = get_pool_name(exchange)

    notification_listener = listener.get_notification_listener(
        trans,
        targets,
        endpoints,
        executor='threading',
        allow_requeue=False,
        pool=pool_name
    )
    notification_listener.start()

    return notification_listener
