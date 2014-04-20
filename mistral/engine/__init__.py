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

from mistral.openstack.common import importutils
from mistral.openstack.common import log as logging


LOG = logging.getLogger(__name__)


def get_transport(transport=None):
    return (transport if transport else messaging.get_transport(cfg.CONF))


class Engine(object):

    def __init__(self, transport=None):
        module_name = cfg.CONF.engine.engine
        module = importutils.import_module(module_name)
        self.transport = get_transport(transport)
        self.backend = module.get_engine()
        self.backend.transport = self.transport

    def start_workflow_execution(self, cntx, **kwargs):
        """Starts a workflow execution based on the specified workbook name
        and target task.

        :param cntx: a request context dict
        :type cntx: dict
        :param kwargs: a dict of method arguments
        :type kwargs: dict
        :return: Workflow execution.
        """
        workbook_name = kwargs.get('workbook_name')
        task_name = kwargs.get('task_name')
        context = kwargs.get('context', None)
        return self.backend.start_workflow_execution(
            workbook_name, task_name, context)

    def stop_workflow_execution(self, cntx, **kwargs):
        """Stops the workflow execution with the given id.

        :param cntx: a request context dict
        :type cntx: dict
        :param kwargs: a dict of method arguments
        :type kwargs: dict
        :return: Workflow execution.
        """
        workbook_name = kwargs.get('workbook_name')
        execution_id = kwargs.get('execution_id')
        return self.backend.stop_workflow_execution(
            workbook_name, execution_id)

    def convey_task_result(self, cntx, **kwargs):
        """Conveys task result to Mistral Engine.

        This method should be used by clients of Mistral Engine to update
        state of a task once task action has been performed. One of the
        clients of this method is Mistral REST API server that receives
        task result from the outside action handlers.

        Note: calling this method serves an event notifying Mistral that
        it possibly needs to move the workflow on, i.e. run other workflow
        tasks for which all dependencies are satisfied.

        :param cntx: a request context dict
        :type cntx: dict
        :param kwargs: a dict of method arguments
        :type kwargs: dict
        :return: Task.
        """
        workbook_name = kwargs.get('workbook_name')
        execution_id = kwargs.get('execution_id')
        task_id = kwargs.get('task_id')
        state = kwargs.get('state')
        result = kwargs.get('result')
        return self.backend.convey_task_result(
            workbook_name, execution_id, task_id, state, result)

    def get_workflow_execution_state(self, cntx, **kwargs):
        """Gets the workflow execution state.

        :param cntx: a request context dict
        :type cntx: dict
        :param kwargs: a dict of method arguments
        :type kwargs: dict
        :return: Current workflow state.
        """
        workbook_name = kwargs.get('workbook_name')
        execution_id = kwargs.get('execution_id')
        return self.backend.get_workflow_execution_state(
            workbook_name, execution_id)

    def get_task_state(self, cntx, **kwargs):
        """Gets task state.

        :param cntx: a request context dict
        :type cntx: dict
        :param kwargs: a dict of method arguments
        :type kwargs: dict
        :return: Current task state.
        """
        workbook_name = kwargs.get('workbook_name')
        execution_id = kwargs.get('execution_id')
        task_id = kwargs.get('task_id')
        return self.backend.get_task_state(
            workbook_name, execution_id, task_id)
