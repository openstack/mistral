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
import jsonschema
import six

from mistral import exceptions as exc
from mistral.utils import inspect_utils
from mistral.workflow import data_flow


@six.add_metaclass(abc.ABCMeta)
class Engine(object):
    """Engine interface."""

    @abc.abstractmethod
    def start_workflow(self, wf_identifier, wf_input, description='',
                       **params):
        """Starts the specified workflow.

        :param wf_identifier: Workflow ID or name. Workflow ID is recommended,
            workflow name will be deprecated since Mitaka.
        :param wf_input: Workflow input data as a dictionary.
        :param description: Execution description.
        :param params: Additional workflow type specific parameters.
        :return: Workflow execution object.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def start_action(self, action_name, action_input,
                     description=None, **params):
        """Starts the specific action.

        :param action_name: Action name.
        :param action_input: Action input data as a dictionary.
        :param description: Execution description.
        :param params: Additional options for action running.
        :return: Action execution object.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def on_action_complete(self, action_ex_id, result, wf_action=False):
        """Accepts action result and continues the workflow.

        Action execution result here is a result which comes from an
        action/workflow associated which the task.
        :param action_ex_id: Action execution id.
        :param result: Action/workflow result. Instance of
            mistral.workflow.base.Result
        :param wf_action: If True it means that the given id points to
            a workflow execution rather than action execution. It happens
            when a nested workflow execution sends its result to a parent
            workflow.
        :return: Action(or workflow if wf_action=True) execution object.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def pause_workflow(self, wf_ex_id):
        """Pauses workflow.

        :param wf_ex_id: Execution id.
        :return: Workflow execution object.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def resume_workflow(self, wf_ex_id, env=None):
        """Resumes workflow.

        :param wf_ex_id: Execution id.
        :param env: Workflow environment.
        :return: Workflow execution object.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def rerun_workflow(self, task_ex_id, reset=True, env=None):
        """Rerun workflow from the specified task.

        :param task_ex_id: Task execution id.
        :param reset: If True, reset task state including deleting its action
            executions.
        :param env: Workflow environment.
        :return: Workflow execution object.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def stop_workflow(self, wf_ex_id, state, message):
        """Stops workflow.

        :param wf_ex_id: Workflow execution id.
        :param state: State assigned to the workflow. Permitted states are
            SUCCESS or ERROR.
        :param message: Optional information string.

        :return: Workflow execution.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def rollback_workflow(self, wf_ex_id):
        """Rolls back workflow execution.

        :param wf_ex_id: Execution id.
        :return: Workflow execution object.
        """
        raise NotImplementedError


@six.add_metaclass(abc.ABCMeta)
class Executor(object):
    """Action executor interface."""

    @abc.abstractmethod
    def run_action(self, action_ex_id, action_class_str, attributes,
                   action_params, safe_rerun, redelivered=False):
        """Runs action.

        :param action_ex_id: Corresponding action execution id.
        :param action_class_str: Path to action class in dot notation.
        :param attributes: Attributes of action class which will be set to.
        :param action_params: Action parameters.
        :param safe_rerun: Tells if given action can be safely rerun.
        :param redelivered: Tells if given action was run before on another
            executor.
        """
        raise NotImplementedError()


@six.add_metaclass(abc.ABCMeta)
class EventEngine(object):
    """Action event trigger interface."""

    @abc.abstractmethod
    def create_event_trigger(self, trigger, events):
        raise NotImplementedError()

    @abc.abstractmethod
    def delete_event_trigger(self, trigger, events):
        raise NotImplementedError()


@six.add_metaclass(abc.ABCMeta)
class TaskPolicy(object):
    """Task policy.

    Provides interface to perform any work after a task has completed.
    An example of task policy may be 'retry' policy that makes engine
    to run a task repeatedly if it finishes with a failure.
    """
    _schema = {}

    def before_task_start(self, task_ex, task_spec):
        """Called right before task start.

        :param task_ex: DB model for task that is about to start.
        :param task_spec: Task specification.
        """
        wf_ex = task_ex.workflow_execution

        ctx_view = data_flow.ContextView(
            task_ex.in_context,
            wf_ex.context,
            wf_ex.input
        )

        data_flow.evaluate_object_fields(self, ctx_view)

        self._validate()

    def after_task_complete(self, task_ex, task_spec):
        """Called right after task completes.

        :param task_ex: Completed task DB model.
        :param task_spec: Completed task specification.
        """
        wf_ex = task_ex.workflow_execution

        ctx_view = data_flow.ContextView(
            task_ex.in_context,
            wf_ex.context,
            wf_ex.input
        )

        data_flow.evaluate_object_fields(self, ctx_view)

        self._validate()

    def _validate(self):
        """Validation of types after YAQL evaluation."""
        props = inspect_utils.get_public_fields(self)

        try:
            jsonschema.validate(props, self._schema)
        except Exception as e:
            raise exc.InvalidModelException(
                "Invalid data type in %s: %s. Value(s) can be shown after "
                "YAQL evaluating. If you use YAQL here, please correct it."
                % (self.__class__.__name__, e.message)
            )
