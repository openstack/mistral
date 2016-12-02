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
from mistral.engine import default_executor
from mistral.engine.rpc_backend import rpc
from mistral.service import base as service_base
from mistral.utils import profiler as profiler_utils
from mistral.utils import rpc_utils

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

        if self._setup_profiler:
            profiler_utils.setup('mistral-executor', cfg.CONF.executor.host)

        # Initialize and start RPC server.

        self._rpc_server = rpc.get_rpc_server_driver()(
            rpc_utils.get_rpc_info_from_oslo(cfg.CONF.executor)
        )
        self._rpc_server.register_endpoint(self)

        self._rpc_server.run(executor='threading')

        self._notify_started('Executor server started.')

    def stop(self, graceful=False):
        super(ExecutorServer, self).stop(graceful)

        if self._rpc_server:
            self._rpc_server.stop(graceful)

    def run_action(self, rpc_ctx, action_ex_id, action_class_str,
                   attributes, params, safe_rerun):
        """Receives calls over RPC to run action on executor.

        :param rpc_ctx: RPC request context dictionary.
        :param action_ex_id: Action execution id.
        :param action_class_str: Action class name.
        :param attributes: Action class attributes.
        :param params: Action input parameters.
        :param safe_rerun: Tells if given action can be safely rerun.
        :return: Action result.
        """

        LOG.info(
            "Received RPC request 'run_action'[rpc_ctx=%s,"
            " action_ex_id=%s, action_class=%s, attributes=%s, params=%s]"
            % (rpc_ctx, action_ex_id, action_class_str, attributes, params)
        )

        redelivered = rpc_ctx.redelivered or False

        return self.executor.run_action(
            action_ex_id,
            action_class_str,
            attributes,
            params,
            safe_rerun,
            redelivered
        )


def get_oslo_service(setup_profiler=True):
    return ExecutorServer(
        default_executor.DefaultExecutor(),
        setup_profiler=setup_profiler
    )
