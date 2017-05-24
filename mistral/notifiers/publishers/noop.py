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

from oslo_log import log as logging

from mistral.notifiers import base


LOG = logging.getLogger(__name__)


class NoopPublisher(base.NotificationPublisher):

    def publish(self, ex_id, data, event, timestamp, **kwargs):
        LOG.info(
            'The event %s for %s is published by the '
            'noop notification publisher.',
            event,
            ex_id
        )
