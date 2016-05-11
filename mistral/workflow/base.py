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

from oslo_log import log as logging

from mistral import exceptions as exc
from mistral import utils as u
from mistral.workbook import parser as spec_parser
from mistral.workflow import commands
from mistral.workflow import data_flow
from mistral.workflow import states
from mistral.workflow import utils as wf_utils


LOG = logging.getLogger(__name__)


def get_controller(wf_ex, wf_spec=None):
    """Gets a workflow controller instance by given workflow execution object.

    :param wf_ex: Workflow execution object.
    :param wf_spec: Workflow specification object. If passed, the method works
        faster.
    :returns: Workflow controller class.
    """

    if not wf_spec:
        wf_spec = spec_parser.get_workflow_spec(wf_ex['spec'])

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
            wf_spec = spec_parser.get_workflow_spec(wf_ex.spec)

        self.wf_spec = wf_spec

    @staticmethod
    def _update_task_ex_env(task_ex, env):
        if not env:
            return task_ex

        task_ex.in_context['__env'] = u.merge_dicts(
            task_ex.in_context['__env'],
            env
        )

        return task_ex

    def continue_workflow(self, task_ex=None, reset=True, env=None):
        """Calculates a list of commands to continue the workflow.

        Given a workflow specification this method makes required analysis
        according to this workflow type rules and identifies a list of
        commands needed to continue the workflow.

        :param task_ex: Task execution to rerun.
        :param reset: If true, then purge action executions for the tasks.
        :param env: A set of environment variables to overwrite.
        :return: List of workflow commands (instances of
            mistral.workflow.commands.WorkflowCommand).
        """
        if self._is_paused_or_completed():
            return []

        if task_ex:
            return self._get_rerun_commands([task_ex], reset, env=env)

        return self._find_next_commands(env=env)

    @abc.abstractmethod
    def is_error_handled_for(self, task_ex):
        """Determines if error is handled for specific task.

        :param task_ex: Task execution perform a check for.
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

    @abc.abstractmethod
    def evaluate_workflow_final_context(self):
        """Evaluates final workflow context assuming that workflow has finished.

        :return: Final workflow context.
        """
        raise NotImplementedError

    def _get_task_inbound_context(self, task_spec):
        upstream_task_execs = self._get_upstream_task_executions(task_spec)

        upstream_ctx = data_flow.evaluate_upstream_context(upstream_task_execs)

        ctx = u.merge_dicts(
            copy.deepcopy(self.wf_ex.context),
            upstream_ctx
        )

        if self.wf_ex.context:
            ctx['__env'] = u.merge_dicts(
                copy.deepcopy(upstream_ctx.get('__env', {})),
                copy.deepcopy(self.wf_ex.context.get('__env', {}))
            )

        return ctx

    @abc.abstractmethod
    def _get_upstream_task_executions(self, task_spec):
        """Gets workflow upstream tasks for the given task.

        :param task_spec: Task specification.
        :return: List of upstream task executions for the given task spec.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def _find_next_commands(self, env=None):
        """Finds commands that should run next.

        A concrete algorithm of finding such tasks depends on a concrete
        workflow controller.

        :param env: A set of environment variables to overwrite.
        :return: List of workflow commands.
        """
        # Add all tasks in IDLE state.
        idle_tasks = wf_utils.find_task_executions_with_state(
            self.wf_ex,
            states.IDLE
        )

        for task_ex in idle_tasks:
            self._update_task_ex_env(task_ex, env)

        return [commands.RunExistingTask(t) for t in idle_tasks]

    def _get_rerun_commands(self, task_exs, reset=True, env=None):
        """Get commands to rerun existing task executions.

        :param task_exs: List of task executions.
        :param reset: If true, then purge action executions for the tasks.
        :param env: A set of environment variables to overwrite.
        :return: List of workflow commands.
        """
        for task_ex in task_exs:
            self._update_task_ex_env(task_ex, env)

        cmds = [commands.RunExistingTask(t_e, reset) for t_e in task_exs]

        LOG.debug("Found commands: %s" % cmds)

        return cmds

    def _is_paused_or_completed(self):
        return states.is_paused_or_completed(self.wf_ex.state)
