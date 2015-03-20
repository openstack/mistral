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

from mistral import expressions as expr
from mistral.openstack.common import log as logging
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
        return filter(
            lambda t_e: self._is_upstream_task_execution(task_spec, t_e),
            wf_utils.find_task_executions(
                self.wf_ex,
                self._find_inbound_task_specs(task_spec)
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

    def _find_next_commands(self):
        cmds = super(DirectWorkflowController, self)._find_next_commands()

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
        t_specs = []

        for t_s in self.wf_spec.get_tasks():
            if not self._has_inbound_transitions(t_s):
                t_specs.append(t_s)

        return [
            commands.RunTask(
                self.wf_ex,
                t_s,
                self._get_task_inbound_context(t_s)
            )
            for t_s in t_specs
        ]

    def _find_next_commands_for_task(self, task_ex):
        """Finds next commands based on the state of the given task.

        :param task_ex: Task execution for which next commands need
            to be found.
        :return: List of workflow commands.
        """

        ctx = data_flow.evaluate_task_outbound_context(task_ex)

        cmds = []

        for t_n in self._find_next_task_names(task_ex, ctx):
            # If t_s is None we assume that it's one of the reserved
            # engine commands and in this case we pass the parent task
            # specification and it's inbound context.
            t_s = (
                self.wf_spec.get_tasks()[t_n]
                or
                self.wf_spec.get_tasks()[task_ex.name]
            )

            cmds.append(
                commands.create_command(
                    t_n,
                    self.wf_ex,
                    t_s,
                    self._get_task_inbound_context(t_s)
                )
            )

        LOG.debug("Found commands: %s" % cmds)

        # We need to remove all "join" tasks that have already started
        # (or even completed) to prevent running "join" tasks more than
        # once.
        cmds = self._remove_started_joins(cmds)

        return self._remove_unsatisfied_joins(cmds)

    def _has_inbound_transitions(self, task_spec):
        return len(self._find_inbound_task_specs(task_spec)) > 0

    def _find_inbound_task_specs(self, task_spec):
        return [
            t_s for t_s in self.wf_spec.get_tasks()
            if self._transition_exists(t_s.get_name(), task_spec.get_name())
        ]

    def _find_outbound_task_specs(self, task_spec):
        return [
            t_s for t_s in self.wf_spec.get_tasks()
            if self._transition_exists(task_spec.get_name(), t_s.get_name())
        ]

    def _transition_exists(self, from_task_name, to_task_name):
        t_names = set()

        for tup in self.get_on_error_clause(from_task_name):
            t_names.add(tup[0])

        for tup in self.get_on_success_clause(from_task_name):
            t_names.add(tup[0])

        for tup in self.get_on_complete_clause(from_task_name):
            t_names.add(tup[0])

        return to_task_name in t_names

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

    def all_errors_handled(self):
        for t_ex in wf_utils.find_error_tasks(self.wf_ex):
            if not self.get_on_error_clause(t_ex.name):
                return False

        return True

    def _find_end_tasks(self):
        return filter(
            lambda t_db: not self._has_outbound_tasks(t_db),
            wf_utils.find_successful_tasks(self.wf_ex)
        )

    def _has_outbound_tasks(self, task_ex):
        t_specs = self._find_outbound_task_specs(
            self.wf_spec.get_tasks()[task_ex.name]
        )

        return any(
            [wf_utils.find_task_execution(self.wf_ex, t_s) for t_s in t_specs]
        )

    @staticmethod
    def _remove_task_from_clause(on_clause, t_name):
        return filter(lambda tup: tup[0] != t_name, on_clause)

    def get_on_error_clause(self, t_name):
        result = self.wf_spec.get_tasks()[t_name].get_on_error()

        if not result:
            task_defaults = self.wf_spec.get_task_defaults()

            if task_defaults:
                result = self._remove_task_from_clause(
                    task_defaults.get_on_error(),
                    t_name
                )

        return result

    def get_on_success_clause(self, t_name):
        result = self.wf_spec.get_tasks()[t_name].get_on_success()

        if not result:
            task_defaults = self.wf_spec.get_task_defaults()

            if task_defaults:
                result = self._remove_task_from_clause(
                    task_defaults.get_on_success(),
                    t_name
                )

        return result

    def get_on_complete_clause(self, t_name):
        result = self.wf_spec.get_tasks()[t_name].get_on_complete()

        if not result:
            task_defaults = self.wf_spec.get_task_defaults()

            if task_defaults:
                result = self._remove_task_from_clause(
                    task_defaults.get_on_complete(),
                    t_name
                )

        return result

    def _find_next_task_names(self, task_ex, ctx):
        t_state = task_ex.state
        t_name = task_ex.name

        t_names = []

        if states.is_completed(t_state):
            t_names += self._find_next_task_names_for_clause(
                self.get_on_complete_clause(t_name),
                ctx
            )

        if t_state == states.ERROR:
            t_names += self._find_next_task_names_for_clause(
                self.get_on_error_clause(t_name),
                ctx
            )

        elif t_state == states.SUCCESS:
            t_names += self._find_next_task_names_for_clause(
                self.get_on_success_clause(t_name),
                ctx
            )

        return t_names

    @staticmethod
    def _find_next_task_names_for_clause(clause, ctx):
        """Finds next task(command) names base on given {name: condition}
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
            t_name
            for t_name, condition in clause
            if not condition or expr.evaluate(condition, ctx)
        ]

    def _remove_started_joins(self, cmds):
        return filter(lambda cmd: not self._is_started_join(cmd), cmds)

    def _is_started_join(self, cmd):
        if not isinstance(cmd, commands.RunTask):
            return False

        return (cmd.task_spec.get_join()
                and wf_utils.find_task_execution(self.wf_ex, cmd.task_spec))

    def _remove_unsatisfied_joins(self, cmds):
        return filter(lambda cmd: not self._is_unsatisfied_join(cmd), cmds)

    def _is_unsatisfied_join(self, cmd):
        if not isinstance(cmd, commands.RunTask):
            return False

        task_spec = cmd.task_spec

        join_expr = task_spec.get_join()

        if not join_expr:
            return False

        in_task_specs = self._find_inbound_task_specs(task_spec)

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

    def _triggers_join(self, join_task_spec, inbound_task_spec):
        in_t_ex = wf_utils.find_task_execution(self.wf_ex, inbound_task_spec)

        if not in_t_ex or not states.is_completed(in_t_ex.state):
            return False

        return filter(
            lambda t_name: join_task_spec.get_name() == t_name,
            self._find_next_task_names(
                in_t_ex,
                data_flow.evaluate_task_outbound_context(in_t_ex))
        )
