# Copyright 2018 - Nokia Networks.
#
# Licensed under the Apache License, Version 2.0 (the "License");
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

from mistral.rpc import base as rpc
from mistral.service import base as service_base


LOG = logging.getLogger(__name__)

CONF = cfg.CONF


class SchedulerServer(service_base.MistralService):
    """Scheduler server.

    Manages scheduler life-cycle and gets registered as an RPC
    endpoint to process scheduler specific calls.
    """

    def __init__(self, scheduler, setup_profiler=True):
        super(SchedulerServer, self).__init__(
            'scheduler_group',
            setup_profiler
        )

        self.scheduler = scheduler
        self._rpc_server = None

    def start(self):
        super(SchedulerServer, self).start()

        self._rpc_server = rpc.get_rpc_server_driver()(cfg.CONF.engine)
        self._rpc_server.register_endpoint(self)

        self._rpc_server.run()

        self._notify_started('Scheduler server started.')

    def stop(self, graceful=False):
        super(SchedulerServer, self).stop()

        if self._rpc_server:
            self._rpc_server.stop(graceful)

    def schedule(self, rpc_ctx, job):
        """Receives requests over RPC to schedule delayed calls.

        :param rpc_ctx: RPC request context.
        :param job: Scheduler job.
        """
        LOG.info("Received RPC request 'schedule'[job=%s]", job)

        return self.scheduler.schedule(job, allow_redistribute=False)
