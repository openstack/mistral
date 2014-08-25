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


import abc
import six


@six.add_metaclass(abc.ABCMeta)
class Engine(object):
    """Engine interface."""

    @abc.abstractmethod
    def start_workflow(self, workflow_name, workflow_input, **params):
        """Starts the specified workflow.

        :param workflow_name: Workflow name.
        :param workflow_input: Workflow input data as a dictionary.
        :param params: Additional workflow type specific parameters.
        :return: Workflow execution object.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def on_task_result(self, task_id, raw_result):
        """Accepts workflow task raw result and continues the workflow.

        Task result here is a raw task result which comes from a corresponding
        action/workflow associated which the task is associated with.
        :param task_id: Task id.
        :param raw_result: Raw task result that comes from action/workflow
        (before publisher). Instance of mistral.workflow.base.TaskResult
        :return:
        """
        raise NotImplementedError

    @abc.abstractmethod
    def stop_workflow(self, execution_id):
        """Stops workflow execution.

        :param execution_id: Execution id.
        :return: Workflow execution object.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def resume_workflow(self, execution_id):
        """Resumes workflow execution.

        :param execution_id: Execution id.
        :return: Workflow execution object.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def rollback_workflow(self, execution_id):
        """Rolls back workflow execution.

        :param execution_id: Execution id.
        :return: Workflow execution object.
        """
        raise NotImplementedError


@six.add_metaclass(abc.ABCMeta)
class Executor(object):
    """Action executor interface."""

    @abc.abstractmethod
    def run_action(self, task_id, action_name, action_params):
        """Runs action.

        :param task_id: Corresponding task id.
        :param action_name: Action name.
        :param action_params: Action parameters.
        """
        raise NotImplementedError()


@six.add_metaclass(abc.ABCMeta)
class WorkflowPolicy(object):
    """Workflow policy.

    Provides the interface to change the workflow state depending on certain
    conditions.
    """

    @abc.abstractmethod
    def on_task_finish(self, exec_db, task_db):
        """Calculates workflow state after task completion.

        :param task_db: Completed task.
        :return: New workflow state.
        """
        raise NotImplementedError


@six.add_metaclass(abc.ABCMeta)
class TaskPolicy(object):
    """Task policy.

    Provides the interface to perform any work after a has completed.
    An example of task policy may be 'retry' policy that makes engine
    to run a task repeatedly if it finishes with a failure.
    """

    @abc.abstractmethod
    def on_task_finish(self, task_db):
        """Calculates workflow state after task completion.

        :param task_db: Completed task.
        :return: New task state.
        """
        raise NotImplementedError
