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
        # TODO(rakhmerov): For direct workflow it's pretty hard to do
        #  so we may need to get rid of it at all.
        return []

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

    def _transition_exists(self, from_task_name, to_task_name):
        t_names = set()

        for tup in self.get_on_error_clause(from_task_name):
            t_names.add(tup[0])

        for tup in self.get_on_success_clause(from_task_name):
            t_names.add(tup[0])

        for tup in self.get_on_complete_clause(from_task_name):
            t_names.add(tup[0])

        return to_task_name in t_names

    def _find_next_commands(self, task_db):
        """Finds commands that should run after completing given task.

        Expression 'on_complete' is not mutually exclusive to 'on_success'
         and 'on_error'.
        :param task_db: Task DB model.
        :return: List of task specifications.
        """
        commands = []

        t_name = task_db.name
        t_state = task_db.state

        ctx = data_flow.evaluate_outbound_context(task_db)

        if states.is_finished(t_state):
            on_complete = self.get_on_complete_clause(t_name)

            if on_complete:
                commands += self._get_next_commands(on_complete, ctx)

        if t_state == states.ERROR:
            on_error = self.get_on_error_clause(t_name)

            if on_error:
                commands += self._get_next_commands(on_error, ctx)

        elif t_state == states.SUCCESS:
            on_success = self.get_on_success_clause(t_name)

            if on_success:
                commands += self._get_next_commands(on_success, ctx)

        LOG.debug("Found commands: %s" % commands)

        return commands

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
        commands = []

        for t_name, condition in cmd_conditions:
            if not condition or expr.evaluate(condition, ctx):
                commands.append(self.build_command(t_name))

        return commands

    def build_command(self, cmd_name):
        cmd = commands.get_reserved_command(cmd_name)

        return cmd or commands.RunTask(self.wf_spec.get_tasks()[cmd_name])
