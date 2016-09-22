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
from osprofiler import profiler

from mistral import exceptions as exc
from mistral import expressions as expr
from mistral import utils
from mistral.workflow import base
from mistral.workflow import commands
from mistral.workflow import data_flow
from mistral.workflow import lookup_utils
from mistral.workflow import states


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
                lookup_utils.find_task_executions_by_specs(
                    self.wf_ex.id,
                    self.wf_spec.find_inbound_task_specs(task_spec)
                )
            )
        )

    def _is_upstream_task_execution(self, t_spec, t_ex_candidate):
        if not states.is_completed(t_ex_candidate.state):
            return False

        if not t_spec.get_join():
            return not t_ex_candidate.processed

        induced_state, _ = self._get_induced_join_state(
            self.wf_spec.get_tasks()[t_ex_candidate.name],
            t_spec
        )

        return induced_state == states.RUNNING

    def _find_next_commands(self, task_ex=None):
        cmds = super(DirectWorkflowController, self)._find_next_commands(
            task_ex
        )

        # Checking if task_ex is empty here is a serious optimization here
        # because 'self.wf_ex.task_executions' leads to initialization of
        # the entire collection which in case of highly-parallel workflows
        # may be very expensive.
        if not task_ex and not self.wf_ex.task_executions:
            return self._find_start_commands()

        if task_ex:
            task_execs = [task_ex]
        else:
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
                self.wf_spec,
                t_s,
                self.get_task_inbound_context(t_s)
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

        ctx = data_flow.evaluate_task_outbound_context(task_ex)

        for t_n, params in self._find_next_tasks(task_ex):
            t_s = self.wf_spec.get_tasks()[t_n]

            if not (t_s or t_n in commands.RESERVED_CMDS):
                raise exc.WorkflowException("Task '%s' not found." % t_n)
            elif not t_s:
                t_s = self.wf_spec.get_tasks()[task_ex.name]

            cmd = commands.create_command(
                t_n,
                self.wf_ex,
                self.wf_spec,
                t_s,
                ctx,
                params
            )

            self._configure_if_join(cmd)

            cmds.append(cmd)

        LOG.debug("Found commands: %s" % cmds)

        return cmds

    def _configure_if_join(self, cmd):
        if not isinstance(cmd, commands.RunTask):
            return

        if not cmd.task_spec.get_join():
            return

        cmd.unique_key = self._get_join_unique_key(cmd)
        cmd.wait = True

    def _get_join_unique_key(self, cmd):
        return 'join-task-%s-%s' % (self.wf_ex.id, cmd.task_spec.get_name())

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

    def get_logical_task_state(self, task_ex):
        task_spec = self.wf_spec.get_tasks()[task_ex.name]

        if not task_spec.get_join():
            # A simple 'non-join' task does not have any preconditions
            # based on state of other tasks so its logical state always
            # equals to its real state.
            return task_ex.state, task_ex.state_info, 0

        return self._get_join_logical_state(task_spec)

    def is_error_handled_for(self, task_ex):
        return bool(self.wf_spec.get_on_error_clause(task_ex.name))

    def all_errors_handled(self):
        for t_ex in lookup_utils.find_error_task_executions(self.wf_ex.id):
            ctx_view = data_flow.ContextView(
                data_flow.evaluate_task_outbound_context(t_ex),
                self.wf_ex.context,
                self.wf_ex.input
            )

            tasks_on_error = self._find_next_tasks_for_clause(
                self.wf_spec.get_on_error_clause(t_ex.name),
                ctx_view
            )

            if not tasks_on_error:
                return False

        return True

    def _find_end_tasks(self):
        return list(
            filter(
                lambda t_ex: not self._has_outbound_tasks(t_ex),
                lookup_utils.find_successful_task_executions(self.wf_ex.id)
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

        ctx_view = data_flow.ContextView(
            data_flow.evaluate_task_outbound_context(task_ex),
            self.wf_ex.context,
            self.wf_ex.input
        )

        t_names_and_params = []

        if states.is_completed(t_state):
            t_names_and_params += (
                self._find_next_tasks_for_clause(
                    self.wf_spec.get_on_complete_clause(t_name),
                    ctx_view
                )
            )

        if t_state == states.ERROR:
            t_names_and_params += (
                self._find_next_tasks_for_clause(
                    self.wf_spec.get_on_error_clause(t_name),
                    ctx_view
                )
            )

        elif t_state == states.SUCCESS:
            t_names_and_params += (
                self._find_next_tasks_for_clause(
                    self.wf_spec.get_on_success_clause(t_name),
                    ctx_view
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

    @profiler.trace('direct-wf-controller-get-join-logical-state')
    def _get_join_logical_state(self, task_spec):
        """Evaluates logical state of 'join' task.

        :param task_spec: 'join' task specification.
        :return: Tuple (state, state_info, spec_cardinality) where 'state' and
            'state_info' describe the logical state of the given 'join'
            task and 'spec_cardinality' gives the remaining number of
            unfulfilled preconditions. If logical state is not WAITING then
            'spec_cardinality' should always be 0.
        """

        # TODO(rakhmerov): We need to use task_ex instead of task_spec
        # in order to cover a use case when there's more than one instance
        # of the same 'join' task in a workflow.
        # TODO(rakhmerov): In some cases this method will be expensive because
        # it uses a multistep recursive search. We need to optimize it moving
        # forward (e.g. with Workflow Execution Graph).

        join_expr = task_spec.get_join()

        in_task_specs = self.wf_spec.find_inbound_task_specs(task_spec)

        if not in_task_specs:
            return states.RUNNING, None, 0

        # List of tuples (task_name, (state, depth)).
        induced_states = [
            (t_s.get_name(), self._get_induced_join_state(t_s, task_spec))
            for t_s in in_task_specs
        ]

        def count(state):
            cnt = 0
            total_depth = 0

            for s in induced_states:
                if s[1][0] == state:
                    cnt += 1
                    total_depth += s[1][1]

            return cnt, total_depth

        errors_tuples = count(states.ERROR)
        runnings_tuple = count(states.RUNNING)
        total_count = len(induced_states)

        def _blocked_message():
            return (
                'Blocked by tasks: %s' %
                [s[0] for s in induced_states if s[1][0] == states.WAITING]
            )

        def _failed_message():
            return (
                'Failed by tasks: %s' %
                [s[0] for s in induced_states if s[1][0] == states.ERROR]
            )

        # If "join" is configured as a number or 'one'.
        if isinstance(join_expr, int) or join_expr == 'one':
            spec_cardinality = 1 if join_expr == 'one' else join_expr

            if runnings_tuple[0] >= spec_cardinality:
                return states.RUNNING, None, 0

            # E.g. 'join: 3' with inbound [ERROR, ERROR, RUNNING, WAITING]
            # No chance to get 3 RUNNING states.
            if errors_tuples[0] > (total_count - spec_cardinality):
                return states.ERROR, _failed_message(), 0

            # Calculate how many tasks need to finish to trigger this 'join'.
            cardinality = spec_cardinality - runnings_tuple[0]

            return states.WAITING, _blocked_message(), cardinality

        if join_expr == 'all':
            if total_count == runnings_tuple[0]:
                return states.RUNNING, None, 0

            if errors_tuples[0] > 0:
                return states.ERROR, _failed_message(), 0

            # Remaining cardinality is just a difference between all tasks and
            # a number of those tasks that induce RUNNING state.
            cardinality = total_count - runnings_tuple[1]

            return states.WAITING, _blocked_message(), cardinality

        raise RuntimeError('Unexpected join expression: %s' % join_expr)

    # TODO(rakhmerov): Method signature is incorrect given that
    # we may have multiple task executions for a task. It should
    # accept inbound task execution rather than a spec.
    def _get_induced_join_state(self, inbound_task_spec, join_task_spec):
        join_task_name = join_task_spec.get_name()

        in_task_ex = self._find_task_execution_by_name(
            inbound_task_spec.get_name()
        )

        if not in_task_ex:
            possible, depth = self._possible_route(inbound_task_spec)

            if possible:
                return states.WAITING, depth
            else:
                return states.ERROR, depth

        if not states.is_completed(in_task_ex.state):
            return states.WAITING, 1

        if join_task_name not in self._find_next_task_names(in_task_ex):
            return states.ERROR, 1

        return states.RUNNING, 1

    def _find_task_execution_by_name(self, t_name):
        # Note: in case of 'join' completion check it's better to initialize
        # the entire task_executions collection to avoid too many DB queries.
        t_execs = lookup_utils.find_task_executions_by_name(
            self.wf_ex.id,
            t_name
        )

        # TODO(rakhmerov): Temporary hack. See the previous comment.
        return t_execs[-1] if t_execs else None

    def _possible_route(self, task_spec, depth=1):
        in_task_specs = self.wf_spec.find_inbound_task_specs(task_spec)

        if not in_task_specs:
            return True, depth

        for t_s in in_task_specs:
            t_ex = self._find_task_execution_by_name(t_s.get_name())

            if not t_ex:
                if self._possible_route(t_s, depth + 1):
                    return True, depth
            else:
                t_name = task_spec.get_name()

                if (not states.is_completed(t_ex.state) or
                        t_name in self._find_next_task_names(t_ex)):
                    return True, depth

        return False, depth
