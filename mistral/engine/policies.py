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

from mistral.db import utils as db_utils
from mistral.db.v2 import api as db_api
from mistral.engine import base
from mistral.engine import post_tx_queue
from mistral.engine import workflow_handler as wf_handler
from mistral import expressions
from mistral.scheduler import base as sched_base
from mistral.utils import wf_trace
from mistral.workflow import data_flow
from mistral.workflow import states


_CONTINUE_TASK_PATH = 'mistral.engine.policies._continue_task'
_COMPLETE_TASK_PATH = 'mistral.engine.policies._complete_task'
_FAIL_IF_INCOMPLETE_TASK_PATH = (
    'mistral.engine.policies._fail_task_if_incomplete'
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
        build_fail_on_policy,
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

    if isinstance(wait_before, str) or wait_before > 0:
        return WaitBeforePolicy(wait_before)
    else:
        return None


def build_wait_after_policy(policies_spec):
    if not policies_spec:
        return None

    wait_after = policies_spec.get_wait_after()

    if isinstance(wait_after, str) or wait_after > 0:
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

    if isinstance(timeout_policy, str) or timeout_policy > 0:
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


def build_fail_on_policy(policies_spec):
    if not policies_spec:
        return None

    fail_on_policy = policies_spec.get_fail_on()

    return (FailOnPolicy(fail_on_policy)
            if fail_on_policy else None)


def _ensure_context_has_key(runtime_context, key):
    if not runtime_context:
        runtime_context = {}

    if key not in runtime_context:
        runtime_context.update({key: {}})

    return runtime_context


class WaitBeforePolicy(base.TaskPolicy):
    _schema = {
        "properties": {
            "delay": {
                "type": "integer",
                "minimum": 0
            }
        }
    }

    def __init__(self, delay):
        self.delay = delay

    def before_task_start(self, task):
        super(WaitBeforePolicy, self).before_task_start(task)

        # No need to wait for a task if delay is 0
        if self.delay == 0:
            return

        ctx_key = 'wait_before_policy'

        policy_ctx = task.get_policy_context(ctx_key)

        if policy_ctx.get('skip'):
            # Unset state 'RUNNING_DELAYED'.
            task.set_state(states.RUNNING, None)

            return

        if task.get_state() != states.IDLE:
            policy_ctx.update({'skip': True})

            task.set_state(
                states.RUNNING_DELAYED,
                "Delayed by 'wait-before' policy [delay=%s]" % self.delay
            )

            sched = sched_base.get_system_scheduler()

            job = sched_base.SchedulerJob(
                run_after=self.delay,
                func_name=_CONTINUE_TASK_PATH,
                func_args={'task_ex_id': task.get_id()}
            )

            sched.schedule(job)


class WaitAfterPolicy(base.TaskPolicy):
    _schema = {
        "properties": {
            "delay": {
                "type": "integer",
                "minimum": 0
            }
        }
    }

    def __init__(self, delay):
        self.delay = delay

    def after_task_complete(self, task):
        super(WaitAfterPolicy, self).after_task_complete(task)

        # No need to postpone a task if delay is 0
        if self.delay == 0:
            return

        ctx_key = 'wait_after_policy'

        policy_ctx = task.get_policy_context(ctx_key)

        if policy_ctx.get('skip'):
            # Skip, already processed.
            return

        policy_ctx.update({'skip': True})

        end_state = task.get_state()
        end_state_info = task.get_state_info()

        # Set task state to 'RUNNING_DELAYED'.
        task.set_state(
            states.RUNNING_DELAYED,
            "Delayed by 'wait-after' policy [delay=%s]" % self.delay
        )

        # Schedule to change task state to RUNNING again.
        sched = sched_base.get_system_scheduler()

        job = sched_base.SchedulerJob(
            run_after=self.delay,
            func_name=_COMPLETE_TASK_PATH,
            func_args={
                'task_ex_id': task.get_id(),
                'state': end_state,
                'state_info': end_state_info
            }
        )

        sched.schedule(job)


class RetryPolicy(base.TaskPolicy):
    _schema = {
        "properties": {
            "delay": {
                "type": "integer",
                "minimum": 0
            },
            "count": {
                "type": "integer",
                "minimum": 0
            },
        }
    }

    def __init__(self, count, delay, break_on, continue_on):
        self.count = count
        self.delay = delay
        self._break_on_clause = break_on
        self._continue_on_clause = continue_on

    def after_task_complete(self, task):
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
        super(RetryPolicy, self).after_task_complete(task)

        # There is nothing to repeat
        if self.count == 0:
            return

        # TODO(m4dcoder): If the task_ex.action_executions and
        # task_ex.workflow_executions collection are not called,
        # then the retry_no in the runtime_context of the task_ex will not
        # be updated accurately. To be exact, the retry_no will be one
        # iteration behind.
        ex = task.task_ex.executions  # noqa

        ctx_key = 'retry_task_policy'

        expr_ctx = task.get_expression_context(
            ctx=data_flow.evaluate_task_outbound_context(task.task_ex)
        )

        continue_on_evaluation = expressions.evaluate(
            self._continue_on_clause,
            expr_ctx
        )

        break_on_evaluation = expressions.evaluate(
            self._break_on_clause,
            expr_ctx
        )

        state = task.get_state()

        if not states.is_completed(state) or states.is_cancelled(state):
            return

        policy_ctx = task.get_policy_context(ctx_key)

        retry_no = 0

        if 'retry_no' in policy_ctx:
            retry_no = policy_ctx['retry_no']

            del policy_ctx['retry_no']

        retries_remain = retry_no < self.count

        stop_continue_flag = (
            task.get_state() == states.SUCCESS and
            not self._continue_on_clause
        )

        stop_continue_flag = (
            stop_continue_flag or
            (self._continue_on_clause and not continue_on_evaluation)
        )

        break_triggered = (
            task.get_state() == states.ERROR and
            break_on_evaluation
        )

        if not retries_remain or break_triggered or stop_continue_flag:
            return

        task.invalidate_result()

        policy_ctx['retry_no'] = retry_no + 1

        task.touch_runtime_context()

        # NOTE(vgvoleg): join tasks in direct workflows can't be
        # retried as-is, because these tasks can't start without
        # a correct logical state.
        if hasattr(task.task_spec, "get_join") and task.task_spec.get_join():
            # TODO(rakhmerov): This is an example of broken encapsulation.
            # The control over such operations should belong to the class Task.
            # If it's done, from the outside of the class there will be just
            # one visible operation "continue_task()" or something like that.
            from mistral.engine import task_handler as t_h

            task.set_state(
                states.WAITING,
                "Delayed by 'retry' policy [delay=%s]" % self.delay
            )

            t_h._schedule_refresh_task_state(task.get_id(), self.delay)

            return

        task.set_state(
            states.RUNNING_DELAYED,
            "Delayed by 'retry' policy [delay=%s]" % self.delay
        )

        sched = sched_base.get_system_scheduler()

        job = sched_base.SchedulerJob(
            run_after=self.delay,
            func_name=_CONTINUE_TASK_PATH,
            func_args={'task_ex_id': task.get_id()}
        )

        sched.schedule(job)


class TimeoutPolicy(base.TaskPolicy):
    _schema = {
        "properties": {
            "delay": {
                "type": "integer",
                "minimum": 0
            }
        }
    }

    def __init__(self, timeout_sec):
        self.delay = timeout_sec

    def before_task_start(self, task):
        super(TimeoutPolicy, self).before_task_start(task)

        # No timeout if delay is 0
        if self.delay == 0:
            return

        sched = sched_base.get_system_scheduler()

        job = sched_base.SchedulerJob(
            run_after=self.delay,
            func_name=_FAIL_IF_INCOMPLETE_TASK_PATH,
            func_args={
                'task_ex_id': task.get_id(),
                'timeout': self.delay
            }
        )

        sched.schedule(job)

        wf_trace.info(
            task.task_ex,
            "Timeout check scheduled [task=%s, timeout(s)=%s]." %
            (task.get_id(), self.delay)
        )


class PauseBeforePolicy(base.TaskPolicy):
    _schema = {
        "properties": {
            "expr": {"type": "boolean"}
        }
    }

    def __init__(self, expression):
        self.expr = expression

    def before_task_start(self, task):
        super(PauseBeforePolicy, self).before_task_start(task)

        if not self.expr:
            return

        wf_trace.info(
            task.task_ex,
            "Workflow paused before task '%s' [%s -> %s]" %
            (
                task.get_name(),
                task.wf_ex.state,
                states.PAUSED
            )
        )

        task.set_state(states.IDLE, "Set by 'pause-before' policy")

        wf_handler.pause_workflow(task.wf_ex)


class ConcurrencyPolicy(base.TaskPolicy):
    _schema = {
        "properties": {
            "concurrency": {
                "type": "integer",
                "minimum": 0
            }
        }
    }

    def __init__(self, concurrency):
        self.concurrency = concurrency

    def before_task_start(self, task):
        super(ConcurrencyPolicy, self).before_task_start(task)

        if self.concurrency == 0:
            return

        # This policy doesn't do anything except validating "concurrency"
        # property value and setting a variable into task runtime context.
        # This variable is then used to define how many action executions
        # may be started in parallel.
        ctx_key = 'concurrency'

        task.set_runtime_context_value(ctx_key, self.concurrency)


class FailOnPolicy(base.TaskPolicy):
    _schema = {
        "properties": {
            "fail-on": {"type": "boolean"},
        }
    }

    def __init__(self, fail_on):
        self.fail_on = fail_on

    def before_task_start(self, task):
        pass

    def after_task_complete(self, task):
        super(FailOnPolicy, self).after_task_complete(task)

        if task.get_state() != states.SUCCESS:
            return

        if self.fail_on:
            task.set_state(states.ERROR, "Failed by 'fail-on' policy")


@db_utils.retry_on_db_error
@post_tx_queue.run
def _continue_task(task_ex_id):
    from mistral.engine import task_handler

    with db_api.transaction():
        task_ex = db_api.load_task_execution(task_ex_id)

        task_handler.continue_task(task_ex)


@db_utils.retry_on_db_error
@post_tx_queue.run
def _complete_task(task_ex_id, state, state_info):
    from mistral.engine import task_handler

    with db_api.transaction():
        task_ex = db_api.load_task_execution(task_ex_id)

        task_handler.complete_task(task_ex, state, state_info)


@db_utils.retry_on_db_error
@post_tx_queue.run
def _fail_task_if_incomplete(task_ex_id, timeout):
    from mistral.engine import task_handler

    with db_api.transaction():
        task_ex = db_api.load_task_execution(task_ex_id)

        if not states.is_completed(task_ex.state):
            msg = 'Task timed out [timeout(s)=%s].' % timeout

            task_handler.complete_task(task_ex, states.ERROR, msg)
