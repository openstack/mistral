# -*- coding: utf-8 -*-
#
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

from oslo import messaging

from mistral import context as auth_ctx
from mistral.openstack.common import log as logging


LOG = logging.getLogger(__name__)


# TODO(rakhmerov): Add engine and executor servers so that we don't need to
# adopt them to work with rpc (taking care about transport, signatures etc.).

class EngineClient(object):
    """RPC client for the Engine."""

    def __init__(self, transport):
        """Construct an RPC client for the Engine.

        :param transport: Messaging transport.
        :type transport: Transport.
        """
        serializer = auth_ctx.RpcContextSerializer(
            auth_ctx.JsonPayloadSerializer())

        # TODO(rakhmerov): Clarify topic.
        target = messaging.Target(
            topic='mistral.engine1.default_engine:DefaultEngine'
        )

        self._client = messaging.RPCClient(
            transport,
            target,
            serializer=serializer
        )

    def start_workflow(self, workbook_name, workflow_name, task_name, input):
        """Starts a workflow execution based on the specified workbook name
        and target task.

        :param workbook_name: Workbook name.
        :param task_name: Target task name.
        :param input: Workflow input data.
        :return: Workflow execution.
        """
        kwargs = {
            'workbook_name': workbook_name,
            'workflow_name': workflow_name,
            'task_name': task_name,
            'input': input
        }

        return self._client.call(auth_ctx.ctx(), 'start_workflow', **kwargs)

    def on_task_result(self, task_id, task_result):
        """Conveys task result to Mistral Engine.

        This method should be used by clients of Mistral Engine to update
        state of a task once task action has been performed. One of the
        clients of this method is Mistral REST API server that receives
        task result from the outside action handlers.

        Note: calling this method serves an event notifying Mistral that
        it possibly needs to move the workflow on, i.e. run other workflow
        tasks for which all dependencies are satisfied.

        :param task_id: Task id.
        :param task_result: Task result data.
        :return: Task.
        """
        kwargs = {
            'task_id': task_id,
            'task_result': task_result
        }

        return self._client.call(auth_ctx.ctx(), 'on_task_result', **kwargs)

    def stop_workflow(self, execution_id):
        """Stops the workflow with the given execution id.

        :param execution_id: Workflow execution id.
        :return: Workflow execution.
        """
        kwargs = {'execution_id': execution_id}

        return self._client.call(auth_ctx.ctx(), 'stop_workflow', **kwargs)

    def resume_workflow(self, execution_id):
        """Resumes the workflow with the given execution id.

        :param execution_id: Workflow execution id.
        :return: Workflow execution.
        """
        kwargs = {'execution_id': execution_id}

        return self._client.call(auth_ctx.ctx(), 'resume_workflow', **kwargs)

    def rollback_workflow(self, execution_id):
        """Rolls back the workflow with the given execution id.

        :param execution_id: Workflow execution id.
        :return: Workflow execution.
        """
        kwargs = {'execution_id': execution_id}

        return self._client.call(auth_ctx.ctx(), 'rollback_workflow', **kwargs)


class ExecutorClient(object):
    """RPC client for Executor."""

    def __init__(self, transport):
        """Construct an RPC client for the Executor.

        :param transport: Messaging transport.
        :type transport: Transport.
        """
        serializer = auth_ctx.RpcContextSerializer(
            auth_ctx.JsonPayloadSerializer())

        # TODO(rakhmerov): Clarify topic.
        target = messaging.Target(
            topic='mistral.engine1.default_engine:DefaultExecutor'
        )

        self._client = messaging.RPCClient(
            transport,
            target,
            serializer=serializer
        )

    # TODO(rakhmerov): Most likely it will be a different method.
    def handle_task(self, cntx, **kwargs):
        """Send the task request to Executor for execution.

        :param cntx: a request context dict
        :type cntx: MistralContext
        :param kwargs: a dict of method arguments
        :type kwargs: dict
        """
        return self._client.cast(cntx, 'handle_task', **kwargs)
