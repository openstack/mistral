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

from mistral.engine1 import commands
from mistral import expressions as expr
from mistral.openstack.common import log as logging
from mistral.workflow import base
from mistral.workflow import data_flow
from mistral.workflow import states
from mistral.workflow import utils as wf_utils


LOG = logging.getLogger(__name__)


class DirectWorkflowHandler(base.WorkflowHandler):
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

    def start_workflow(self, **params):
        self._set_execution_state(states.RUNNING)

        return self._find_start_commands()

    def get_upstream_tasks(self, task_spec):
        # TODO(rakhmerov): Temporary solution, account conditions.
        return self._find_inbound_task_specs(task_spec)

    def _find_start_commands(self):
        start_task_specs = []

        for t_s in self.wf_spec.get_tasks():
            if not self._has_inbound_transitions(t_s):
                start_task_specs.append(t_s)

        return [commands.RunTask(t_s) for t_s in start_task_specs]

    def _has_inbound_transitions(self, task_spec):
        for t_s in self.wf_spec.get_tasks():
            if self._transition_exists(t_s.get_name(), task_spec.get_name()):
                return True

        return False

    def _find_inbound_task_specs(self, task_spec):
        return [
            t_s for t_s in self.wf_spec.get_tasks()
            if self._transition_exists(t_s.get_name(), task_spec.get_name())
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

    def _find_next_commands(self, task_db, remove_unsatisfied_joins=True):
        """Finds commands that should run after completing given task.

        Expression 'on_complete' is not mutually exclusive to 'on_success'
         and 'on_error'.
        :param task_db: Task DB model.
        :param remove_unsatisfied_joins: True if incomplete "join"
            tasks must be excluded from the list of commands.
        :return: List of task specifications.
        """
        cmds = []

        t_name = task_db.name
        t_state = task_db.state

        ctx = data_flow.evaluate_outbound_context(task_db)

        if states.is_completed(t_state):
            on_complete = self.get_on_complete_clause(t_name)

            if on_complete:
                cmds += self._get_next_commands(on_complete, ctx)

        if t_state == states.ERROR:
            on_error = self.get_on_error_clause(t_name)

            if on_error:
                cmds += self._get_next_commands(on_error, ctx)

        elif t_state == states.SUCCESS:
            on_success = self.get_on_success_clause(t_name)

            if on_success:
                cmds += self._get_next_commands(on_success, ctx)

        LOG.debug("Found commands: %s" % cmds)

        # We need to remove all "join" tasks that have already started
        # (or even completed) to prevent running "join" tasks more than
        # once.
        cmds = self._remove_started_joins(cmds)

        if remove_unsatisfied_joins:
            return self._remove_unsatisfied_joins(cmds)
        else:
            return cmds

    def _is_error_handled(self, task_db):
        return self.get_on_error_clause(task_db.name)

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

    def _get_next_commands(self, cmd_conditions, ctx):
        cmds = []

        for t_name, condition in cmd_conditions:
            if not condition or expr.evaluate(condition, ctx):
                cmds.append(self._build_command(t_name))

        return cmds

    def _build_command(self, cmd_name):
        cmd = commands.get_reserved_command(cmd_name)

        return cmd or commands.RunTask(self.wf_spec.get_tasks()[cmd_name])

    def _remove_started_joins(self, cmds):
        return filter(lambda cmd: not self._is_started_join(cmd), cmds)

    def _is_started_join(self, cmd):
        if not isinstance(cmd, commands.RunTask):
            return False

        return (cmd.task_spec.get_join()
                and wf_utils.find_db_task(self.exec_db, cmd.task_spec))

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
        in_t_db = wf_utils.find_db_task(self.exec_db, inbound_task_spec)

        if not in_t_db or not states.is_completed(in_t_db.state):
            return False

        def is_join_task(cmd):
            return (isinstance(cmd, commands.RunTask)
                    and cmd.task_spec == join_task_spec)

        return filter(
            lambda cmd: is_join_task(cmd),
            self._find_next_commands(in_t_db, False)
        )
