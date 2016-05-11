# Copyright 2014 - Mirantis, Inc.
# Copyright 2015 - StackStorm, Inc.
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
import oslo_messaging as messaging
from oslo_messaging.rpc import client
from oslo_messaging.rpc import dispatcher
from oslo_messaging.rpc import server

from mistral import context as auth_ctx
from mistral.engine import base
from mistral import exceptions as exc
from mistral.workflow import utils as wf_utils


LOG = logging.getLogger(__name__)


_TRANSPORT = None

_ENGINE_CLIENT = None
_EXECUTOR_CLIENT = None


def get_rpc_server(transport, target, endpoints, executor='blocking',
                   serializer=None):
    return server.RPCServer(
        transport,
        target,
        dispatcher.RPCDispatcher(endpoints, serializer),
        executor
    )


def cleanup():
    """Intended to be used by tests to recreate all RPC related objects."""

    global _TRANSPORT
    global _ENGINE_CLIENT
    global _EXECUTOR_CLIENT

    _TRANSPORT = None
    _ENGINE_CLIENT = None
    _EXECUTOR_CLIENT = None


def get_transport():
    global _TRANSPORT

    if not _TRANSPORT:
        _TRANSPORT = messaging.get_transport(cfg.CONF)

    return _TRANSPORT


def get_engine_client():
    global _ENGINE_CLIENT

    if not _ENGINE_CLIENT:
        _ENGINE_CLIENT = EngineClient(get_transport())

    return _ENGINE_CLIENT


def get_executor_client():
    global _EXECUTOR_CLIENT

    if not _EXECUTOR_CLIENT:
        _EXECUTOR_CLIENT = ExecutorClient(get_transport())

    return _EXECUTOR_CLIENT


class EngineServer(object):
    """RPC Engine server."""

    def __init__(self, engine):
        self._engine = engine

    def start_workflow(self, rpc_ctx, workflow_identifier, workflow_input,
                       description, params):
        """Receives calls over RPC to start workflows on engine.

        :param rpc_ctx: RPC request context.
        :param workflow_identifier: Workflow definition identifier.
        :param workflow_input: Workflow input.
        :param description: Workflow execution description.
        :param params: Additional workflow type specific parameters.
        :return: Workflow execution.
        """

        LOG.info(
            "Received RPC request 'start_workflow'[rpc_ctx=%s,"
            " workflow_identifier=%s, workflow_input=%s, description=%s, "
            "params=%s]"
            % (rpc_ctx, workflow_identifier, workflow_input, description,
               params)
        )

        return self._engine.start_workflow(
            workflow_identifier,
            workflow_input,
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
            "Received RPC request 'start_action'[rpc_ctx=%s,"
            " name=%s, input=%s, description=%s, params=%s]"
            % (rpc_ctx, action_name, action_input, description, params)
        )

        return self._engine.start_action(
            action_name,
            action_input,
            description,
            **params
        )

    def on_task_state_change(self, rpc_ctx, task_ex_id, state,
                             state_info=None):
        return self._engine.on_task_state_change(task_ex_id, state, state_info)

    def on_action_complete(self, rpc_ctx, action_ex_id, result_data,
                           result_error):
        """Receives RPC calls to communicate action result to engine.

        :param rpc_ctx: RPC request context.
        :param action_ex_id: Action execution id.
        :param result_data: Action result data.
        :param result_error: Action result error.
        :return: Action execution.
        """

        result = wf_utils.Result(result_data, result_error)

        LOG.info(
            "Received RPC request 'on_action_complete'[rpc_ctx=%s,"
            " action_ex_id=%s, result=%s]" % (rpc_ctx, action_ex_id, result)
        )

        return self._engine.on_action_complete(action_ex_id, result)

    def pause_workflow(self, rpc_ctx, execution_id):
        """Receives calls over RPC to pause workflows on engine.

        :param rpc_ctx: Request context.
        :param execution_id: Workflow execution id.
        :return: Workflow execution.
        """

        LOG.info(
            "Received RPC request 'pause_workflow'[rpc_ctx=%s,"
            " execution_id=%s]" % (rpc_ctx, execution_id)
        )

        return self._engine.pause_workflow(execution_id)

    def rerun_workflow(self, rpc_ctx, wf_ex_id, task_ex_id,
                       reset=True, env=None):
        """Receives calls over RPC to rerun workflows on engine.

        :param rpc_ctx: RPC request context.
        :param wf_ex_id: Workflow execution id.
        :param task_ex_id: Task execution id.
        :param reset: If true, then purge action execution for the task.
        :param env: Environment variables to update.
        :return: Workflow execution.
        """

        LOG.info(
            "Received RPC request 'rerun_workflow'[rpc_ctx=%s, "
            "wf_ex_id=%s, task_ex_id=%s]" % (rpc_ctx, wf_ex_id, task_ex_id)
        )

        return self._engine.rerun_workflow(wf_ex_id, task_ex_id, reset, env)

    def resume_workflow(self, rpc_ctx, wf_ex_id, env=None):
        """Receives calls over RPC to resume workflows on engine.

        :param rpc_ctx: RPC request context.
        :param wf_ex_id: Workflow execution id.
        :param env: Environment variables to update.
        :return: Workflow execution.
        """

        LOG.info(
            "Received RPC request 'resume_workflow'[rpc_ctx=%s, "
            "wf_ex_id=%s]" % (rpc_ctx, wf_ex_id)
        )

        return self._engine.resume_workflow(wf_ex_id, env)

    def stop_workflow(self, rpc_ctx, execution_id, state, message=None):
        """Receives calls over RPC to stop workflows on engine.

        Sets execution state to SUCCESS or ERROR. No more tasks will be
        scheduled. Running tasks won't be killed, but their results
        will be ignored.

        :param rpc_ctx: RPC request context.
        :param execution_id: Workflow execution id.
        :param state: State assigned to the workflow. Permitted states are
            SUCCESS or ERROR.
        :param message: Optional information string.

        :return: Workflow execution.
        """

        LOG.info(
            "Received RPC request 'stop_workflow'[rpc_ctx=%s, execution_id=%s,"
            " state=%s, message=%s]" % (rpc_ctx, execution_id, state, message)
        )

        return self._engine.stop_workflow(execution_id, state, message)

    def rollback_workflow(self, rpc_ctx, execution_id):
        """Receives calls over RPC to rollback workflows on engine.

        :param rpc_ctx: RPC request context.
        :return: Workflow execution.
        """

        LOG.info(
            "Received RPC request 'rollback_workflow'[rpc_ctx=%s,"
            " execution_id=%s]" % (rpc_ctx, execution_id)
        )

        return self._engine.resume_workflow(execution_id)


