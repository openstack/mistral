# Copyright 2026 - OVHcloud.
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

from oslo_config import cfg
from oslo_log import log as logging

from mistral.service import base as service_base
from mistral.services import periodic

LOG = logging.getLogger(__name__)

CONF = cfg.CONF


class PeriodicServer(service_base.MistralService):
    """Periodic tasks server.

    Runs the cron trigger processing loop as a standalone Mistral
    component instead of inside the API workers, where every worker
    would run its own competing processing loop.
    """

    def __init__(self):
        super(PeriodicServer, self).__init__()

        self._periodic_tg = None

    def start(self):
        super(PeriodicServer, self).start()

        if CONF.cron_trigger.enabled:
            self._periodic_tg = periodic.setup()
        else:
            LOG.warning(
                "Cron triggers are disabled ([cron_trigger] enabled = "
                "False), the periodic server will not process anything."
            )

        self._notify_started('Periodic server started.')

    def stop(self, graceful=False):
        super(PeriodicServer, self).stop(graceful)

        # This also clears the module-level registry in
        # mistral.services.periodic so a restart doesn't leak
        # stopped thread groups.
        periodic.stop_all_periodic_tasks()

        self._periodic_tg = None


def get_oslo_service():
    return PeriodicServer()
