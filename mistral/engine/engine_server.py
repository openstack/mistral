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
from mistral import exceptions as exc
from mistral.rpc import base as rpc
from mistral.scheduler import base as sched_base
from mistral.service import base as service_base
from mistral.services import action_heartbeat_checker
from mistral.services import action_heartbeat_sender
from mistral.services import expiration_policy
from mistral.utils import profiler as profiler_utils
from mistral_lib import utils

LOG = logging.getLogger(__name__)

CONF = cfg.CONF


def _validate_config():
    if not CONF.yaql.convert_output_data and CONF.yaql.convert_input_data:
        raise exc.MistralError(
            "The config property 'yaql.convert_output_data' is set to False "
            "so 'yaql.convert_input_data' must also be set to False."
        )


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

        _validate_config()

        db_api.setup_db()

        self._scheduler = sched_base.get_system_scheduler()
        self._scheduler.start()

        self._expiration_policy_tg = expiration_policy.setup()

        action_heartbeat_checker.start()

        # If the current engine instance uses a local action executor
        # then we also need to initialize a heartbeat reporter for it.
        # Heartbeats will be sent to the engine tier in the same way as
        # with a remote executor. So if the current cluster node crashes
        # in the middle of executing an action then one of the remaining
        # engine instances will expire the action in a configured period
        # of time.
        if CONF.executor.type == 'local':
            action_heartbeat_sender.start()

        if self._setup_profiler:
            profiler_utils.setup('mistral-engine', CONF.engine.host)

        # Initialize and start RPC server.

        self._rpc_server = rpc.get_rpc_server_driver()(CONF.engine)
        self._rpc_server.register_endpoint(self)

        self._rpc_server.run(executor=CONF.oslo_rpc_executor)

        self._notify_started('Engine server started.')

    def stop(self, graceful=False):
        # NOTE(rakhmerov): Unfortunately, oslo.service doesn't pass the
        # 'graceful' parameter with a correct value. It's simply ignored
        # in the corresponding call chain leading to a concrete service.
        # The only workaround for now is to check 'graceful_shutdown_timeout'
        # configuration option. If it's not empty (not None or 0) then we
        # should treat it a graceful shutdown.
        graceful = bool(CONF.graceful_shutdown_timeout)

        LOG.info(
            'Stopping an engine server [graceful=%s, timeout=%s]',
            graceful,
            CONF.graceful_shutdown_timeout
        )

        super(EngineServer, self).stop(graceful)

        # The rpc server needs to be stopped first so that the engine
        # server stops receiving new RPC calls. Under load, this operation
        # may take much time in case of graceful shutdown because there
        # still may be RPC messages already polled from the queue and
        # waiting for processing. So an underlying RPC server has to wait
        # until they are processed.
        if self._rpc_server:
            self._rpc_server.stop(graceful)

        action_heartbeat_checker.stop(graceful)

        if CONF.executor.type == 'local':
            action_heartbeat_sender.stop(graceful)

        if self._scheduler:
            self._scheduler.stop(graceful)

            sched_base.destroy_system_scheduler()

        if self._expiration_policy_tg:
            self._expiration_policy_tg.stop(graceful)

    def wait(self):
        LOG.info("Waiting for an engine server to exit...")

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

    def start_task(self, rpc_ctx, task_ex_id, first_run, waiting,
                   triggered_by, rerun, **params):
        """Receives calls over RPC to start tasks on engine.

        """
        LOG.info(
            "Received RPC request 'start_task'[task_ex_id=%s, first_run=%s]",
            task_ex_id,
            first_run
        )

        return self.engine.start_task(
            task_ex_id,
            first_run,
            waiting,
            triggered_by,
            rerun,
            **params
        )

    def start_action(self, rpc_ctx, action_name,
                     action_input, description, namespace, params):
        """Receives calls over RPC to start actions on engine.

        :param rpc_ctx: RPC request context.
        :param action_name: name of the Action.
        :param action_input: input dictionary for Action.
        :param description: description of new Action execution.
        :param namespace: The namespace of the action.
        :param params: extra parameters to run Action.
        :return: Action execution.
        """
        LOG.info(
            "Received RPC request 'start_action'[name=%s, input=%s, "
            "description=%s, namespace=%s params=%s]",
            action_name,
            utils.cut(action_input),
            description,
            namespace,
            params
        )

        return self.engine.start_action(
            action_name,
            action_input,
            description,
            namespace=namespace,
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
            result.cut_repr() if result else '<unknown>'
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

    def rerun_workflow(self, rpc_ctx, task_ex_id, reset=True,
                       skip=False, env=None):
        """Receives calls over RPC to rerun workflows on engine.

        :param rpc_ctx: RPC request context.
        :param task_ex_id: Task execution id.
        :param reset: If true, then purge action execution for the task.
        :param skip: If True, then skip failed task and continue workflow
            execution.
        :param env: Environment variables to update.
        :return: Workflow execution.
        """
        LOG.info(
            "Received RPC request 'rerun_workflow'[task_ex_id=%s]",
            task_ex_id
        )

        return self.engine.rerun_workflow(task_ex_id, reset, skip, env)

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

        return self.engine.process_action_heartbeats(action_ex_ids)


def get_oslo_service(setup_profiler=True):
    return EngineServer(
        default_engine.DefaultEngine(),
        setup_profiler=setup_profiler
    )
