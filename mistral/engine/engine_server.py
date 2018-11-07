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
from mistral.db.v2 import api as db_api
from mistral.engine import default_engine
from mistral.rpc import base as rpc
from mistral.service import base as service_base
from mistral.services import action_execution_checker
from mistral.services import expiration_policy
from mistral.services import scheduler
from mistral import utils
from mistral.utils import profiler as profiler_utils

LOG = logging.getLogger(__name__)


class EngineServer(service_base.MistralService):
    """Engine server.

    This class manages engine life-cycle and gets registered as an RPC
    endpoint to process engine specific calls. It also registers a
    cluster member associated with this instance of engine.
    """

    def __init__(self, engine, setup_profiler=True):
        super(EngineServer, self).__init__('engine_group', setup_profiler)

        self.engine = engine
        self._rpc_server = None
        self._scheduler = None
        self._expiration_policy_tg = None

    def start(self):
        super(EngineServer, self).start()

        db_api.setup_db()

        self._scheduler = scheduler.start()
        self._expiration_policy_tg = expiration_policy.setup()

        action_execution_checker.start()

        if self._setup_profiler:
            profiler_utils.setup('mistral-engine', cfg.CONF.engine.host)

        # Initialize and start RPC server.

        self._rpc_server = rpc.get_rpc_server_driver()(cfg.CONF.engine)
        self._rpc_server.register_endpoint(self)

        self._rpc_server.run(executor=cfg.CONF.oslo_rpc_executor)

        self._notify_started('Engine server started.')

    def stop(self, graceful=False):
        super(EngineServer, self).stop(graceful)

        action_execution_checker.stop(graceful)

        if self._scheduler:
            scheduler.stop_scheduler(self._scheduler, graceful)

        if self._expiration_policy_tg:
            self._expiration_policy_tg.stop(graceful)

        if self._rpc_server:
            self._rpc_server.stop(graceful)

    def start_workflow(self, rpc_ctx, wf_identifier, wf_namespace,
                       wf_ex_id, wf_input, description, params):
        """Receives calls over RPC to start workflows on engine.

        :param rpc_ctx: RPC request context.
        :param wf_identifier: Workflow definition identifier.
        :param wf_namespace: Workflow namespace.
        :param wf_input: Workflow input.
        :param wf_ex_id: Workflow execution id. If passed, it will be set
            in the new execution object.
        :param description: Workflow execution description.
        :param params: Additional workflow type specific parameters.
        :return: Workflow execution.
        """

        LOG.info(
            "Received RPC request 'start_workflow'[workflow_identifier=%s, "
            "workflow_input=%s, description=%s, params=%s]",
            wf_identifier,
            utils.cut(wf_input),
            description,
            params
        )

        return self.engine.start_workflow(
            wf_identifier,
            wf_namespace,
            wf_ex_id,
            wf_input,
            description,
            **params
        )

    def start_action(self, rpc_ctx, action_name,
                     action_input, description, params):
        """Receives calls over RPC to start actions on engine.

        :param rpc_ctx: RPC request context.
        :param action_name: name of the Action.
        :param action_input: input dictionary for Action.
        :param description: description of new Action execution.
        :param params: extra parameters to run Action.
        :return: Action execution.
        """
        LOG.info(
            "Received RPC request 'start_action'[name=%s, input=%s, "
            "description=%s, params=%s]",
            action_name,
            utils.cut(action_input),
            description,
            params
        )

        return self.engine.start_action(
            action_name,
            action_input,
            description,
            **params
        )

    def on_action_complete(self, rpc_ctx, action_ex_id, result, wf_action):
        """Receives RPC calls to communicate action result to engine.

        :param rpc_ctx: RPC request context.
        :param action_ex_id: Action execution id.
        :param result: Action result data.
        :param wf_action: True if given id points to a workflow execution.
        :return: Action execution.
        """
        LOG.info(
            "Received RPC request 'on_action_complete'[action_ex_id=%s, "
            "result=%s]",
            action_ex_id,
            result.cut_repr()
        )

        return self.engine.on_action_complete(action_ex_id, result, wf_action)

    def on_action_update(self, rpc_ctx, action_ex_id, state, wf_action):
        """Receives RPC calls to communicate action execution state to engine.

        :param rpc_ctx: RPC request context.
        :param action_ex_id: Action execution id.
        :param state: Action execution state.
        :param wf_action: True if given id points to a workflow execution.
        :return: Action execution.
        """
        LOG.info(
            "Received RPC request 'on_action_update'"
            "[action_ex_id=%s, state=%s]",
            action_ex_id,
            state
        )

        return self.engine.on_action_update(action_ex_id, state, wf_action)

    def pause_workflow(self, rpc_ctx, wf_ex_id):
        """Receives calls over RPC to pause workflows on engine.

        :param rpc_ctx: Request context.
        :param wf_ex_id: Workflow execution id.
        :return: Workflow execution.
        """
        LOG.info(
            "Received RPC request 'pause_workflow'[execution_id=%s]",
            wf_ex_id
        )

        return self.engine.pause_workflow(wf_ex_id)

    def rerun_workflow(self, rpc_ctx, task_ex_id, reset=True, env=None):
        """Receives calls over RPC to rerun workflows on engine.

        :param rpc_ctx: RPC request context.
        :param task_ex_id: Task execution id.
        :param reset: If true, then purge action execution for the task.
        :param env: Environment variables to update.
        :return: Workflow execution.
        """
        LOG.info(
            "Received RPC request 'rerun_workflow'[task_ex_id=%s]",
            task_ex_id
        )

        return self.engine.rerun_workflow(task_ex_id, reset, env)

    def resume_workflow(self, rpc_ctx, wf_ex_id, env=None):
        """Receives calls over RPC to resume workflows on engine.

        :param rpc_ctx: RPC request context.
        :param wf_ex_id: Workflow execution id.
        :param env: Environment variables to update.
        :return: Workflow execution.
        """
        LOG.info(
            "Received RPC request 'resume_workflow'[wf_ex_id=%s]",
            wf_ex_id
        )

        return self.engine.resume_workflow(wf_ex_id, env)

    def stop_workflow(self, rpc_ctx, wf_ex_id, state, message=None):
        """Receives calls over RPC to stop workflows on engine.

        Sets execution state to SUCCESS or ERROR. No more tasks will be
        scheduled. Running tasks won't be killed, but their results
        will be ignored.

        :param rpc_ctx: RPC request context.
        :param wf_ex_id: Workflow execution id.
        :param state: State assigned to the workflow. Permitted states are
            SUCCESS or ERROR.
        :param message: Optional information string.

        :return: Workflow execution.
        """
        LOG.info(
            "Received RPC request 'stop_workflow'[execution_id=%s,"
            " state=%s, message=%s]",
            wf_ex_id,
            state,
            message
        )

        return self.engine.stop_workflow(wf_ex_id, state, message)

    def rollback_workflow(self, rpc_ctx, wf_ex_id):
        """Receives calls over RPC to rollback workflows on engine.

        :param rpc_ctx: RPC request context.
        :param wf_ex_id Workflow execution id.
        :return: Workflow execution.
        """
        LOG.info(
            "Received RPC request 'rollback_workflow'[execution_id=%s]",
            wf_ex_id
        )

        return self.engine.rollback_workflow(wf_ex_id)

    def report_running_actions(self, rpc_ctx, action_ex_ids):
        """Receives calls over RPC to receive action execution heartbeats.

        :param rpc_ctx: RPC request context.
        :param action_ex_ids: Action execution ids.
        """
        LOG.info(
            "Received RPC request 'report_running_actions'[action_ex_ids=%s]",
            action_ex_ids
        )

        return self.engine.report_running_actions(action_ex_ids)


def get_oslo_service(setup_profiler=True):
    return EngineServer(
        default_engine.DefaultEngine(),
        setup_profiler=setup_profiler
    )
