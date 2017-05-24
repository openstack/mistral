# Copyright 2018 - Extreme Networks, Inc.
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

import abc
import six

from oslo_log import log as logging
from stevedore import driver


LOG = logging.getLogger(__name__)

_NOTIFIERS = {}
_NOTIFICATION_PUBLISHERS = {}


def cleanup():
    global _NOTIFIERS
    global _NOTIFICATION_PUBLISHERS

    _NOTIFIERS = {}
    _NOTIFICATION_PUBLISHERS = {}


def get_notifier(notifier_name):
    global _NOTIFIERS

    if not _NOTIFIERS.get(notifier_name):
        mgr = driver.DriverManager(
            'mistral.notifiers',
            notifier_name,
            invoke_on_load=True
        )

        _NOTIFIERS[notifier_name] = mgr.driver

    return _NOTIFIERS[notifier_name]


def get_notification_publisher(publisher_name):
    global _NOTIFICATION_PUBLISHERS

    if not _NOTIFICATION_PUBLISHERS.get(publisher_name):
        mgr = driver.DriverManager(
            'mistral.notification.publishers',
            publisher_name,
            invoke_on_load=True
        )

        _NOTIFICATION_PUBLISHERS[publisher_name] = mgr.driver

    return _NOTIFICATION_PUBLISHERS[publisher_name]


@six.add_metaclass(abc.ABCMeta)
class Notifier(object):
    """Notifier interface."""

    @abc.abstractmethod
    def notify(self, ex_id, data, event, timestamp, **kwargs):
        raise NotImplementedError()


@six.add_metaclass(abc.ABCMeta)
class NotificationPublisher(object):
    """Notifier plugin interface."""

    @abc.abstractmethod
    def publish(self, ex_id, data, event, timestamp, **kwargs):
        raise NotImplementedError()
