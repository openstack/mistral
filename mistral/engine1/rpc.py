# Copyright 2014 - Mirantis, Inc.
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

from oslo.config import cfg
from oslo import messaging

from mistral import context as auth_ctx
from mistral.engine1 import base
from mistral.openstack.common import log as logging
from mistral.workflow import utils as wf_utils

LOG = logging.getLogger(__name__)


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

    def start_workflow(self, rpc_ctx, workflow_name, workflow_input, params):
        """Receives calls over RPC to start workflows on engine.

        :param rpc_ctx: RPC request context.
        :return: Workflow execution.
        """

        LOG.info(
            "Received RPC request 'start_workflow'[rpc_ctx=%s,"
            " workflow_name=%s, workflow_input=%s, params=%s]"
            % (rpc_ctx, workflow_name, workflow_input, params)
        )

        return self._engine.start_workflow(
            workflow_name,
            workflow_input,
            **params
        )

    def on_task_result(self, rpc_ctx, task_id, result_data, result_error):
        """Receives calls over RPC to communicate task result to engine.

        :param rpc_ctx: RPC request context.
        :return: Task.
        """

        task_result = wf_utils.TaskResult(result_data, result_error)

        LOG.info(
            "Received RPC request 'on_task_result'[rpc_ctx=%s,"
            " task_id=%s, task_result=%s]" % (rpc_ctx, task_id, task_result)
        )

        return self._engine.on_task_result(task_id, task_result)

    def run_task(self, rpc_ctx, task_id):
        """Runs task with given id..

        :param rpc_ctx: RPC request context.
        :param task_id: Task id.
        """

        LOG.info(
            "Received RPC request 'run_task'[rpc_ctx=%s, task_id=%s]" %
            (rpc_ctx, task_id)
        )

        return self._engine.run_task(task_id)

    def pause_workflow(self, rpc_ctx, execution_id):
        """Receives calls over RPC to pause workflows on engine.

        :param rpc_ctx: Request context.
        :return: Workflow execution.
        """

        LOG.info(
            "Received RPC request 'pause_workflow'[rpc_ctx=%s,"
            " execution_id=%s]" % (rpc_ctx, execution_id)
        )

        return self._engine.pause_workflow(execution_id)

    def resume_workflow(self, rpc_ctx, execution_id):
        """Receives calls over RPC to resume workflows on engine.

        :param rpc_ctx: RPC request context.
        :return: Workflow execution.
        """

        LOG.info(
            "Received RPC request 'resume_workflow'[rpc_ctx=%s,"
            " execution_id=%s]" % (rpc_ctx, execution_id)
        )

        return self._engine.resume_workflow(execution_id)

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

    def start_workflow(self, workflow_name, workflow_input, **params):
        """Starts workflow sending a request to engine over RPC.

        :return: Workflow execution.
        """
        return self._client.call(
            auth_ctx.ctx(),
            'start_workflow',
            workflow_name=workflow_name,
            workflow_input=workflow_input or {},
            params=params
        )

    def on_task_result(self, task_id, raw_result):
        """Conveys task result to Mistral Engine.

        This method should be used by clients of Mistral Engine to update
        state of a task once task action has been performed. One of the
        clients of this method is Mistral REST API server that receives
        task result from the outside action handlers.

        Note: calling this method serves an event notifying Mistral that
        it possibly needs to move the workflow on, i.e. run other workflow
        tasks for which all dependencies are satisfied.

        :return: Task.
        """

        return self._client.call(
            auth_ctx.ctx(),
            'on_task_result',
            task_id=task_id,
            result_data=raw_result.data,
            result_error=raw_result.error
        )

    def run_task(self, task_id):
        """Runs task with given id.

        :param task_id: Task id.
        """
        return self._client.call(auth_ctx.ctx(),
                                 'run_task',
                                 task_id=task_id)

    def pause_workflow(self, execution_id):
        """Stops the workflow with the given execution id.

        :return: Workflow execution.
        """

        return self._client.call(
            auth_ctx.ctx(),
            'pause_workflow',
            execution_id=execution_id
        )

    def resume_workflow(self, execution_id):
        """Resumes the workflow with the given execution id.

        :return: Workflow execution.
        """

        return self._client.call(
            auth_ctx.ctx(),
            'resume_workflow',
            execution_id=execution_id
        )

    def rollback_workflow(self, execution_id):
        """Rolls back the workflow with the given execution id.

        :return: Workflow execution.
        """

        return self._client.call(
            auth_ctx.ctx(),
            'rollback_workflow',
            execution_id=execution_id
        )


class ExecutorServer(object):
    """RPC Executor server."""

    def __init__(self, executor):
        self._executor = executor

    def run_action(self, rpc_ctx, task_id, action_class_str,
                   attributes, params):
        """Receives calls over RPC to run task on engine.

        :param rpc_ctx: RPC request context dictionary.
        """

        LOG.info(
            "Received RPC request 'run_action'[rpc_ctx=%s,"
            " task_id=%s, action_class=%s, attributes=%s, params=%s]"
            % (rpc_ctx, task_id, action_class_str, attributes, params)
        )

        self._executor.run_action(task_id, action_class_str,
                                  attributes, params)


class ExecutorClient(base.Executor):
    """RPC Executor client."""

    def __init__(self, transport):
        """Constructs an RPC client for the Executor.

        :param transport: Messaging transport.
        :type transport: Transport.
        """
        serializer = auth_ctx.RpcContextSerializer(
            auth_ctx.JsonPayloadSerializer()
        )

        self.topic = cfg.CONF.executor.topic
        self._client = messaging.RPCClient(
            transport,
            messaging.Target(),
            serializer=serializer
        )

    def run_action(self, task_id, action_class_str, attributes,
                   action_params, targets=None):
        """Sends a request to run action to executor."""

        kwargs = {
            'task_id': task_id,
            'action_class_str': action_class_str,
            'attributes': attributes,
            'params': action_params
        }

        if targets:
            for target in targets:
                self._cast_run_action(self.topic, target, **kwargs)
        else:
            self._cast_run_action(self.topic, **kwargs)

    def _cast_run_action(self, topic, target=None, **kwargs):
        self._client.prepare(topic=topic, server=target).cast(
            auth_ctx.ctx(),
            'run_action',
            **kwargs
        )
