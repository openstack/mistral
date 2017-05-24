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

from mistral import config as cfg
from mistral.notifiers import default_notifier as notif
from mistral.rpc import base as rpc
from mistral.service import base as service_base
from mistral import utils
from mistral.utils import profiler as profiler_utils

LOG = logging.getLogger(__name__)


class NotificationServer(service_base.MistralService):

    def __init__(self, notifier, setup_profiler=True):
        super(NotificationServer, self).__init__(
            'notifier_group',
            setup_profiler
        )

        self.notifier = notifier
        self._rpc_server = None

    def start(self):
        super(NotificationServer, self).start()

        if self._setup_profiler:
            profiler_utils.setup('mistral-notifier', cfg.CONF.notifier.host)

        # Initialize and start RPC server.

        self._rpc_server = rpc.get_rpc_server_driver()(cfg.CONF.notifier)
        self._rpc_server.register_endpoint(self)

        self._rpc_server.run(executor='threading')

        self._notify_started('Notification server started.')

    def stop(self, graceful=False):
        super(NotificationServer, self).stop(graceful)

        if self._rpc_server:
            self._rpc_server.stop(graceful)

    def notify(self, rpc_ctx, ex_id, data, event, timestamp, publishers):
        """Receives calls over RPC to notify on notification server.

        :param rpc_ctx: RPC request context dictionary.
        :param ex_id: Workflow, task, or action execution id.
        :param data: Dictionary to include in the notification message.
        :param event: Event being notified on.
        :param timestamp: Datetime when this event occurred.
        :param publishers: The list of publishers to send the notification.
        """

        LOG.info(
            "Received RPC request 'notify'[ex_id=%s, event=%s, "
            "timestamp=%s, data=%s, publishers=%s]",
            ex_id,
            event,
            timestamp,
            data,
            utils.cut(publishers)
        )

        self.notifier.notify(
            ex_id,
            data,
            event,
            timestamp,
            publishers
        )


def get_oslo_service(setup_profiler=True):
    return NotificationServer(
        notif.DefaultNotifier(),
        setup_profiler=setup_profiler
    )
