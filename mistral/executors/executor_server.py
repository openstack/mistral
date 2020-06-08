# Copyright 2016 - Nokia Networks
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
from mistral.executors import default_executor as exe
from mistral.rpc import base as rpc
from mistral.service import base as service_base
from mistral.services import action_heartbeat_sender
from mistral.services import actions as action_service
from mistral.utils import profiler as profiler_utils


CONF = cfg.CONF
LOG = logging.getLogger(__name__)


class ExecutorServer(service_base.MistralService):
    """Executor server.

    This class manages executor life-cycle and gets registered as an RPC
    endpoint to process executor specific calls. It also registers a
    cluster member associated with this instance of executor.
    """

    def __init__(self, executor, setup_profiler=True):
        super(ExecutorServer, self).__init__('executor_group', setup_profiler)

        self.executor = executor
        self._rpc_server = None

    def start(self):
        super(ExecutorServer, self).start()

        action_heartbeat_sender.start()

        if self._setup_profiler:
            profiler_utils.setup('mistral-executor', cfg.CONF.executor.host)

        # Initialize action providers to make sure all action classes
        # are initially imported.
        action_service.get_system_action_provider()

        # Initialize and start RPC server.

        self._rpc_server = rpc.get_rpc_server_driver()(cfg.CONF.executor)
        self._rpc_server.register_endpoint(self)

        self._rpc_server.run(executor='threading')

        self._notify_started('Executor server started.')

    def stop(self, graceful=False):
        super(ExecutorServer, self).stop(graceful)

        action_heartbeat_sender.stop()

        if self._rpc_server:
            self._rpc_server.stop(graceful)

    def run_action(self, rpc_ctx, action, action_ex_id, safe_rerun, exec_ctx,
                   timeout):

        """Receives calls over RPC to run action on executor.

        :param rpc_ctx: RPC request context dictionary.
        :param action: Action.
        :param action_ex_id: Action execution id.
        :param safe_rerun: Tells if given action can be safely rerun.
        :param exec_ctx: A dict of values providing information about
            the current execution.
        :param timeout: a period of time in seconds after which execution of
            action will be interrupted
        :return: Action result.
        """
        LOG.debug(
            "Received RPC request 'run_action'"
            "[action=%s, action_ex_id=%s, timeout=%s]",
            action,
            action_ex_id,
            timeout
        )

        redelivered = rpc_ctx.redelivered or False

        res = self.executor.run_action(
            action,
            action_ex_id,
            safe_rerun,
            exec_ctx,
            redelivered,
            timeout=timeout
        )

        LOG.debug(
            "Sending action result to engine"
            " [action=%s, action_ex_id=%s]",
            action,
            action_ex_id
        )

        return res


def get_oslo_service(setup_profiler=True):
    return ExecutorServer(
        exe.DefaultExecutor(),
        setup_profiler=setup_profiler
    )
