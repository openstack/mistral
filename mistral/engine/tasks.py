# Copyright 2016 - Nokia Networks.
# Copyright 2016 - Brocade Communications Systems, Inc.
# Copyright 2018 - Extreme Networks, Inc.
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

import abc
import copy
import json
from oslo_config import cfg
from oslo_log import log as logging
from osprofiler import profiler
import six

from mistral.db.v2 import api as db_api
from mistral.engine import actions
from mistral.engine import dispatcher
from mistral.engine import policies
from mistral.engine import post_tx_queue
from mistral.engine import workflow_handler as wf_handler
from mistral import exceptions as exc
from mistral import expressions as expr
from mistral.notifiers import base as notif
from mistral.notifiers import notification_events as events
from mistral import utils
from mistral.utils import wf_trace
from mistral.workflow import base as wf_base
from mistral.workflow import data_flow
from mistral.workflow import states


LOG = logging.getLogger(__name__)


@six.add_metaclass(abc.ABCMeta)
class Task(object):
    """Task.

    Represents a workflow task and defines interface that can be used by
    Mistral engine or its components in order to manipulate with tasks.
    """

    def __init__(self, wf_ex, wf_spec, task_spec, ctx, task_ex=None,
                 unique_key=None, waiting=False, triggered_by=None,
                 rerun=False):
        self.wf_ex = wf_ex
        self.task_spec = task_spec
        self.ctx = ctx
        self.task_ex = task_ex
        self.wf_spec = wf_spec
        self.unique_key = unique_key
        self.waiting = waiting
        self.triggered_by = triggered_by
        self.rerun = rerun
        self.reset_flag = False
        self.created = False
        self.state_changed = False

    def notify(self, old_task_state, new_task_state):
        publishers = self.wf_ex.params.get('notify')

        if not publishers and not isinstance(publishers, list):
            return

        notifier = notif.get_notifier(cfg.CONF.notifier.type)
        event = events.identify_task_event(old_task_state, new_task_state)

        notifier.notify(
            self.task_ex.id,
            self.task_ex.to_dict(),
            event,
            self.task_ex.updated_at,
            publishers
        )

    def is_completed(self):
        return self.task_ex and states.is_completed(self.task_ex.state)

    def is_waiting(self):
        return self.waiting

    def is_created(self):
        return self.created

    def is_state_changed(self):
        return self.state_changed

    @abc.abstractmethod
    def on_action_complete(self, action_ex):
        """Handle action completion.

        :param action_ex: Action execution.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def on_action_update(self, action_ex):
        """Handle action update.

        :param action_ex: Action execution.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def run(self):
        """Runs task."""
        raise NotImplementedError

    @profiler.trace('task-defer')
    def defer(self):
        """Defers task.

        This method puts task to a waiting state.
        """

        # NOTE(rakhmerov): using named locks may cause problems under load
        # with MySQL that raises a lot of deadlocks in case of high
        # parallelism so it makes sense to do a fast check if the object
        # already exists in DB outside of the lock.
        if not self.task_ex:
            t_execs = db_api.get_task_executions(
                workflow_execution_id=self.wf_ex.id,
                unique_key=self.unique_key,
                state=states.WAITING
            )

            self.task_ex = t_execs[0] if t_execs else None

        if self.task_ex:
            return

        with db_api.named_lock(self.unique_key):
            if not self.task_ex:
                t_execs = db_api.get_task_executions(
                    workflow_execution_id=self.wf_ex.id,
                    unique_key=self.unique_key
                )

                self.task_ex = t_execs[0] if t_execs else None

            msg = 'Task is waiting.'

            if not self.task_ex:
                self._create_task_execution(
                    state=states.WAITING,
                    state_info=msg
                )
            elif self.task_ex.state != states.WAITING:
                self.set_state(states.WAITING, msg)

    def reset(self):
        self.reset_flag = True

    @profiler.trace('task-set-state')
    def set_state(self, state, state_info, processed=None):
        """Sets task state without executing post completion logic.

        :param state: New task state.
        :param state_info: New state information (i.e. error message).
        :param processed: New "processed" flag value.
        :return: True if the state was changed as a result of this call,
            False otherwise.
        """

        assert self.task_ex

        cur_state = self.task_ex.state

        # Set initial started_at in case of waiting => running.
        # We can't set this just in run_existing, because task retries
        # will update started_at, which is incorrect.
        if cur_state == states.WAITING and state == states.RUNNING:
            self.save_started_time()

        if cur_state != state or self.task_ex.state_info != state_info:
            task_ex = db_api.update_task_execution_state(
                id=self.task_ex.id,
                cur_state=cur_state,
                state=state
            )

            if task_ex is None:
                # Do nothing because the update query did not change the DB.
                return False

            self.task_ex = task_ex
            self.task_ex.state_info = json.dumps(state_info) \
                if isinstance(state_info, dict) else state_info
            self.state_changed = True

            if processed is not None:
                self.task_ex.processed = processed

            wf_trace.info(
                self.task_ex.workflow_execution,
                "Task '%s' (%s) [%s -> %s, msg=%s]" %
                (self.task_ex.name,
                 self.task_ex.id,
                 cur_state,
                 state,
                 self.task_ex.state_info)
            )

        return True

    @profiler.trace('task-complete')
    def complete(self, state, state_info=None):
        """Complete task and set specified state.

        Method sets specified task state and runs all necessary post
        completion logic such as publishing workflow variables and
        scheduling new workflow commands.

        :param state: New task state.
        :param state_info: New state information (i.e. error message).
        """

        assert self.task_ex

        # Record the current task state.
        old_task_state = self.task_ex.state

        # Ignore if task already completed.
        if self.is_completed():
            # Publish task event again so subscribers know
            # task completed state is being processed again.
            self.notify(old_task_state, self.task_ex.state)

            return

        # If we were unable to change the task state it means that it was
        # already changed by a concurrent process. In this case we need to
        # skip all regular completion logic like scheduling new tasks,
        # running engine commands and publishing.
        if not self.set_state(state, state_info):
            return

        data_flow.publish_variables(self.task_ex, self.task_spec)

        if not self.task_spec.get_keep_result():
            # Destroy task result.
            for ex in self.task_ex.action_executions:
                if hasattr(ex, 'output'):
                    ex.output = {}

        self._after_task_complete()

        # Ignore DELAYED state.
        if self.task_ex.state == states.RUNNING_DELAYED:
            return

        # If workflow is paused we shouldn't schedule new commands
        # and mark task as processed.
        if states.is_paused(self.wf_ex.state):
            # Publish task event even if the workflow is paused.
            self.notify(old_task_state, self.task_ex.state)

            return

        wf_ctrl = wf_base.get_controller(self.wf_ex, self.wf_spec)

        # Calculate commands to process next.
        cmds = wf_ctrl.continue_workflow(task_ex=self.task_ex)

        # Mark task as processed after all decisions have been made
        # upon its completion.
        self.task_ex.processed = True

        self.register_workflow_completion_check()

        self.save_finished_time()

        # Publish task event.
        self.notify(old_task_state, self.task_ex.state)

        dispatcher.dispatch_workflow_commands(self.wf_ex, cmds)

    def register_workflow_completion_check(self):
        wf_ctrl = wf_base.get_controller(self.wf_ex, self.wf_spec)

        # Register an asynchronous command to check workflow completion
        # in a separate transaction if the task may potentially lead to
        # workflow completion.
        def _check():
            wf_handler.check_and_complete(self.wf_ex.id)

        if wf_ctrl.may_complete_workflow(self.task_ex):
            post_tx_queue.register_operation(_check, in_tx=True)

    @profiler.trace('task-update')
    def update(self, state, state_info=None):
        """Update task and set specified state.

        Method sets specified task state.

        :param state: New task state.
        :param state_info: New state information (i.e. error message).
        """

        assert self.task_ex

        # Record the current task state.
        old_task_state = self.task_ex.state

        # Ignore if task already completed.
        if states.is_completed(self.task_ex.state):
            # Publish task event again so subscribers know
            # task completed state is being processed again.
            self.notify(old_task_state, self.task_ex.state)

            return

        # Update only if state transition is valid.
        if not states.is_valid_transition(self.task_ex.state, state):
            return

        # We can't set the task state to RUNNING if some other
        # child executions are paused.
        child_states = [a_ex.state for a_ex in self.task_ex.executions]

        if state == states.RUNNING and states.PAUSED in child_states:
            return

        self.set_state(state, state_info)

        if states.is_completed(self.task_ex.state):
            self.register_workflow_completion_check()

        # Publish event.
        self.notify(old_task_state, self.task_ex.state)

    def _before_task_start(self):
        policies_spec = self.task_spec.get_policies()

        for p in policies.build_policies(policies_spec, self.wf_spec):
            p.before_task_start(self.task_ex, self.task_spec)

    def _after_task_complete(self):
        policies_spec = self.task_spec.get_policies()

        for p in policies.build_policies(policies_spec, self.wf_spec):
            p.after_task_complete(self.task_ex, self.task_spec)

    @profiler.trace('task-create-task-execution')
    def _create_task_execution(self, state=states.RUNNING, state_info=None):
        task_id = utils.generate_unicode_uuid()
        task_name = self.task_spec.get_name()
        task_type = self.task_spec.get_type()

        values = {
            'id': task_id,
            'name': task_name,
            'workflow_execution_id': self.wf_ex.id,
            'workflow_name': self.wf_ex.workflow_name,
            'workflow_namespace': self.wf_ex.workflow_namespace,
            'workflow_id': self.wf_ex.workflow_id,
            'state': state,
            'state_info': state_info,
            'spec': self.task_spec.to_dict(),
            'unique_key': self.unique_key,
            'in_context': self.ctx,
            'published': {},
            'runtime_context': {},
            'project_id': self.wf_ex.project_id,
            'type': task_type
        }

        if self.triggered_by:
            values['runtime_context']['triggered_by'] = self.triggered_by

        self.task_ex = db_api.create_task_execution(values)

        self.created = True

    def _get_safe_rerun(self):
        safe_rerun = self.task_spec.get_safe_rerun()

        if safe_rerun is not None:
            return safe_rerun

        task_defaults = self.wf_spec.get_task_defaults()

        if task_defaults:
            default_safe_rerun = task_defaults.get_safe_rerun()

            if default_safe_rerun is not None:
                return default_safe_rerun

        return False

    def _get_action_defaults(self):
        action_name = self.task_spec.get_action_name()

        if not action_name:
            return {}

        env = self.wf_ex.params['env']

        return env.get('__actions', {}).get(action_name, {})

    def save_started_time(self, value='default'):
        if not self.task_ex:
            return
        time = value if value is not 'default' else utils.utc_now_sec()
        self.task_ex.started_at = time

    def save_finished_time(self, value='default'):
        if not self.task_ex:
            return
        time = value if value is not 'default' else utils.utc_now_sec()
        self.task_ex.finished_at = time


