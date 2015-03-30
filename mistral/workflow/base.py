# Copyright 2014 - Mirantis, Inc.
# Copyright 2015 - StackStorm, Inc.
# Copyright 2015 - Huawei Technologies Co. Ltd
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
import copy

from mistral import exceptions as exc
from mistral.openstack.common import log as logging
from mistral import utils as u
from mistral.workbook import parser as spec_parser
from mistral.workflow import commands
from mistral.workflow import data_flow
from mistral.workflow import states
from mistral.workflow import utils as wf_utils


LOG = logging.getLogger(__name__)


class WorkflowController(object):
    """Workflow Controller base class.

    Different workflow controllers implement different workflow algorithms.
    In practice it may actually mean that there may be multiple ways of
    describing workflow models (and even languages) that will be supported
    by Mistral.
    """

    def __init__(self, wf_ex):
        """Creates a new workflow controller.

        :param wf_ex: Workflow execution.
        """
        self.wf_ex = wf_ex
        self.wf_spec = spec_parser.get_workflow_spec(wf_ex.spec)

    def continue_workflow(self):
        """Calculates a list of commands to continue the workflow.

        Given a workflow specification this method makes required analysis
        according to this workflow type rules and identifies a list of
        commands needed to continue the workflow.
        :return: List of workflow commands (instances of
            mistral.workflow.commands.WorkflowCommand).
        """
        if self._is_paused_or_completed():
            return []

        return self._find_next_commands()

    @abc.abstractmethod
    def all_errors_handled(self):
        """Determines if all errors (if any) are handled.

        :return: True if either there aren't errors at all or all
            errors are considered handled.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def evaluate_workflow_final_context(self):
        """Evaluates final workflow context assuming that workflow has finished.

        :return: Final workflow context.
        """
        raise NotImplementedError

    def _get_task_inbound_context(self, task_spec):
        upstream_task_execs = self._get_upstream_task_executions(task_spec)

        return u.merge_dicts(
            copy.copy(self.wf_ex.context),
            data_flow.evaluate_upstream_context(upstream_task_execs)
        )

    @abc.abstractmethod
    def _get_upstream_task_executions(self, task_spec):
        """Gets workflow upstream tasks for the given task.

        :param task_spec: Task specification.
        :return: List of upstream task executions for the given task spec.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def _find_next_commands(self):
        """Finds commands that should run next.

        A concrete algorithm of finding such tasks depends on a concrete
        workflow controller.
        :return: List of workflow commands.
        """
        # Add all tasks in IDLE state.
        idle_tasks = wf_utils.find_tasks_with_state(self.wf_ex, states.IDLE)

        return [commands.RunExistingTask(t) for t in idle_tasks]

    def _is_paused_or_completed(self):
        return states.is_paused_or_completed(self.wf_ex.state)

    @staticmethod
    def _get_class(wf_type):
        """Gets a workflow controller class by given workflow type.

        :param wf_type: Workflow type.
        :returns: Workflow controller class.
        """
        for wf_ctrl_cls in u.iter_subclasses(WorkflowController):
            if wf_type == wf_ctrl_cls.__workflow_type__:
                return wf_ctrl_cls

        msg = 'Failed to find a workflow controller [type=%s]' % wf_type
        raise exc.NotFoundException(msg)

    @staticmethod
    def get_controller(wf_ex, wf_spec=None):
        if not wf_spec:
            wf_spec = spec_parser.get_workflow_spec(wf_ex['spec'])

        ctrl_cls = WorkflowController._get_class(wf_spec.get_type())

        return ctrl_cls(wf_ex)
