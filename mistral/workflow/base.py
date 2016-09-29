# Copyright 2014 - Mirantis, Inc.
# Copyright 2015 - StackStorm, Inc.
# Copyright 2015 - Huawei Technologies Co. Ltd
# Copyright 2016 - Brocade Communications Systems, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
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

from oslo_log import log as logging
from osprofiler import profiler

from mistral import exceptions as exc
from mistral import utils as u
from mistral.workbook import parser as spec_parser
from mistral.workflow import commands
from mistral.workflow import data_flow
from mistral.workflow import lookup_utils
from mistral.workflow import states


LOG = logging.getLogger(__name__)


@profiler.trace('wf-controller-get-controller')
def get_controller(wf_ex, wf_spec=None):
    """Gets a workflow controller instance by given workflow execution object.

    :param wf_ex: Workflow execution object.
    :param wf_spec: Workflow specification object. If passed, the method works
        faster.
    :returns: Workflow controller class.
    """

    if not wf_spec:
        wf_spec = spec_parser.get_workflow_spec_by_execution_id(wf_ex.id)

    wf_type = wf_spec.get_type()

    ctrl_cls = None

    for cls in u.iter_subclasses(WorkflowController):
        if cls.__workflow_type__ == wf_type:
            ctrl_cls = cls
            break

    if not ctrl_cls:
        raise exc.MistralError(
            'Failed to find a workflow controller [type=%s]' % wf_type
        )

    return ctrl_cls(wf_ex, wf_spec)


class WorkflowController(object):
    """Workflow Controller base class.

    Different workflow controllers implement different workflow algorithms.
    In practice it may actually mean that there may be multiple ways of
    describing workflow models (and even languages) that will be supported
    by Mistral.
    """

    def __init__(self, wf_ex, wf_spec=None):
        """Creates a new workflow controller.

        :param wf_ex: Workflow execution.

        :param wf_spec: Workflow specification.
        """
        self.wf_ex = wf_ex

        if wf_spec is None:
            wf_spec = spec_parser.get_workflow_spec_by_execution_id(wf_ex.id)

        self.wf_spec = wf_spec

    @profiler.trace('workflow-controller-continue-workflow')
    def continue_workflow(self, task_ex=None):
        """Calculates a list of commands to continue the workflow.

        Given a workflow specification this method makes required analysis
        according to this workflow type rules and identifies a list of
        commands needed to continue the workflow.

        :param task_ex: Task execution that caused workflow continuation.
            Optional. If not specified, it means that no certain task caused
            this operation (e.g. workflow has been just started or resumed
            manually).
        :return: List of workflow commands (instances of
            mistral.workflow.commands.WorkflowCommand).
        """

        if self._is_paused_or_completed():
            return []

        return self._find_next_commands(task_ex)

    def rerun_tasks(self, task_execs, reset=True):
        """Gets commands to rerun existing task executions.

        :param task_execs: List of task executions.
        :param reset: If true, then purge action executions for the tasks.
        :return: List of workflow commands.
        """
        if self._is_paused_or_completed():
            return []

        cmds = [
            commands.RunExistingTask(self.wf_ex, self.wf_spec, t_e, reset)
            for t_e in task_execs
        ]

        LOG.debug("Commands to rerun workflow tasks: %s" % cmds)

        return cmds

    @abc.abstractmethod
    def get_logical_task_state(self, task_ex):
        """Determines a logical state of the given task.

        :param task_ex: Task execution.
        :return: Tuple (state, state_info, cardinality) where 'state' and
            'state_info' are the corresponding values which the given
             task should have according to workflow rules and current
            states of other tasks. 'cardinality' gives the estimation on
            the number of preconditions that are not yet met in case if
            state is WAITING. This number can be used to estimate how
            frequently we can refresh the state of this task.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def is_error_handled_for(self, task_ex):
        """Determines if error is handled for specific task.

        :param task_ex: Task execution.
        :return: True if either there is no error at all or
            error is considered handled.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def all_errors_handled(self):
        """Determines if all errors (if any) are handled.

        :return: True if either there aren't errors at all or all
            errors are considered handled.
        """
        raise NotImplementedError

    def any_cancels(self):
        """Determines if there are any task cancellations.

        :return: True if there is one or more tasks in cancelled state.
        """
        t_execs = lookup_utils.find_cancelled_task_executions(self.wf_ex.id)

        return len(t_execs) > 0

    @abc.abstractmethod
    def evaluate_workflow_final_context(self):
        """Evaluates final workflow context assuming that workflow has finished.

        :return: Final workflow context.
        """
        raise NotImplementedError

    def get_task_inbound_context(self, task_spec):
        # TODO(rakhmerov): This method should also be able to work with task_ex
        # to cover 'split' (aka 'merge') use case.
        upstream_task_execs = self._get_upstream_task_executions(task_spec)

        return data_flow.evaluate_upstream_context(upstream_task_execs)

    @abc.abstractmethod
    def _get_upstream_task_executions(self, task_spec):
        """Gets workflow upstream tasks for the given task.

        :param task_spec: Task specification.
        :return: List of upstream task executions for the given task spec.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def _find_next_commands(self, task_ex):
        """Finds commands that should run next.

        A concrete algorithm of finding such tasks depends on a concrete
        workflow controller.

        :return: List of workflow commands.
        """

        # If task execution was passed then we should make all calculations
        # only based on it.
        if task_ex:
            return []

        # Add all tasks in IDLE state.
        idle_tasks = lookup_utils.find_task_executions_with_state(
            self.wf_ex.id,
            states.IDLE
        )

        return [
            commands.RunExistingTask(self.wf_ex, self.wf_spec, t)
            for t in idle_tasks
        ]

    def _is_paused_or_completed(self):
        return states.is_paused_or_completed(self.wf_ex.state)
