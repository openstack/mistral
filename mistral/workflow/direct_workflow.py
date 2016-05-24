# Copyright 2015 - Mirantis, Inc.
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

from oslo_log import log as logging

from mistral import exceptions as exc
from mistral import expressions as expr
from mistral import utils
from mistral.workflow import base
from mistral.workflow import commands
from mistral.workflow import data_flow
from mistral.workflow import states
from mistral.workflow import utils as wf_utils


LOG = logging.getLogger(__name__)


class DirectWorkflowController(base.WorkflowController):
    """'Direct workflow' handler.

    This handler implements the workflow pattern which is based on
    direct transitions between tasks, i.e. after each task completion
    a decision should be made which tasks should run next based on
    result of task execution.
    Note, that tasks can run in parallel. For example, if there's a workflow
    consisting of three tasks 'A', 'B' and 'C' where 'A' starts first then
    'B' and 'C' can start second if certain associated with transition
    'A'->'B' and 'A'->'C' evaluate to true.
    """

    __workflow_type__ = "direct"

    def _get_upstream_task_executions(self, task_spec):
        return list(
            filter(
                lambda t_e: self._is_upstream_task_execution(task_spec, t_e),
                wf_utils.find_task_executions_by_specs(
                    self.wf_ex,
                    self.wf_spec.find_inbound_task_specs(task_spec)
                )
            )
        )

    def _is_upstream_task_execution(self, t_spec, t_ex_candidate):
        if not states.is_completed(t_ex_candidate.state):
            return False

        if not t_spec.get_join():
            return not t_ex_candidate.processed

        return self._triggers_join(
            t_spec,
            self.wf_spec.get_tasks()[t_ex_candidate.name]
        )

    def _find_next_commands(self, env=None):
        cmds = super(DirectWorkflowController, self)._find_next_commands(
            env=env
        )

        if not self.wf_ex.task_executions:
            return self._find_start_commands()

        task_execs = [
            t_ex for t_ex in self.wf_ex.task_executions
            if states.is_completed(t_ex.state) and not t_ex.processed
        ]

        for t_ex in task_execs:
            cmds.extend(self._find_next_commands_for_task(t_ex))

        return cmds

    def _find_start_commands(self):
        return [
            commands.RunTask(
                self.wf_ex,
                t_s,
                self._get_task_inbound_context(t_s)
            )
            for t_s in self.wf_spec.find_start_tasks()
        ]

    def _find_next_commands_for_task(self, task_ex):
        """Finds next commands based on the state of the given task.

        :param task_ex: Task execution for which next commands need
            to be found.
        :return: List of workflow commands.
        """

        cmds = []

        for t_n, params in self._find_next_tasks(task_ex):
            t_s = self.wf_spec.get_tasks()[t_n]

            if not (t_s or t_n in commands.RESERVED_CMDS):
                raise exc.WorkflowException("Task '%s' not found." % t_n)
            elif not t_s:
                t_s = self.wf_spec.get_tasks()[task_ex.name]

            cmd = commands.create_command(
                t_n,
                self.wf_ex,
                t_s,
                self._get_task_inbound_context(t_s),
                params
            )

            # NOTE(xylan): Decide whether or not a join task should run
            # immediately.
            if self._is_unsatisfied_join(cmd):
                cmd.wait = True

            cmds.append(cmd)

        # We need to remove all "join" tasks that have already started
        # (or even completed) to prevent running "join" tasks more than
        # once.
        cmds = self._remove_started_joins(cmds)

        LOG.debug("Found commands: %s" % cmds)

        return cmds

    # TODO(rakhmerov): Need to refactor this method to be able to pass tasks
    # whose contexts need to be merged.
    def evaluate_workflow_final_context(self):
        ctx = {}

        for t_ex in self._find_end_tasks():
            ctx = utils.merge_dicts(
                ctx,
                data_flow.evaluate_task_outbound_context(t_ex)
            )

        return ctx

    def is_error_handled_for(self, task_ex):
        return bool(self.wf_spec.get_on_error_clause(task_ex.name))

    def all_errors_handled(self):
        for t_ex in wf_utils.find_error_task_executions(self.wf_ex):

            tasks_on_error = self._find_next_tasks_for_clause(
                self.wf_spec.get_on_error_clause(t_ex.name),
                data_flow.evaluate_task_outbound_context(t_ex)
            )

            if not tasks_on_error:
                return False

        return True

    def _find_end_tasks(self):
        return list(
            filter(
                lambda t_ex: not self._has_outbound_tasks(t_ex),
                wf_utils.find_successful_task_executions(self.wf_ex)
            )
        )

    def _has_outbound_tasks(self, task_ex):
        # In order to determine if there are outbound tasks we just need
        # to calculate next task names (based on task outbound context)
        # and remove all engine commands. To do the latter it's enough to
        # check if there's a corresponding task specification for a task name.
        return bool([
            t_name for t_name in self._find_next_task_names(task_ex)
            if self.wf_spec.get_tasks()[t_name]
        ])

    def _find_next_task_names(self, task_ex):
        return [t[0] for t in self._find_next_tasks(task_ex)]

    def _find_next_tasks(self, task_ex):
        t_state = task_ex.state
        t_name = task_ex.name

        ctx = data_flow.evaluate_task_outbound_context(task_ex)

        t_names_and_params = []

        if states.is_completed(t_state):
            t_names_and_params += (
                self._find_next_tasks_for_clause(
                    self.wf_spec.get_on_complete_clause(t_name),
                    ctx
                )
            )

        if t_state == states.ERROR:
            t_names_and_params += (
                self._find_next_tasks_for_clause(
                    self.wf_spec.get_on_error_clause(t_name),
                    ctx
                )
            )

        elif t_state == states.SUCCESS:
            t_names_and_params += (
                self._find_next_tasks_for_clause(
                    self.wf_spec.get_on_success_clause(t_name),
                    ctx
                )
            )

        return t_names_and_params

    @staticmethod
    def _find_next_tasks_for_clause(clause, ctx):
        """Finds next tasks names.

         This method finds next task(command) base on given {name: condition}
         dictionary.

        :param clause: Dictionary {task_name: condition} taken from
            'on-complete', 'on-success' or 'on-error' clause.
        :param ctx: Context that clause expressions should be evaluated
            against of.
        :return: List of task(command) names.
        """
        if not clause:
            return []

        return [
            (t_name, expr.evaluate_recursively(params, ctx))
            for t_name, condition, params in clause
            if not condition or expr.evaluate(condition, ctx)
        ]

    def _remove_started_joins(self, cmds):
        return list(
            filter(lambda cmd: not self._is_started_join(cmd), cmds)
        )

    def _is_started_join(self, cmd):
        if not (isinstance(cmd, commands.RunTask) and
                cmd.task_spec.get_join()):
            return False

        return wf_utils.find_task_execution_not_state(
            self.wf_ex,
            cmd.task_spec,
            states.WAITING
        )

    def _is_unsatisfied_join(self, cmd):
        if not isinstance(cmd, commands.RunTask):
            return False

        task_spec = cmd.task_spec

        join_expr = task_spec.get_join()

        if not join_expr:
            return False

        in_task_specs = self.wf_spec.find_inbound_task_specs(task_spec)

        if not in_task_specs:
            return False

        # We need to count a number of triggering inbound transitions.
        num = len([1 for in_t_s in in_task_specs
                   if self._triggers_join(task_spec, in_t_s)])

        # If "join" is configured as a number.
        if isinstance(join_expr, int) and num < join_expr:
            return True

        if join_expr == 'all' and len(in_task_specs) > num:
            return True

        if join_expr == 'one' and num == 0:
            return True

        return False

    # TODO(rakhmerov): Method signature is incorrect given that
    # we may have multiple task executions for a task. It should
    # accept inbound task execution rather than a spec.
    def _triggers_join(self, join_task_spec, inbound_task_spec):
        in_t_execs = wf_utils.find_task_executions_by_spec(
            self.wf_ex,
            inbound_task_spec
        )

        # TODO(rakhmerov): Temporary hack. See the previous comment.
        in_t_ex = in_t_execs[-1] if in_t_execs else None

        if not in_t_ex or not states.is_completed(in_t_ex.state):
            return False

        return list(
            filter(
                lambda t_name: join_task_spec.get_name() == t_name,
                self._find_next_task_names(in_t_ex)
            )
        )