class RegularTask(Task):
    """Regular task.

    Takes care of processing regular tasks with one action.
    """

    @profiler.trace('regular-task-on-action-complete', hide_args=True)
    def on_action_complete(self, action_ex):
        state = action_ex.state
        # TODO(rakhmerov): Here we can define more informative messages for
        # cases when action is successful and when it's not. For example,
        # in state_info we can specify the cause action.

        if state == states.SUCCESS:
            state_info = None
        else:
            action_result = action_ex.output.get('result')

            state_info = str(action_result) if action_result else None

        self.complete(state, state_info)

    @profiler.trace('regular-task-on-action-update', hide_args=True)
    def on_action_update(self, action_ex):
        self.update(action_ex.state)

    @profiler.trace('task-run')
    def run(self):
        if not self.task_ex:
            self._run_new()
        else:
            self._run_existing()

    @profiler.trace('task-run-new')
    def _run_new(self):
        if self.waiting:
            self.defer()

            return

        self._create_task_execution()
        self.save_started_time()

        # Publish event.
        self.notify(None, self.task_ex.state)

        LOG.debug(
            'Starting task [name=%s, init_state=%s, workflow_name=%s,'
            ' execution_id=%s]',
            self.task_spec.get_name(),
            self.task_ex.state,
            self.wf_ex.name,
            self.wf_ex.id
        )

        self._before_task_start()

        # Policies could possibly change task state.
        if self.task_ex.state != states.RUNNING:
            return

        self._schedule_actions()

    @profiler.trace('task-run-existing')
    def _run_existing(self):
        if self.waiting:
            return

        # Explicitly change task state to RUNNING.
        # Throw exception if the existing task already succeeded.
        if self.task_ex.state == states.SUCCESS:
            raise exc.MistralError(
                'Rerunning succeeded tasks is not supported.'
            )

        # Record the current task state.
        old_task_state = self.task_ex.state

        self.set_state(states.RUNNING, None, processed=False)

        # Publish event.
        self.notify(old_task_state, self.task_ex.state)

        if self.rerun:
            self.save_started_time()
            self.save_finished_time(value=None)
            self._before_task_start()

            # Policies could possibly change task state.
            if self.task_ex.state != states.RUNNING:
                return

        self._update_inbound_context()
        self._update_triggered_by()
        self._reset_actions()
        self._schedule_actions()

    def _update_inbound_context(self):
        assert self.task_ex

        wf_ctrl = wf_base.get_controller(self.wf_ex, self.wf_spec)

        self.ctx = wf_ctrl.get_task_inbound_context(self.task_spec)

        utils.update_dict(self.task_ex.in_context, self.ctx)

    def _update_triggered_by(self):
        assert self.task_ex

        if not self.triggered_by:
            return

        self.task_ex.runtime_context['triggered_by'] = self.triggered_by

    def _reset_actions(self):
        """Resets task state.

        Depending on task type this method may reset task state. For example,
        delete all task actions etc.
        """

        # Reset state of processed task and related action executions.
        if self.reset_flag:
            execs = self.task_ex.executions
        else:
            execs = [e for e in self.task_ex.executions if
                     (e.accepted and
                      e.state in [states.ERROR, states.CANCELLED])]

        for ex in execs:
            ex.accepted = False

    def _schedule_actions(self):
        # Regular task schedules just one action.
        input_dict = self._get_action_input()
        target = self._get_target(input_dict)

        action = self._build_action()

        action.validate_input(input_dict)

        action.schedule(
            input_dict,
            target,
            safe_rerun=self._get_safe_rerun(),
            timeout=self._get_timeout()
        )

    @profiler.trace('regular-task-get-target', hide_args=True)
    def _get_target(self, input_dict):
        if not self.task_spec.get_target():
            return None

        ctx_view = data_flow.ContextView(
            input_dict,
            self.ctx,
            data_flow.get_workflow_environment_dict(self.wf_ex),
            self.wf_ex.context,
            self.wf_ex.input
        )

        return expr.evaluate_recursively(
            self.task_spec.get_target(),
            ctx_view
        )

    @profiler.trace('regular-task-get-action-input', hide_args=True)
    def _get_action_input(self, ctx=None):
        input_spec = self.task_spec.get_input()

        input_dict = (
            self._evaluate_expression(input_spec, ctx) if input_spec else {}
        )

        if not isinstance(input_dict, dict):
            raise exc.InputException(
                "Wrong dynamic input for task: %s. Dict type is expected. "
                "Actual type: %s. Actual value: %s" %
                (self.task_spec.get_name(), type(input_dict), str(input_dict))
            )

        return utils.merge_dicts(
            input_dict,
            self._get_action_defaults(),
            overwrite=False
        )

    def _evaluate_expression(self, expression, ctx=None):
        ctx_view = data_flow.ContextView(
            data_flow.get_current_task_dict(self.task_ex),
            data_flow.get_workflow_environment_dict(self.wf_ex),
            ctx or self.ctx,
            self.wf_ex.context,
            self.wf_ex.input
        )

        return expr.evaluate_recursively(expression, ctx_view)

    def _build_action(self):
        action_name = self.task_spec.get_action_name()
        wf_name = self.task_spec.get_workflow_name()

        # For dynamic workflow evaluation we regenerate the action.
        if wf_name:
            return actions.WorkflowAction(
                wf_name=self._evaluate_expression(wf_name),
                task_ex=self.task_ex
            )

        # For dynamic action evaluation we just regenerate the name.
        if action_name:
            action_name = self._evaluate_expression(action_name)

        if not action_name:
            action_name = 'std.noop'

        action_def = actions.resolve_action_definition(
            action_name,
            self.wf_ex.name,
            self.wf_spec.get_name()
        )

        if action_def.spec:
            return actions.AdHocAction(action_def, task_ex=self.task_ex,
                                       task_ctx=self.ctx,
                                       wf_ctx=self.wf_ex.context)

        return actions.PythonAction(action_def, task_ex=self.task_ex)

    def _get_timeout(self):
        timeout = self.task_spec.get_policies().get_timeout()

        if not isinstance(timeout, (int, float)):
            wf_ex = self.task_ex.workflow_execution

            ctx_view = data_flow.ContextView(
                self.task_ex.in_context,
                wf_ex.context,
                wf_ex.input
            )

            timeout = expr.evaluate_recursively(data=timeout, context=ctx_view)

        return timeout if timeout > 0 else None


