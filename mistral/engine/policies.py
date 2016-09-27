# Copyright 2014 - Mirantis, Inc.
# Copyright 2015 - StackStorm, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

from mistral.db.v2 import api as db_api
from mistral.engine import base
from mistral import expressions
from mistral.services import scheduler
from mistral.utils import wf_trace
from mistral.workflow import data_flow
from mistral.workflow import states

import six

_CONTINUE_TASK_PATH = 'mistral.engine.policies._continue_task'
_COMPLETE_TASK_PATH = 'mistral.engine.policies._complete_task'


def _log_task_delay(task_ex, delay_sec):
    wf_trace.info(
        task_ex,
        "Task '%s' [%s -> %s, delay = %s sec]" %
        (task_ex.name, task_ex.state, states.RUNNING_DELAYED, delay_sec)
    )


def build_policies(policies_spec, wf_spec):
    task_defaults = wf_spec.get_task_defaults()
    wf_policies = task_defaults.get_policies() if task_defaults else None

    if not (policies_spec or wf_policies):
        return []

    return construct_policies_list(policies_spec, wf_policies)


def get_policy_factories():
    return [
        build_pause_before_policy,
        build_wait_before_policy,
        build_wait_after_policy,
        build_retry_policy,
        build_timeout_policy,
        build_concurrency_policy
    ]


def construct_policies_list(policies_spec, wf_policies):
    policies = []

    for factory in get_policy_factories():
        policy = factory(policies_spec)

        if wf_policies and not policy:
            policy = factory(wf_policies)

        if policy:
            policies.append(policy)

    return policies


def build_wait_before_policy(policies_spec):
    if not policies_spec:
        return None

    wait_before = policies_spec.get_wait_before()

    if (isinstance(wait_before, six.string_types) or wait_before > 0):
        return WaitBeforePolicy(wait_before)
    else:
        return None


def build_wait_after_policy(policies_spec):
    if not policies_spec:
        return None

    wait_after = policies_spec.get_wait_after()

    if (isinstance(wait_after, six.string_types) or wait_after > 0):
        return WaitAfterPolicy(wait_after)
    else:
        return None


def build_retry_policy(policies_spec):
    if not policies_spec:
        return None

    retry = policies_spec.get_retry()

    if not retry:
        return None

    return RetryPolicy(
        retry.get_count(),
        retry.get_delay(),
        retry.get_break_on(),
        retry.get_continue_on()
    )


def build_timeout_policy(policies_spec):
    if not policies_spec:
        return None

    timeout_policy = policies_spec.get_timeout()

    if (isinstance(timeout_policy, six.string_types) or timeout_policy > 0):
        return TimeoutPolicy(timeout_policy)
    else:
        return None


def build_pause_before_policy(policies_spec):
    if not policies_spec:
        return None

    pause_before_policy = policies_spec.get_pause_before()

    return (PauseBeforePolicy(pause_before_policy)
            if pause_before_policy else None)


def build_concurrency_policy(policies_spec):
    if not policies_spec:
        return None

    concurrency_policy = policies_spec.get_concurrency()

    return (ConcurrencyPolicy(concurrency_policy)
            if concurrency_policy else None)


def _ensure_context_has_key(runtime_context, key):
    if not runtime_context:
        runtime_context = {}

    if key not in runtime_context:
        runtime_context.update({key: {}})

    return runtime_context


