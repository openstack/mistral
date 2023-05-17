# Copyright 2014 - Mirantis, Inc.
# Copyright 2017 - Brocade Communications Systems, Inc.
# Copyright 2020 Nokia Software.
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

from mistral import exceptions as exc
from mistral import utils

from mistral_lib.utils import inspect_utils


class Engine(object, metaclass=abc.ABCMeta):
    """Engine interface."""

    @abc.abstractmethod
    def start_workflow(self, wf_identifier, wf_namespace='', wf_ex_id=None,
                       wf_input=None, description='', async_=False, **params):
        """Starts the specified workflow.

        :param wf_identifier: Workflow ID or name. Workflow ID is recommended,
            workflow name will be deprecated since Mitaka.
        :param wf_namespace: Workflow namespace.
        :param wf_input: Workflow input data as a dictionary.
        :param wf_ex_id: Workflow execution id. If passed, it will be set
            in the new execution object.
        :param description: Execution description.
        :param async_: If True, start workflow in asynchronous mode
            (w/o waiting for completion).
        :param params: Additional workflow type specific parameters.
        :return: Workflow execution object.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def start_task(self, task_ex_id, first_run, waiting,
                   triggered_by, rerun, reset, **params):
        """Starts task sending a request to engine over RPC.

        """
        raise NotImplementedError

    @abc.abstractmethod
    def start_action(self, action_name, action_input,
                     description=None, namespace='', **params):
        """Starts the specific action.

        :param action_name: Action name.
        :param action_input: Action input data as a dictionary.
        :param description: Execution description.
        :param namespace: The namespace of the action.
        :param params: Additional options for action running.
        :return: Action execution object.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def on_action_complete(self, action_ex_id, result, wf_action=False,
                           async_=False):
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
        :param async: If True, run action in asynchronous mode (w/o waiting
            for completion).
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
    def rerun_workflow(self, task_ex_id, reset=True, skip=False, env=None):
        """Rerun workflow from the specified task.

        :param task_ex_id: Task execution id.
        :param reset: If True, reset task state including deleting its action
            executions.
        :param skip: If True, then skip failed task and continue workflow
            execution.
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

    @abc.abstractmethod
    def process_action_heartbeats(self, action_ex_ids):
        """Receives the heartbeat about the running actions.

        :param action_ex_ids: The action execution ids.
        """
        raise NotImplementedError


class TaskPolicy(object, metaclass=abc.ABCMeta):
    """Task policy.

    Provides interface to perform any work after a task has completed.
    An example of task policy may be 'retry' policy that makes engine
    to run a task repeatedly if it finishes with a failure.
    """
    _schema = {}

    def before_task_start(self, task):
        """Called right before task start.

        :param task: Engine task. Instance of engine.tasks.Task.
        """
        utils.evaluate_object_fields(self, task.get_expression_context())

        self._validate()

    def after_task_complete(self, task):
        """Called right after task completes.

        :param task: Engine task. Instance of engine.tasks.Task.
        """
        utils.evaluate_object_fields(self, task.get_expression_context())

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
                % (self.__class__.__name__, str(e))
            )