class WithItemsTask(RegularTask):
    """With-items task.

    Takes care of processing "with-items" tasks.
    """

    _CONCURRENCY = 'concurrency'
    _CAPACITY = 'capacity'
    _COUNT = 'count'
    _WITH_ITEMS = 'with_items'

    _DEFAULT_WITH_ITEMS = {
        _COUNT: 0,
        _CONCURRENCY: 0,
        _CAPACITY: 0
    }

    @profiler.trace('with-items-task-on-action-complete', hide_args=True)
    def on_action_complete(self, action_ex):
        assert self.task_ex

        with db_api.named_lock('with-items-%s' % self.task_ex.id):
            # NOTE: We need to refresh task execution object right
            # after the lock is acquired to make sure that we're
            # working with a fresh state of its runtime context.
            # Otherwise, SQLAlchemy session can contain a stale
            # cached version of it so that we don't modify actual
            # values (i.e. capacity).
            db_api.refresh(self.task_ex)

            if self.is_completed():
                return

            self._increase_capacity()

            if self.is_with_items_completed():
                state = self._get_final_state()

                # TODO(rakhmerov): Here we can define more informative messages
                # in cases when action is successful and when it's not.
                # For example, in state_info we can specify the cause action.
                # The use of action_ex.output.get('result') for state_info is
                # not accurate because there could be action executions that
                # had failed or was cancelled prior to this action execution.
                state_info = {
                    states.SUCCESS: None,
                    states.ERROR: 'One or more actions had failed.',
                    states.CANCELLED: 'One or more actions was cancelled.'
                }

                self.complete(state, state_info[state])

                return

            if self._has_more_iterations() and self._get_concurrency():
                self._schedule_actions()

    def _schedule_actions(self):
        with_items_values = self._get_with_items_values()

        if self._is_new():
            self._validate_values(with_items_values)

            action_count = len(six.next(iter(with_items_values.values())))

            self._prepare_runtime_context(action_count)

        input_dicts = self._get_input_dicts(with_items_values)

        if not input_dicts:
            self.complete(states.SUCCESS)

            return

        for i, input_dict in input_dicts:
            target = self._get_target(input_dict)

            action = self._build_action()

            action.validate_input(input_dict)

            action.schedule(
                input_dict,
                target,
                index=i,
                safe_rerun=self._get_safe_rerun(),
                timeout=self._get_timeout()
            )

            self._decrease_capacity(1)

    def _get_with_items_values(self):
        """Returns all values evaluated from 'with-items' expression.

        Example:
          DSL:
            with-items:
              - var1 in <% $.arrayI %>
              - var2 in <% $.arrayJ %>

        where arrayI = [1,2,3] and arrayJ = [a,b,c]

        The result of the method in this case will be:
            {
                'var1': [1,2,3],
                'var2': [a,b,c]
            }

        :return: Evaluated 'with-items' expression values.
        """
        ctx_view = data_flow.ContextView(
            self.ctx,
            self.wf_ex.context,
            self.wf_ex.input
        )

        return expr.evaluate_recursively(
            self.task_spec.get_with_items(),
            ctx_view
        )

    def _validate_values(self, with_items_values):
        # Take only mapped values and check them.
        values = list(with_items_values.values())

        if not all([isinstance(v, list) for v in values]):
            raise exc.InputException(
                "Wrong input format for: %s. List type is"
                " expected for each value." % with_items_values
            )

        required_len = len(values[0])

        if not all(len(v) == required_len for v in values):
            raise exc.InputException(
                "Wrong input format for: %s. All arrays must"
                " have the same length." % with_items_values
            )

    def _get_input_dicts(self, with_items_values):
        """Calculate input dictionaries for another portion of actions.

        :return: a list of tuples containing indexes and
            corresponding input dicts.
        """
        result = []

        for i in self._get_next_indexes():
            ctx = {}

            for k, v in with_items_values.items():
                ctx.update({k: v[i]})

            ctx = utils.merge_dicts(ctx, self.ctx)

            result.append((i, self._get_action_input(ctx)))

        return result

    def _get_with_items_context(self):
        return self.task_ex.runtime_context.get(
            self._WITH_ITEMS,
            self._DEFAULT_WITH_ITEMS
        )

    def _get_with_items_count(self):
        return self._get_with_items_context()[self._COUNT]

    def _get_with_items_capacity(self):
        return self._get_with_items_context()[self._CAPACITY]

    def _get_concurrency(self):
        return self.task_ex.runtime_context.get(self._CONCURRENCY)

    def is_with_items_completed(self):
        find_cancelled = lambda x: x.accepted and x.state == states.CANCELLED

        if list(filter(find_cancelled, self.task_ex.executions)):
            return True

        execs = list([t for t in self.task_ex.executions if t.accepted])
        count = self._get_with_items_count() or 1

        # We need to make sure that method on_action_complete() has been
        # called for every action. Just looking at number of actions and
        # their 'accepted' flag is not enough because action gets accepted
        # before on_action_complete() is called for it. This call is
        # mandatory in order to do all needed processing from task
        # perspective. So we can simply check if capacity is fully reset
        # to its initial state.
        full_capacity = (
            not self._get_concurrency() or
            self._get_with_items_capacity() == self._get_concurrency()
        )

        return count == len(execs) and full_capacity

    def _get_final_state(self):
        find_cancelled = lambda x: x.accepted and x.state == states.CANCELLED
        find_error = lambda x: x.accepted and x.state == states.ERROR

        if list(filter(find_cancelled, self.task_ex.executions)):
            return states.CANCELLED
        elif list(filter(find_error, self.task_ex.executions)):
            return states.ERROR
        else:
            return states.SUCCESS

    def _get_accepted_executions(self):
        # Choose only if not accepted but completed.
        return list(
            [x for x in self.task_ex.executions
             if x.accepted and states.is_completed(x.state)]
        )

    def _get_unaccepted_executions(self):
        # Choose only if not accepted but completed.
        return list(
            filter(
                lambda x: not x.accepted and states.is_completed(x.state),
                self.task_ex.executions
            )
        )

    def _get_next_start_index(self):
        f = lambda x: (
            x.accepted or
            states.is_running(x.state) or
            states.is_idle(x.state)
        )

        return len(list(filter(f, self.task_ex.executions)))

    def _get_next_indexes(self):
        capacity = self._get_with_items_capacity()
        count = self._get_with_items_count()

        def _get_indexes(exs):
            return sorted(set([ex.runtime_context['index'] for ex in exs]))

        accepted = _get_indexes(self._get_accepted_executions())
        unaccepted = _get_indexes(self._get_unaccepted_executions())

        candidates = sorted(list(set(unaccepted) - set(accepted)))

        if candidates:
            indices = copy.copy(candidates)

            if max(candidates) < count - 1:
                indices += list(six.moves.range(max(candidates) + 1, count))
        else:
            i = self._get_next_start_index()
            indices = list(six.moves.range(i, count))

        return indices[:capacity]

    def _increase_capacity(self):
        ctx = self._get_with_items_context()
        concurrency = self._get_concurrency()

        if concurrency and ctx[self._CAPACITY] < concurrency:
            ctx[self._CAPACITY] += 1

            self.task_ex.runtime_context.update({self._WITH_ITEMS: ctx})

    def _decrease_capacity(self, count):
        ctx = self._get_with_items_context()

        capacity = ctx[self._CAPACITY]

        if capacity is not None:
            if capacity >= count:
                ctx[self._CAPACITY] -= count
            else:
                raise RuntimeError(
                    "Can't decrease with-items capacity"
                    " [capacity=%s, count=%s]" % (capacity, count)
                )

        self.task_ex.runtime_context.update({self._WITH_ITEMS: ctx})

    def _is_new(self):
        return not self.task_ex.runtime_context.get(self._WITH_ITEMS)

    def _prepare_runtime_context(self, action_count):
        runtime_ctx = self.task_ex.runtime_context

        if not runtime_ctx.get(self._WITH_ITEMS):
            # Prepare current indexes and parallel limitation.
            runtime_ctx[self._WITH_ITEMS] = {
                self._CAPACITY: self._get_concurrency(),
                self._COUNT: action_count
            }

    def _has_more_iterations(self):
        # See action executions which have been already
        # accepted or are still running.
        action_exs = list(filter(
            lambda x: x.accepted or x.state == states.RUNNING,
            self.task_ex.executions
        ))

        return self._get_with_items_count() > len(action_exs)
