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
    def run_task(self, task_id):
        """Runs task with given id..

        :param task_id: Task id.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def pause_workflow(self, execution_id):
        """Pauses workflow execution.

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
    def run_action(self, task_id, action_class_str, attributes,
                   action_params):
        """Runs action.

        :param task_id: Corresponding task id.
        :param action_class_str: Path to action class in dot notation.
        :param attributes: Attributes of action class which will be set to.
        :param action_params: Action parameters.
        """
        raise NotImplementedError()


@six.add_metaclass(abc.ABCMeta)
class TaskPolicy(object):
    """Task policy.

    Provides interface to perform any work after a task has completed.
    An example of task policy may be 'retry' policy that makes engine
    to run a task repeatedly if it finishes with a failure.
    """

    def before_task_start(self, task_db, task_spec):
        """Called right before task start.

        :param task_db: DB model for task that is about to start.
        :param task_spec: Task specification.
        """
        # No-op by default.
        pass

    def after_task_complete(self, task_db, task_spec, raw_result):
        """Called right after task completes.

        :param task_db: Completed task DB model.
        :param task_spec: Completed task specification.
        :param raw_result: TaskResult instance passed to on_task_result.
         It is needed for analysis of result and scheduling task again.
        """
        # No-op by default.
        pass