class WaitBeforePolicy(base.TaskPolicy):
    _schema = {
        "properties": {
            "delay": {"type": "integer"}
        }
    }

    def __init__(self, delay):
        self.delay = delay

    def before_task_start(self, task_ex, task_spec):
        super(WaitBeforePolicy, self).before_task_start(task_ex, task_spec)

        context_key = 'wait_before_policy'

        runtime_context = _ensure_context_has_key(
            task_ex.runtime_context,
            context_key
        )

        task_ex.runtime_context = runtime_context

        policy_context = runtime_context[context_key]

        if policy_context.get('skip'):
            # Unset state 'RUNNING_DELAYED'.
            wf_trace.info(
                task_ex,
                "Task '%s' [%s -> %s]"
                % (task_ex.name, states.RUNNING_DELAYED, states.RUNNING)
            )

            task_ex.state = states.RUNNING

            return

        if task_ex.state != states.IDLE:
            policy_context.update({'skip': True})

            _log_task_delay(task_ex, self.delay)

            task_ex.state = states.RUNNING_DELAYED

            scheduler.schedule_call(
                None,
                _CONTINUE_TASK_PATH,
                self.delay,
                task_ex_id=task_ex.id,
            )


class WaitAfterPolicy(base.TaskPolicy):
    _schema = {
        "properties": {
            "delay": {"type": "integer"}
        }
    }

    def __init__(self, delay):
        self.delay = delay

    def after_task_complete(self, task_ex, task_spec):
        super(WaitAfterPolicy, self).after_task_complete(task_ex, task_spec)

        context_key = 'wait_after_policy'

        runtime_context = _ensure_context_has_key(
            task_ex.runtime_context,
            context_key
        )

        task_ex.runtime_context = runtime_context

        policy_context = runtime_context[context_key]

        if policy_context.get('skip'):
            # Skip, already processed.
            return

        policy_context.update({'skip': True})

        _log_task_delay(task_ex, self.delay)

        end_state = task_ex.state
        end_state_info = task_ex.state_info

        # TODO(rakhmerov): Policies probably needs to have tasks.Task
        # interface in order to change manage task state safely.
        # Set task state to 'DELAYED'.
        task_ex.state = states.RUNNING_DELAYED
        task_ex.state_info = (
            'Suspended by wait-after policy for %s seconds' % self.delay
        )

        # Schedule to change task state to RUNNING again.
        scheduler.schedule_call(
            None,
            _COMPLETE_TASK_PATH,
            self.delay,
            task_ex_id=task_ex.id,
            state=end_state,
            state_info=end_state_info
        )


class RetryPolicy(base.TaskPolicy):
    _schema = {
        "properties": {
            "delay": {"type": "integer"},
            "count": {"type": "integer"}
        }
    }

    def __init__(self, count, delay, break_on, continue_on):
        self.count = count
        self.delay = delay
        self.break_on = break_on
        self._continue_on_clause = continue_on

    def after_task_complete(self, task_ex, task_spec):
        """Possible Cases:

        1. state = SUCCESS
           if continue_on is not specified,
           no need to move to next iteration;
           if current:count achieve retry:count then policy
           breaks the loop (regardless on continue-on condition);
           otherwise - check continue_on condition and if
           it is True - schedule the next iteration,
           otherwise policy breaks the loop.
        2. retry:count = 5, current:count = 2, state = ERROR,
           state = IDLE/DELAYED, current:count = 3
        3. retry:count = 5, current:count = 4, state = ERROR
        Iterations complete therefore state = #{state}, current:count = 4.
        """
        super(RetryPolicy, self).after_task_complete(task_ex, task_spec)

        # TODO(m4dcoder): If the task_ex.action_executions and
        # task_ex.workflow_executions collection are not called,
        # then the retry_no in the runtime_context of the task_ex will not
        # be updated accurately. To be exact, the retry_no will be one
        # iteration behind.
        ex = task_ex.executions  # noqa

        context_key = 'retry_task_policy'

        runtime_context = _ensure_context_has_key(
            task_ex.runtime_context,
            context_key
        )

        wf_ex = task_ex.workflow_execution

        ctx_view = data_flow.ContextView(
            data_flow.evaluate_task_outbound_context(task_ex),
            wf_ex.context,
            wf_ex.input
        )

        continue_on_evaluation = expressions.evaluate(
            self._continue_on_clause,
            ctx_view
        )

        task_ex.runtime_context = runtime_context

        state = task_ex.state

        if not states.is_completed(state):
            return

        policy_context = runtime_context[context_key]

        retry_no = 0

        if 'retry_no' in policy_context:
            retry_no = policy_context['retry_no']
            del policy_context['retry_no']

        retries_remain = retry_no + 1 < self.count

        stop_continue_flag = (task_ex.state == states.SUCCESS and
                              not self._continue_on_clause)
        stop_continue_flag = (stop_continue_flag or
                              (self._continue_on_clause and
                               not continue_on_evaluation))
        break_triggered = task_ex.state == states.ERROR and self.break_on

        if not retries_remain or break_triggered or stop_continue_flag:
            return

        _log_task_delay(task_ex, self.delay)

        data_flow.invalidate_task_execution_result(task_ex)
        task_ex.state = states.RUNNING_DELAYED

        policy_context['retry_no'] = retry_no + 1
        runtime_context[context_key] = policy_context

        scheduler.schedule_call(
            None,
            _CONTINUE_TASK_PATH,
            self.delay,
            task_ex_id=task_ex.id,
        )


