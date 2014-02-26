# -*- coding: utf-8 -*-
#
# Copyright 2013 - Mirantis, Inc.
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

"""
Facade interface to Mistral Engine that provides control over lifecycle
of workflow executions.
"""

from mistral.openstack.common import importutils
from oslo.config import cfg

_engine = None


def load_engine():
    global _engine
    module_name = cfg.CONF.engine.engine
    module = importutils.import_module(module_name)
    _engine = module.get_engine()


def start_workflow_execution(workbook_name, task_name, context=None):
    """Starts a workflow execution based on the specified workbook name
     and target task.

    :param workbook_name: Workbook name
    :param task_name: Target task name
    :param context: Execution context which defines a workflow input
    :return: Workflow execution.
    """
    return _engine.start_workflow_execution(workbook_name, task_name, context)


def stop_workflow_execution(workbook_name, execution_id):
    """Stops the workflow execution with the given id.

    :param workbook_name: Workbook name.
    :param execution_id: Workflow execution id.
    :return: Workflow execution.
    """
    return _engine.stop_workflow_execution(workbook_name, execution_id)


def convey_task_result(workbook_name, execution_id, task_id, state, result):
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
    return _engine.convey_task_result(workbook_name, execution_id, task_id,
                                      state, result)


def get_workflow_execution_state(workbook_name, execution_id):
    """Gets the workflow execution state.

    :param workbook_name: Workbook name.
    :param execution_id: Workflow execution id.
    :return: Current workflow state.
    """
    return _engine.get_workflow_execution_state(workbook_name, execution_id)


def get_task_state(workbook_name, execution_id, task_id):
    """Gets task state.

    :param workbook_name: Workbook name.
    :param execution_id: Workflow execution id.
    :param task_id: Task id.
    :return: Current task state.
    """
    return _engine.get_task_state(workbook_name, execution_id, task_id)
