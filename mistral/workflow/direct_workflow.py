# Copyright 2015 - Mirantis, Inc.
# Copyright 2020 - NetCracker Technology Corp.
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

from mistral.db.v2 import api as db_api
from mistral import exceptions as exc
from mistral import expressions as expr
from mistral.workflow import base
from mistral.workflow import commands
from mistral.workflow import data_flow
from mistral.workflow import states
from mistral_lib import utils


LOG = logging.getLogger(__name__)

MAX_SEARCH_DEPTH = 5


class DirectWorkflowController(base.WorkflowController):
    """'Direct workflow' controller.

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

    def _get_upstream_task_executions(self, task_spec, triggered_by=None):
        t_specs_names = [t_spec.get_name() for t_spec in
                         self.wf_spec.find_inbound_task_specs(task_spec)]

        if not t_specs_names:
            return []

        if not task_spec.get_join():
            if triggered_by and len(triggered_by) > 0:
                return self._get_task_executions(
                    name=t_specs_names[0],  # not a join, has just one parent
                    state={'in': (states.SUCCESS, states.ERROR,
                                  states.CANCELLED)},
                    id={'in': triggered_by},
                    processed=True
                )
            return self._get_task_executions(
                name=t_specs_names[0],  # not a join, has just one parent
                state={'in': (states.SUCCESS, states.ERROR, states.CANCELLED)},
                processed=True
            )

        t_execs_candidates = self._get_task_executions(
            name={'in': t_specs_names},
            state={'in': (states.SUCCESS, states.ERROR, states.CANCELLED)},
        )

        t_execs = []
        for t_ex in t_execs_candidates:
            if task_spec.get_name() in [t[0] for t in t_ex.next_tasks]:
                t_execs.append(t_ex)

        return t_execs

    def _find_next_commands(self, task_ex=None):
        cmds = super(DirectWorkflowController, self)._find_next_commands(
            task_ex
        )

        # Checking if task_ex is empty is a serious optimization here
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

    @profiler.trace(
        'direct-wf-controller-find-next-commands-for-task',
        hide_args=True
    )
    def _find_next_commands_for_task(self, task_ex):
        """Finds next commands based on the state of the given task.

        :param task_ex: Task execution for which next commands need
            to be found.
        :return: List of workflow commands.
        """

        cmds = []

        ctx = data_flow.evaluate_task_outbound_context(task_ex)

        for t_n, params, event_name in self._find_next_tasks(task_ex, ctx):
            t_s = self.wf_spec.get_tasks()[t_n]

            if not (t_s or t_n in commands.ENGINE_CMD_CLS):
                raise exc.WorkflowException("Task '%s' not found." % t_n)
            elif not t_s:
                t_s = self.wf_spec.get_task(task_ex.name)

            triggered_by = [
                {
                    'task_id': task_ex.id,
                    'event': event_name
                }
            ]

            cmd = commands.create_command(
                t_n,
                self.wf_ex,
                self.wf_spec,
                t_s,
                ctx,
                params=params,
                triggered_by=triggered_by,
                handles_error=(event_name == 'on-error')
            )

            self._configure_if_join(cmd)

            cmds.append(cmd)

        LOG.debug("Found commands: %s", cmds)

        return cmds

    def _configure_if_join(self, cmd):
        if not isinstance(cmd, (commands.RunTask, commands.RunExistingTask)):
            return

        if not cmd.task_spec.get_join():
            return

        cmd.unique_key = self._get_join_unique_key(cmd)
        cmd.wait = True

    def _get_join_unique_key(self, cmd):
        return 'join-task-%s-%s' % (self.wf_ex.id, cmd.task_spec.get_name())

    def rerun_tasks(self, task_execs, reset=True):
        cmds = super(DirectWorkflowController, self).rerun_tasks(
            task_execs,
            reset
        )

        for cmd in cmds:
            self._configure_if_join(cmd)

        return cmds

    # TODO(rakhmerov): Need to refactor this method to be able to pass tasks
    # whose contexts need to be merged.
    def evaluate_workflow_final_context(self):
        ctx = {}

        for batch in self._find_end_task_executions_as_batches():
            for t_ex in batch:
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
            return base.TaskLogicalState(task_ex.state, task_ex.state_info)

        return self._get_join_logical_state(task_spec)

    def find_indirectly_affected_task_executions(self, t_name):
        all_joins = {task_spec.get_name()
                     for task_spec in self.wf_spec.get_tasks()
                     if task_spec.get_join()}

        t_execs_cache = {
            t_ex.name: t_ex for t_ex in self._get_task_executions(
                fields=('id', 'name'),
                name={'in': all_joins}
            )
        } if all_joins else {}

        visited_task_names = set()
        clauses = self.wf_spec.find_outbound_task_names(t_name)

        res = set()

        while clauses:
            visited_task_names.add(t_name)
            t_name = clauses.pop()

            # Handle cycles.
            if t_name in visited_task_names:
                continue

            # Encountered an engine command.
            if not self.wf_spec.get_tasks()[t_name]:
                continue

            if t_name in all_joins and t_name in t_execs_cache:
                res.add(t_execs_cache[t_name])
                continue

            clauses.update(self.wf_spec.find_outbound_task_names(t_name))

        return res

    def is_error_handled_for(self, task_ex):
        # TODO(rakhmerov): The method works in a different way than
        # all_errors_handled(). It doesn't evaluate expressions under
        # "on-error" clause.
        return bool(self.wf_spec.get_on_error_clause(task_ex.name))

    def all_errors_handled(self):
        cnt = db_api.get_task_executions_count(
            workflow_execution_id=self.wf_ex.id,
            state=states.ERROR,
            error_handled=False
        )

        return cnt == 0

    def _find_end_task_executions_as_batches(self):
        batches = db_api.get_completed_task_executions_as_batches(
            workflow_execution_id=self.wf_ex.id,
            has_next_tasks=False
        )

        for batch in batches:
            yield batch

    def may_complete_workflow(self, task_ex):
        res = super(DirectWorkflowController, self).may_complete_workflow(
            task_ex
        )

        return res and not task_ex.has_next_tasks

    @profiler.trace('direct-wf-controller-find-next-tasks', hide_args=True)
    def _find_next_tasks(self, task_ex, ctx):
        t_n = task_ex.name
        t_s = task_ex.state

        ctx_view = data_flow.ContextView(
            data_flow.get_current_task_dict(task_ex),
            ctx,
            data_flow.get_workflow_environment_dict(self.wf_ex),
            self.wf_ex.context,
            self.wf_ex.input
        )

        # [(task_name, params, 'on-success'|'on-error'|'on-complete'), ...]
        result = []

        if t_s == states.ERROR:
            for name, cond, params in self.wf_spec.get_on_error_clause(t_n):
                if not cond or expr.evaluate(cond, ctx_view):
                    params = expr.evaluate_recursively(params, ctx_view)

                    result.append((name, params, 'on-error'))

        skip_is_empty = False
        if t_s == states.SKIPPED:
            for name, cond, params in self.wf_spec.get_on_skip_clause(t_n):
                if not cond or expr.evaluate(cond, ctx_view):
                    params = expr.evaluate_recursively(params, ctx_view)
                    result.append((name, params, 'on-skip'))

            # We should go to 'on-success' branch in case of
            # skipping task with no 'on-skip' specified.
            if len(result) == 0:
                skip_is_empty = True

        if t_s == states.SUCCESS or skip_is_empty:
            for name, cond, params in self.wf_spec.get_on_success_clause(t_n):
                if not cond or expr.evaluate(cond, ctx_view):
                    params = expr.evaluate_recursively(params, ctx_view)

                    result.append((name, params, 'on-success'))

        if states.is_completed(t_s) \
                and not states.is_cancelled_or_skipped(t_s):
            for name, cond, params in self.wf_spec.get_on_complete_clause(t_n):
                if not cond or expr.evaluate(cond, ctx_view):
                    params = expr.evaluate_recursively(params, ctx_view)

                    result.append((name, params, 'on-complete'))

        return result

    @profiler.trace(
        'direct-wf-controller-get-join-logical-state',
        hide_args=True
    )
    def _get_join_logical_state(self, task_spec):
        """Evaluates logical state of 'join' task.

        :param task_spec: 'join' task specification.
        :return: TaskLogicalState (state, state_info, cardinality,
            triggered_by) where 'state' and 'state_info' describe the logical
            state of the given 'join' task and 'cardinality' gives the
            remaining number of unfulfilled preconditions. If logical state
            is not WAITING then 'cardinality' should always be 0.
        """

        # TODO(rakhmerov): We need to use task_ex instead of task_spec
        # in order to cover a use case when there's more than one instance
        # of the same 'join' task in a workflow.

        join_expr = task_spec.get_join()

        in_task_specs = self.wf_spec.find_inbound_task_specs(task_spec)

        if not in_task_specs:
            return base.TaskLogicalState(states.RUNNING)

        t_execs_cache = self._prepare_task_executions_cache(task_spec)

        # List of tuples (task_name, task_ex, state, depth, event_name).
        induced_states = []

        for t_s in in_task_specs:
            t_ex = t_execs_cache[t_s.get_name()]

            tup = self._get_induced_join_state(
                t_s,
                t_ex,
                task_spec,
                t_execs_cache
            )

            induced_states.append(
                (
                    t_s.get_name(),
                    t_ex,
                    tup[0],
                    tup[1],
                    tup[2]
                )
            )

        def count(state):
            cnt = 0
            total_depth = 0

            for s in induced_states:
                if s[2] == state:
                    cnt += 1
                    total_depth += s[3]

            return cnt, total_depth

        errors_tuple = count(states.ERROR)
        runnings_tuple = count(states.RUNNING)
        total_count = len(induced_states)

        def _blocked_message():
            return (
                'Blocked by tasks: %s' %
                [s[0] for s in induced_states if s[2] == states.WAITING]
            )

        def _failed_message():
            return (
                'Failed by tasks: %s' %
                [s[0] for s in induced_states if s[2] == states.ERROR]
            )

        def _triggered_by(state):
            return [
                {'task_id': s[1].id, 'event': s[4]}
                for s in induced_states
                if s[2] == state and s[1] is not None
            ]

        # If "join" is configured as a number or 'one'.
        if isinstance(join_expr, int) or join_expr == 'one':
            spec_cardinality = 1 if join_expr == 'one' else join_expr

            if runnings_tuple[0] >= spec_cardinality:
                return base.TaskLogicalState(
                    states.RUNNING,
                    triggered_by=_triggered_by(states.RUNNING)
                )

            # E.g. 'join: 3' with inbound [ERROR, ERROR, RUNNING, WAITING]
            # No chance to get 3 RUNNING states.
            if errors_tuple[0] > (total_count - spec_cardinality):
                return base.TaskLogicalState(states.ERROR, _failed_message())

            # Calculate how many tasks need to finish to trigger this 'join'.
            cardinality = spec_cardinality - runnings_tuple[0]

            return base.TaskLogicalState(
                states.WAITING,
                _blocked_message(),
                cardinality=cardinality
            )

        if join_expr == 'all':
            if total_count == runnings_tuple[0]:
                return base.TaskLogicalState(
                    states.RUNNING,
                    triggered_by=_triggered_by(states.RUNNING)
                )

            if errors_tuple[0] > 0:
                return base.TaskLogicalState(
                    states.ERROR,
                    _failed_message(),
                    triggered_by=_triggered_by(states.ERROR)
                )

            # Remaining cardinality is just a difference between all tasks and
            # a number of those tasks that induce RUNNING state.
            cardinality = total_count - runnings_tuple[1]

            return base.TaskLogicalState(
                states.WAITING,
                _blocked_message(),
                cardinality=cardinality
            )

        raise RuntimeError('Unexpected join expression: %s' % join_expr)

    # TODO(rakhmerov): Method signature is incorrect given that
    # we may have multiple task executions for a task. It should
    # accept inbound task execution rather than a spec.
    @profiler.trace(
        'direct-wf-controller-get-induced-join-state',
        hide_args=True
    )
    def _get_induced_join_state(self, in_task_spec, in_task_ex,
                                join_task_spec, t_execs_cache):
        join_task_name = join_task_spec.get_name()

        if not in_task_ex:
            possible, depth = self._possible_route(
                in_task_spec,
                t_execs_cache
            )

            if possible:
                return states.WAITING, depth, None
            else:
                return states.ERROR, depth, 'impossible route'

        if not states.is_completed(in_task_ex.state):
            return states.WAITING, 1, None

        # [(task name, event name), ...]
        next_tasks_tuples = in_task_ex.next_tasks or []

        next_tasks_dict = {tup[0]: tup[1] for tup in next_tasks_tuples}

        if join_task_name not in next_tasks_dict:
            return states.ERROR, 1, "not triggered"

        return states.RUNNING, 1, next_tasks_dict[join_task_name]

    def _possible_route(self, task_spec, t_execs_cache, depth=1):
        in_task_specs = self.wf_spec.find_inbound_task_specs(task_spec)

        if not in_task_specs:
            return True, depth

        for t_s in in_task_specs:
            if t_s.get_name() not in t_execs_cache:
                t_execs_cache.update(
                    self._prepare_task_executions_cache(task_spec)
                )

            t_ex = t_execs_cache.get(t_s.get_name())

            if not t_ex:
                possible, depth = self._possible_route(
                    t_s,
                    t_execs_cache,
                    depth + 1
                )

                if possible:
                    return True, depth
            else:
                t_name = task_spec.get_name()

                if not states.is_completed(t_ex.state):
                    return True, depth

                if t_name in [t[0] for t in t_ex.next_tasks]:
                    return True, depth

        return False, depth

    def _find_all_parent_task_names(self, task_spec, depth=1):
        if depth == MAX_SEARCH_DEPTH:
            return {task_spec.get_name()}

        in_task_specs = self.wf_spec.find_inbound_task_specs(task_spec)

        if not in_task_specs:
            return {task_spec.get_name()}

        names = set()
        for t_s in in_task_specs:
            names.update(self._find_all_parent_task_names(t_s, depth + 1))

        if depth > 1:
            names.add(task_spec.get_name())

        return names

    def _prepare_task_executions_cache(self, task_spec):
        names = self._find_all_parent_task_names(task_spec)

        t_execs_cache = {
            t_ex.name: t_ex for t_ex in self._get_task_executions(
                fields=('id', 'name', 'state', 'next_tasks'),
                name={'in': names}
            )
        } if names else {}  # don't perform a db request if 'names' are empty

        for name in names:
            if name not in t_execs_cache:
                t_execs_cache[name] = None

        return t_execs_cache
