# -*- coding: utf-8 -*-
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
from oslo.config import cfg

from mistral.openstack.common import log as logging


LOG = logging.getLogger(__name__)


class EngineClient(object):
    """
    RPC client for the Engine.
    """

    def __init__(self, transport):
        """Construct an RPC client for the Engine.

        :param transport: a messaging transport handle
        :type transport: Transport
        """
        target = messaging.Target(topic=cfg.CONF.engine.topic)
        self._client = messaging.RPCClient(transport, target)

    def start_workflow_execution(self, workbook_name, task_name, context=None):
        """Starts a workflow execution based on the specified workbook name
        and target task.

        :param workbook_name: Workbook name
        :param task_name: Target task name
        :param context: Execution context which defines a workflow input
        :return: Workflow execution.
        """
        # TODO(m4dcoder): refactor auth context
        cntx = {}
        kwargs = {'workbook_name': workbook_name,
                  'task_name': task_name,
                  'context': context}
        return self._client.call(cntx, 'start_workflow_execution', **kwargs)

    def stop_workflow_execution(self, workbook_name, execution_id):
        """Stops the workflow execution with the given id.

        :param workbook_name: Workbook name.
        :param execution_id: Workflow execution id.
        :return: Workflow execution.
        """
        # TODO(m4dcoder): refactor auth context
        cntx = {}
        kwargs = {'workbook_name': workbook_name,
                  'execution_id': execution_id}
        return self._client.call(cntx, 'stop_workflow_execution', **kwargs)

    def convey_task_result(self, workbook_name, execution_id,
                           task_id, state, result):
        """Conveys task result to Mistral Engine.

        This method should be used by clients of Mistral Engine to update
        state of a task once task action has been performed. One of the
        clients of this method is Mistral REST API server that receives
        task result from the outside action handlers.

        Note: calling this method serves an event notifying Mistral that
        it possibly needs to move the workflow on, i.e. run other workflow
        tasks for which all dependencies are satisfied.

        :param workbook_name: Workbook name.
        :param execution_id: Workflow execution id.
        :param task_id: Task id.
        :param state: New task state.
        :param result: Task result data.
        :return: Task.
        """
        # TODO(m4dcoder): refactor auth context
        cntx = {}
        kwargs = {'workbook_name': workbook_name,
                  'execution_id': execution_id,
                  'task_id': task_id,
                  'state': state,
                  'result': result}
        return self._client.call(cntx, 'convey_task_result', **kwargs)

    def get_workflow_execution_state(self, workbook_name, execution_id):
        """Gets the workflow execution state.

        :param workbook_name: Workbook name.
        :param execution_id: Workflow execution id.
        :return: Current workflow state.
        """
        # TODO(m4dcoder): refactor auth context
        cntx = {}
        kwargs = {'workbook_name': workbook_name,
                  'execution_id': execution_id}
        return self._client.call(
            cntx, 'get_workflow_execution_state', **kwargs)

    def get_task_state(self, workbook_name, execution_id, task_id):
        """Gets task state.

        :param workbook_name: Workbook name.
        :param execution_id: Workflow execution id.
        :param task_id: Task id.
        :return: Current task state.
        """
        # TODO(m4dcoder): refactor auth context
        cntx = {}
        kwargs = {'workbook_name': workbook_name,
                  'executioin_id': execution_id,
                  'task_id': task_id}
        return self._client.call(cntx, 'get_task_state', **kwargs)