class TimeoutPolicy(base.TaskPolicy):
    _schema = {
        "properties": {
            "delay": {"type": "integer"}
        }
    }

    def __init__(self, timeout_sec):
        self.delay = timeout_sec

    def before_task_start(self, task_ex, task_spec):
        super(TimeoutPolicy, self).before_task_start(task_ex, task_spec)

        scheduler.schedule_call(
            None,
            'mistral.engine.policies._fail_task_if_incomplete',
            self.delay,
            task_ex_id=task_ex.id,
            timeout=self.delay
        )

        wf_trace.info(
            task_ex,
            "Timeout check scheduled [task=%s, timeout(s)=%s]." %
            (task_ex.id, self.delay)
        )


class PauseBeforePolicy(base.TaskPolicy):
    _schema = {
        "properties": {
            "expr": {"type": "boolean"}
        }
    }

    def __init__(self, expression):
        self.expr = expression

    def before_task_start(self, task_ex, task_spec):
        super(PauseBeforePolicy, self).before_task_start(task_ex, task_spec)

        if not self.expr:
            return

        wf_trace.info(
            task_ex,
            "Workflow paused before task '%s' [%s -> %s]" %
            (task_ex.name, task_ex.workflow_execution.state, states.PAUSED)
        )

        task_ex.workflow_execution.state = states.PAUSED
        task_ex.state = states.IDLE


class ConcurrencyPolicy(base.TaskPolicy):
    _schema = {
        "properties": {
            "concurrency": {"type": "integer"},
        }
    }

    def __init__(self, concurrency):
        self.concurrency = concurrency

    def before_task_start(self, task_ex, task_spec):
        super(ConcurrencyPolicy, self).before_task_start(task_ex, task_spec)

        # This policy doesn't do anything except validating "concurrency"
        # property value and setting a variable into task runtime context.
        # This variable is then used to define how many action executions
        # may be started in parallel.
        context_key = 'concurrency'

        runtime_context = _ensure_context_has_key(
            task_ex.runtime_context,
            context_key
        )

        runtime_context[context_key] = self.concurrency
        task_ex.runtime_context = runtime_context


def _continue_task(task_ex_id):
    from mistral.engine import task_handler

    with db_api.transaction():
        task_handler.continue_task(db_api.get_task_execution(task_ex_id))


def _complete_task(task_ex_id, state, state_info):
    from mistral.engine import task_handler

    with db_api.transaction():
        task_handler.complete_task(
            db_api.get_task_execution(task_ex_id),
            state,
            state_info
        )


def _fail_task_if_incomplete(task_ex_id, timeout):
    from mistral.engine import task_handler

    with db_api.transaction():
        task_ex = db_api.get_task_execution(task_ex_id)

        if not states.is_completed(task_ex.state):
            msg = 'Task timed out [timeout(s)=%s].' % timeout

            task_handler.complete_task(
                db_api.get_task_execution(task_ex_id),
                states.ERROR,
                msg
            )
