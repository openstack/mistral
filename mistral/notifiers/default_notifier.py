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

import copy

from oslo_log import log as logging

from mistral.notifiers import base


LOG = logging.getLogger(__name__)


class DefaultNotifier(base.Notifier):
    """Local notifier that process notification request."""

    def notify(self, ex_id, data, event, timestamp, publishers):
        for entry in publishers:
            params = copy.deepcopy(entry)
            publisher_name = params.pop('type', None)

            if not publisher_name:
                LOG.error('Notification publisher type is not specified.')
                continue

            try:
                publisher = base.get_notification_publisher(publisher_name)
                publisher.publish(ex_id, data, event, timestamp, **params)
            except Exception:
                LOG.exception(
                    'Unable to process event for publisher "%s".',
                    publisher_name
                )
