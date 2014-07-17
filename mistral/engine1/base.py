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


class TaskResult(object):
    """Explicit data structure containing a result of task execution."""

    def __init__(self, data=None, error=None):
        self.data = data
        self.error = error

    def is_error(self):
        return self.error is not None

    def is_success(self):
        return not self.is_error()


@six.add_metaclass(abc.ABCMeta)
class Engine(object):
    """Engine interface."""

    @abc.abstractmethod
    def start_workflow(self, workbook_name, workflow_name, task_name, input):
        """Starts the specified workflow.

        :param workbook_name: Workbook name.
        :param workflow_name: Workflow name.
        :param task_name: Task name.
        :param input: Workflow input data as a dictionary.
        :return: Workflow execution object.
        """
        raise NotImplemented

    @abc.abstractmethod
    def on_task_result(self, task_id, task_result):
        """Accepts workflow task raw result and continues the workflow.

        Task result here is a raw task result which comes from a corresponding
        action/workflow associated which the task is associated with.
        :param task_id: Task id.
        :param task_result: Task result object.
        :return:
        """
        raise NotImplemented

    @abc.abstractmethod
    def stop_workflow(self, execution_id):
        """Stops workflow execution.

        :param execution_id: Execution id.
        :return: Workflow execution object.
        """
        raise NotImplemented

    @abc.abstractmethod
    def resume_workflow(self, execution_id):
        """Resumes workflow execution.

        :param execution_id: Execution id.
        :return: Workflow execution object.
        """
        raise NotImplemented

    @abc.abstractmethod
    def rollback_workflow(self, execution_id):
        """Rolls back workflow execution.

        :param execution_id: Execution id.
        :return: Workflow execution object.
        """
        raise NotImplemented


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
        raise NotImplemented


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
        raise NotImplemented