def _wrap_exception_and_reraise(exception):
    message = "%s: %s" % (exception.__class__.__name__, exception.args[0])

    raise exc.MistralException(message)


def wrap_messaging_exception(method):
    """This decorator unwrap remote error in one of MistralException.

    oslo.messaging has different behavior on raising exceptions
    when fake or rabbit transports are used. In case of rabbit
    transport it raises wrapped RemoteError which forwards directly
    to API. Wrapped RemoteError contains one of MistralException raised
    remotely on Engine and for correct exception interpretation we
    need to unwrap and raise given exception and manually send it to
    API layer.
    """
    def decorator(*args, **kwargs):
        try:
            return method(*args, **kwargs)

        except exc.MistralException:
            raise
        except (client.RemoteError, Exception) as e:
            if hasattr(e, 'exc_type') and hasattr(exc, e.exc_type):
                exc_cls = getattr(exc, e.exc_type)
                raise exc_cls(e.value)

            _wrap_exception_and_reraise(e)

    return decorator


class EngineClient(base.Engine):
    """RPC Engine client."""

    def __init__(self, transport):
        """Constructs an RPC client for engine.

        :param transport: Messaging transport.
        """
        serializer = auth_ctx.RpcContextSerializer(
            auth_ctx.JsonPayloadSerializer())

        self._client = messaging.RPCClient(
            transport,
            messaging.Target(topic=cfg.CONF.engine.topic),
            serializer=serializer
        )

    @wrap_messaging_exception
    def start_workflow(self, wf_identifier, wf_input, description='',
                       **params):
        """Starts workflow sending a request to engine over RPC.

        :return: Workflow execution.
        """
        return self._client.call(
            auth_ctx.ctx(),
            'start_workflow',
            workflow_identifier=wf_identifier,
            workflow_input=wf_input or {},
            description=description,
            params=params
        )

    @wrap_messaging_exception
    def start_action(self, action_name, action_input,
                     description=None, **params):
        """Starts action sending a request to engine over RPC.

        :return: Action execution.
        """
        return self._client.call(
            auth_ctx.ctx(),
            'start_action',
            action_name=action_name,
            action_input=action_input or {},
            description=description,
            params=params
        )

    def on_task_state_change(self, task_ex_id, state, state_info=None):
        return self._client.call(
            auth_ctx.ctx(),
            'on_task_state_change',
            task_ex_id=task_ex_id,
            state=state,
            state_info=state_info
        )

    @wrap_messaging_exception
    def on_action_complete(self, action_ex_id, result):
        """Conveys action result to Mistral Engine.

        This method should be used by clients of Mistral Engine to update
        state of a action execution once action has executed. One of the
        clients of this method is Mistral REST API server that receives
        action result from the outside action handlers.

        Note: calling this method serves an event notifying Mistral that
        it possibly needs to move the workflow on, i.e. run other workflow
        tasks for which all dependencies are satisfied.

        :param action_ex_id: Action execution id.
        :param result: Action execution result.
        :return: Task.
        """

        return self._client.call(
            auth_ctx.ctx(),
            'on_action_complete',
            action_ex_id=action_ex_id,
            result_data=result.data,
            result_error=result.error
        )

    @wrap_messaging_exception
    def pause_workflow(self, wf_ex_id):
        """Stops the workflow with the given execution id.

        :param wf_ex_id: Workflow execution id.
        :return: Workflow execution.
        """

        return self._client.call(
            auth_ctx.ctx(),
            'pause_workflow',
            execution_id=wf_ex_id
        )

    @wrap_messaging_exception
    def rerun_workflow(self, wf_ex_id, task_ex_id, reset=True, env=None):
        """Rerun the workflow.

        This method reruns workflow with the given execution id
        at the specific task execution id.

        :param wf_ex_id: Workflow execution id.
        :param task_ex_id: Task execution id.
        :param reset: If true, then reset task execution state and purge
            action execution for the task.
        :param env: Environment variables to update.
        :return: Workflow execution.
        """

        return self._client.call(
            auth_ctx.ctx(),
            'rerun_workflow',
            wf_ex_id=wf_ex_id,
            task_ex_id=task_ex_id,
            reset=reset,
            env=env
        )

    @wrap_messaging_exception
    def resume_workflow(self, wf_ex_id, env=None):
        """Resumes the workflow with the given execution id.

        :param wf_ex_id: Workflow execution id.
        :param env: Environment variables to update.
        :return: Workflow execution.
        """

        return self._client.call(
            auth_ctx.ctx(),
            'resume_workflow',
            wf_ex_id=wf_ex_id,
            env=env
        )

    @wrap_messaging_exception
    def stop_workflow(self, wf_ex_id, state, message=None):
        """Stops workflow execution with given status.

        Once stopped, the workflow is complete with SUCCESS or ERROR,
        and can not be resumed.

        :param wf_ex_id: Workflow execution id
        :param state: State assigned to the workflow: SUCCESS or ERROR
        :param message: Optional information string

        :return: Workflow execution, model.Execution
        """

        return self._client.call(
            auth_ctx.ctx(),
            'stop_workflow',
            execution_id=wf_ex_id,
            state=state,
            message=message
        )

    @wrap_messaging_exception
    def rollback_workflow(self, wf_ex_id):
        """Rolls back the workflow with the given execution id.

        :param wf_ex_id: Workflow execution id.

        :return: Workflow execution.
        """

        return self._client.call(
            auth_ctx.ctx(),
            'rollback_workflow',
            execution_id=wf_ex_id
        )


