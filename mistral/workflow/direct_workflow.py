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

from mistral.db.v2 import api as db_api
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

    def _get_upstream_task_executions(self, task_spec):
        t_specs_names = [t_spec.get_name() for t_spec in
                         self.wf_spec.find_inbound_task_specs(task_spec)]
        t_execs = self._get_task_executions(name={'in': t_specs_names})

        return [t_ex for t_ex in t_execs
                if self._is_upstream_task_execution(task_spec, t_ex)]

    def _is_upstream_task_execution(self, t_spec, t_ex_candidate):
        if not states.is_completed(t_ex_candidate.state):
            return False

        if not t_spec.get_join():
            return t_ex_candidate.processed

        induced_state, _, _ = self._get_induced_join_state(
            self.wf_spec.get_tasks()[t_ex_candidate.name],
            self._find_task_execution_by_name(t_ex_candidate.name),
            t_spec,
            {}
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

        for t_n, params, event_name in self._find_next_tasks(task_ex, ctx=ctx):
            t_s = self.wf_spec.get_tasks()[t_n]

            if not (t_s or t_n in commands.ENGINE_CMD_CLS):
                raise exc.WorkflowException("Task '%s' not found." % t_n)
            elif not t_s:
                t_s = self.wf_spec.get_tasks()[task_ex.name]

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

    def find_indirectly_affected_task_executions(self, task_name):
        return self._find_indirectly_affected_created_joins(task_name)

    def is_error_handled_for(self, task_ex):
        # TODO(rakhmerov): The method works in a different way than
        # all_errors_handled(). It doesn't evaluate expressions under
        # "on-error" clause.
        return bool(self.wf_spec.get_on_error_clause(task_ex.name))

    def all_errors_handled(self):
        cnt = lookup_utils.find_task_executions_count(
            workflow_execution_id=self.wf_ex.id,
            state=states.ERROR,
            error_handled=False
        )

        return cnt == 0

    def _find_end_task_executions_as_batches(self):
        batches = lookup_utils.find_completed_task_executions_as_batches(
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

    def _find_next_task_names(self, task_ex):
        return [t[0] for t in self._find_next_tasks(task_ex)]

    def _find_next_tasks(self, task_ex, ctx=None):
        t_state = task_ex.state
        t_name = task_ex.name

        ctx_view = data_flow.ContextView(
            data_flow.get_current_task_dict(task_ex),
            ctx or data_flow.evaluate_task_outbound_context(task_ex),
            data_flow.get_workflow_environment_dict(self.wf_ex),
            self.wf_ex.context,
            self.wf_ex.input
        )

        # [(task_name, params, 'on-success'|'on-error'|'on-complete'), ...]
        result = []

        def process_clause(clause, event_name):
            task_tuples = self._find_next_tasks_for_clause(clause, ctx_view)

            for t in task_tuples:
                result.append((t[0], t[1], event_name))

        if t_state == states.SUCCESS:
            process_clause(
                self.wf_spec.get_on_success_clause(t_name),
                'on-success'
            )
        elif t_state == states.ERROR:
            process_clause(
                self.wf_spec.get_on_error_clause(t_name),
                'on-error'
            )

        if states.is_completed(t_state) and not states.is_cancelled(t_state):
            process_clause(
                self.wf_spec.get_on_complete_clause(t_name),
                'on-complete'
            )

        return result

    @staticmethod
    def _find_next_tasks_for_clause(clause, ctx):
        """Finds next tasks names.

         This method finds next tasks(commands) base on given {name: condition}
         dictionary.

        :param clause: Tuple (task_name, condition, parameters) taken from
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

    @profiler.trace('direct-wf-controller-find-downstream-joins')
    def _find_indirectly_affected_created_joins(self, task_name, result=None,
                                                visited_task_names=None):
        visited_task_names = (
            set() if visited_task_names is None else visited_task_names
        )

        if task_name in visited_task_names:
            return

        visited_task_names.add(task_name)

        result = set() if result is None else result

        def _process_clause(clause):
            for t_name, condition, params in clause:
                t_spec = self.wf_spec.get_tasks()[t_name]

                # Encountered an engine command.
                if not t_spec:
                    continue

                if t_spec.get_join():
                    # TODO(rakhmerov): This is a fundamental limitation
                    # that prevents us having cycles within workflows
                    # that contain joins because we assume that there
                    # can be only one "join" task with a given name.
                    t_ex = self._find_task_execution_by_name(t_name)

                    if t_ex:
                        result.add(t_ex)

                        # If we found a "join" we don't need to go further
                        # because completion of the found join will handle
                        # other deeper joins.
                        continue

                # Recursion.
                self._find_indirectly_affected_created_joins(
                    t_name,
                    result=result,
                    visited_task_names=visited_task_names
                )

        _process_clause(self.wf_spec.get_on_success_clause(task_name))
        _process_clause(self.wf_spec.get_on_error_clause(task_name))
        _process_clause(self.wf_spec.get_on_complete_clause(task_name))

        return result

    @profiler.trace('direct-wf-controller-get-join-logical-state')
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

        names = self._find_all_parent_task_names(task_spec)

        t_execs_cache = {
            t_ex.name: t_ex for t_ex in self._get_task_executions(
                fields=('id', 'name', 'state'),
                name={'in': names}
            )
        } if names else {}  # don't perform a db request if 'names' are empty

        # List of tuples (task_name, task_ex, state, depth, event_name).
        induced_states = []

        for t_s in in_task_specs:
            t_ex = t_execs_cache.get(t_s.get_name())

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

        if self._is_conditional_transition(in_task_ex, in_task_spec) and \
                not hasattr(in_task_ex, "in_context"):
            in_task_ex = db_api.get_task_execution(in_task_ex.id)
            t_execs_cache[in_task_ex.name] = in_task_ex

        # [(task name, params, event name), ...]
        next_tasks_tuples = self._find_next_tasks(in_task_ex)

        next_tasks_dict = {tup[0]: tup[2] for tup in next_tasks_tuples}

        if join_task_name not in next_tasks_dict:
            return states.ERROR, 1, "not triggered"

        return states.RUNNING, 1, next_tasks_dict[join_task_name]

    def _find_task_execution_by_name(self, t_name):
        # Note: in case of 'join' completion check it's better to initialize
        # the entire task_executions collection to avoid too many DB queries.

        t_execs = lookup_utils.find_task_executions_by_name(
            self.wf_ex.id,
            t_name
        )

        # TODO(rakhmerov): Temporary hack. See the previous comment.
        return t_execs[-1] if t_execs else None

    def _possible_route(self, task_spec, t_execs_cache, depth=1):
        in_task_specs = self.wf_spec.find_inbound_task_specs(task_spec)

        if not in_task_specs:
            return True, depth

        for t_s in in_task_specs:
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

                # By default we don't download task context from the database,
                # but just basic fields: 'id', 'name' and 'state'. It's a good
                # optimization, because contexts can be too heavy and we don't
                # need them most of the time.
                # But sometimes we need it for conditional transitions (when
                # the decision where to go is based on the current context),
                # and if this is the case, we download full task execution
                # and then evaluate its context to find the route.
                # TODO(mfedosin): Think of a way to avoid this.
                if self._is_conditional_transition(t_ex, task_spec) and \
                        not hasattr(t_ex, "in_context"):
                    t_ex = db_api.get_task_execution(t_ex.id)
                    t_execs_cache[t_ex.name] = t_ex

                if t_name in self._find_next_task_names(t_ex):
                    return True, depth

        return False, depth

    def _find_all_parent_task_names(self, task_spec):

        all_parent_names = set()

        inbound_specs = self.wf_spec.find_inbound_task_specs(task_spec)[:]
        while inbound_specs:
            spec = inbound_specs.pop()
            all_parent_names.add(spec.get_name())
            inbound_specs += self.wf_spec.find_inbound_task_specs(spec)

        return all_parent_names

    @staticmethod
    def _is_conditional_transition(t_ex, t_spec):
        if t_ex.state == states.SUCCESS:
            return t_spec.is_conditional_transition('on-success')
        elif t_ex.state == states.ERROR:
            return t_spec.is_conditional_transition('on-error')

        return False
