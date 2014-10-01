# -*- coding: utf-8 -*-
#
# Copyright 2014 - Mirantis, Inc.
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

from oslo.config import cfg

from mistral.db.v2 import api as db_api
from mistral.engine import states
from mistral.engine1 import base
from mistral.engine1 import rpc
from mistral import expressions
from mistral.openstack.common import log as logging
from mistral.services import scheduler
from mistral.workflow import utils


WF_TRACE = logging.getLogger(cfg.CONF.workflow_trace_log_name)

_ENGINE_CLIENT_PATH = 'mistral.engine1.rpc.get_engine_client'


def _log_task_delay(task_name, state_from, delay_sec):
    WF_TRACE.info(
        "Task '%s' [%s -> %s, delay = %s sec]" %
        (task_name, state_from, states.DELAYED, delay_sec)
    )


def build_policies(policies_spec, wf_spec):
    task_defaults = wf_spec.get_task_defaults()
    wf_policies = task_defaults.get_policies() if task_defaults else None

    if not (policies_spec or wf_policies):
        return []

    return construct_policies_list(policies_spec, wf_policies)


def get_policy_factories():
    return [
        build_wait_before_policy,
        build_wait_after_policy,
        build_retry_policy,
        build_timeout_policy
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
    wait_before = policies_spec.get_wait_before()

    return WaitBeforePolicy(wait_before) if wait_before > 0 else None


def build_wait_after_policy(policies_spec):
    wait_after = policies_spec.get_wait_after()

    return WaitAfterPolicy(wait_after) if wait_after > 0 else None


def build_retry_policy(policies_spec):
    retry = policies_spec.get_retry()

    if not retry:
        return None

    return RetryPolicy(
        retry.get_count(),
        retry.get_delay(),
        retry.get_break_on()
    )


def build_timeout_policy(policies_spec):
    timeout_policy = policies_spec.get_timeout()

    return TimeoutPolicy(timeout_policy) if timeout_policy > 0 else None


def _ensure_context_has_key(runtime_context, key):
    if not runtime_context:
        runtime_context = {}

    if key not in runtime_context:
        runtime_context.update({key: {}})

    return runtime_context


class WaitBeforePolicy(base.TaskPolicy):
    def __init__(self, delay):
        self.delay = delay

    def before_task_start(self, task_db, task_spec):
        context_key = 'wait_before_policy'

        runtime_context = _ensure_context_has_key(
            task_db.runtime_context,
            context_key
        )

        task_db.runtime_context = runtime_context

        policy_context = runtime_context[context_key]

        if policy_context.get('skip'):
            # Unset state 'DELAYED'.
            WF_TRACE.info(
                "Task '%s' [%s -> %s]"
                % (task_db.name, states.DELAYED, states.RUNNING)
            )

            task_db.state = states.RUNNING

            return

        policy_context.update({'skip': True})

        _log_task_delay(task_db.name, task_db.state, self.delay)

        task_db.state = states.DELAYED

        scheduler.schedule_call(
            _ENGINE_CLIENT_PATH,
            'run_task',
            self.delay,
            task_id=task_db.id
        )


class WaitAfterPolicy(base.TaskPolicy):
    def __init__(self, delay):
        self.delay = delay

    def after_task_complete(self, task_db, task_spec, raw_result):
        context_key = 'wait_after_policy'

        runtime_context = _ensure_context_has_key(
            task_db.runtime_context,
            context_key
        )

        task_db.runtime_context = runtime_context

        policy_context = runtime_context[context_key]

        if policy_context.get('skip'):
            # Need to avoid terminal states.
            if not states.is_finished(task_db.state):
                # Unset state 'DELAYED'.

                WF_TRACE.info(
                    "Task '%s' [%s -> %s]"
                    % (task_db.name, states.DELAYED, states.RUNNING)
                )

                task_db.state = states.RUNNING

            return

        policy_context.update({'skip': True})

        _log_task_delay(task_db.name, task_db.state, self.delay)

        # Set task state to 'DELAYED'.
        task_db.state = states.DELAYED

        serializers = {
            'raw_result': 'mistral.workflow.utils.TaskResultSerializer'
        }

        scheduler.schedule_call(
            _ENGINE_CLIENT_PATH,
            'on_task_result',
            self.delay,
            serializers,
            task_id=task_db.id,
            raw_result=raw_result
        )


class RetryPolicy(base.TaskPolicy):
    def __init__(self, count, delay, break_on):
        self.count = count
        self.delay = delay
        self.break_on = break_on

    def after_task_complete(self, task_db, task_spec, raw_result):
        """Possible Cases:

        1. state = SUCCESS
           No need to move to next iteration.
        2. retry:count = 5, current:count = 2, state = ERROR,
           state = IDLE/DELAYED, current:count = 3
        3. retry:count = 5, current:count = 4, state = ERROR
        Iterations complete therefore state = #{state}, current:count = 4.
        """
        context_key = 'retry_task_policy'

        runtime_context = _ensure_context_has_key(
            task_db.runtime_context,
            context_key
        )

        task_db.runtime_context = runtime_context

        state = states.ERROR if raw_result.is_error() else states.SUCCESS

        if state != states.ERROR:
            return

        WF_TRACE.info(
            "Task '%s' [%s -> ERROR]"
            % (task_db.name, task_db.state)
        )

        outbound_context = task_db.output

        policy_context = runtime_context[context_key]
        retry_no = 0

        if "retry_no" in policy_context:
            retry_no = policy_context["retry_no"]
            del policy_context["retry_no"]

        retries_remain = retry_no + 1 < self.count

        break_early = (
            expressions.evaluate(self.break_on, outbound_context)
            if self.break_on and outbound_context else False
        )

        if not retries_remain or break_early:
            return

        task_db.state = states.DELAYED
        retry_no += 1
        policy_context.update({'retry_no': retry_no})
        runtime_context.update({context_key: policy_context})

        _log_task_delay(task_db.name, state, self.delay)

        scheduler.schedule_call(
            _ENGINE_CLIENT_PATH,
            'run_task',
            self.delay,
            task_id=task_db.id
        )


class TimeoutPolicy(base.TaskPolicy):
    def __init__(self, timeout_sec):
        self.delay = timeout_sec

    def before_task_start(self, task_db, task_spec):
        scheduler.schedule_call(
            None,
            'mistral.engine1.policies.fail_task_if_incomplete',
            self.delay,
            task_id=task_db.id,
            timeout=self.delay
        )

        WF_TRACE.info("Timeout check scheduled [task=%s, timeout(s)=%s]."
                      % (task_db.id, self.delay))


def fail_task_if_incomplete(task_id, timeout):
    task_db = db_api.get_task(task_id)

    if not states.is_finished(task_db.state):
        msg = "Task timed out [task=%s, timeout(s)=%s]." % (task_id, timeout)

        WF_TRACE.info(msg)

        WF_TRACE.info(
            "Task '%s' [%s -> ERROR]"
            % (task_db.name, task_db.state)
        )

        rpc.get_engine_client().on_task_result(
            task_id,
            utils.TaskResult(error=msg)
        )
