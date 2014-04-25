# -*- coding: utf-8 -*-
#
# Copyright 2014 - StackStorm, Inc.
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

from oslo.config import cfg

from mistral import expressions
from mistral.engine import states
from mistral.openstack.common import log as logging


WORKFLOW_TRACE = logging.getLogger(cfg.CONF.workflow_trace_log_name)


def get_task_runtime(task_spec, state=states.IDLE, outbound_context=None,
                     task_runtime_context=None):
    """
    Computes the state and exec_flow_context runtime properties for a task
    based on the supplied properties. This method takes the retry nature of a
    task into consideration.

    :param task_spec: specification of the task
    :param state: suggested next state
    :param outbound_context: outbound_context to be used for computation
    :param task_runtime_context: current flow context
    :return: state, exec_flow_context tuple. Sample scenarios are,
    1. state = SUCCESS
       No need to move to next iteration.
    2. retry:count = 5, current:count = 2, state = ERROR,
       state = IDLE/DELAYED, current:count = 3
    3. retry:count = 5, current:count = 4, state = ERROR
    Iterations complete therefore state = #{state}, current:count = 4.
    """

    if not (state == states.ERROR and task_spec.is_retry_task()):
        return state, task_runtime_context

    if task_runtime_context is None:
        task_runtime_context = {}
    if outbound_context is None:
        outbound_context = {}

    wf_trace_msg = "Task '%s' [%s -> " % (task_spec.name, state)

    retry_no = -1
    if "retry_no" in task_runtime_context:
        retry_no = task_runtime_context["retry_no"]
    retry_count, break_on, delay = task_spec.get_retry_parameters()

    retries_remain = retry_no + 1 < retry_count
    break_early = expressions.evaluate(break_on, outbound_context) if \
        break_on and outbound_context else False

    if retries_remain and not break_early:
        state = states.DELAYED if delay > 0 else states.IDLE
        retry_no += 1

    WORKFLOW_TRACE.info(wf_trace_msg + "%s, delay = %s sec]" % (state, delay))

    task_runtime_context["retry_no"] = retry_no

    return state, task_runtime_context