class ExecutorServer(object):
    """RPC Executor server."""

    def __init__(self, executor):
        self._executor = executor

    def run_action(self, rpc_ctx, action_ex_id, action_class_str,
                   attributes, params):
        """Receives calls over RPC to run action on executor.

        :param rpc_ctx: RPC request context dictionary.
        :param action_ex_id: Action execution id.
        :param action_class_str: Action class name.
        :param attributes: Action class attributes.
        :param params: Action input parameters.
        :return: Action result.
        """

        LOG.info(
            "Received RPC request 'run_action'[rpc_ctx=%s,"
            " action_ex_id=%s, action_class=%s, attributes=%s, params=%s]"
            % (rpc_ctx, action_ex_id, action_class_str, attributes, params)
        )

        return self._executor.run_action(
            action_ex_id,
            action_class_str,
            attributes,
            params
        )


class ExecutorClient(base.Executor):
    """RPC Executor client."""

    def __init__(self, transport):
        """Constructs an RPC client for the Executor.

        :param transport: Messaging transport.
        :type transport: Transport.
        """
        self.topic = cfg.CONF.executor.topic

        serializer = auth_ctx.RpcContextSerializer(
            auth_ctx.JsonPayloadSerializer()
        )

        self._client = messaging.RPCClient(
            transport,
            messaging.Target(),
            serializer=serializer
        )

    def run_action(self, action_ex_id, action_class_str, attributes,
                   action_params, target=None, async=True):
        """Sends a request to run action to executor.

        :param action_ex_id: Action execution id.
        :param action_class_str: Action class name.
        :param attributes: Action class attributes.
        :param action_params: Action input parameters.
        :param target: Target (group of action executors).
        :param async: If True, run action in asynchronous mode (w/o waiting
            for completion).
        :return: Action result.
        """

        kwargs = {
            'action_ex_id': action_ex_id,
            'action_class_str': action_class_str,
            'attributes': attributes,
            'params': action_params
        }

        call_ctx = self._client.prepare(topic=self.topic, server=target)

        rpc_client_method = call_ctx.cast if async else call_ctx.call

        res = rpc_client_method(auth_ctx.ctx(), 'run_action', **kwargs)

        # TODO(rakhmerov): It doesn't seem a good approach since we have
        # a serializer for Result class. A better solution would be to
        # use a composite serializer that dispatches serialization and
        # deserialization to concrete serializers depending on object
        # type.

        return (
            wf_utils.Result(data=res['data'], error=res['error'])
            if res else None
        )
