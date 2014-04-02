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

from mistral.engine import expressions
from mistral.engine import states


def get_task_runtime(task_spec, state=states.IDLE, outbound_context=None,
                     task_runtime_context=None):
    """
    Computes the state and exec_flow_context runtime properties for a task
    based on the supplied properties. This method takes the repeat nature of a
    task into consideration.

    :param task_spec: specification of the task
    :param state: suggested next state
    :param outbound_context: outbound_context to be used for computation
    :param task_runtime_context: current flow context
    :return: state, exec_flow_context tuple. Sample scenarios are,
    1. required iteration = 5, current iteration = 0, state = SUCCESS
       Move to next iteration therefore state = IDLE/DELAYED, iteration_no = 1.
    2. required iteration = 5, current iteration = 2, state = ERROR Stop task.
        state = ERROR, iteration_no = 2
    3. required iteration = 5, current iteration = 4, state = SUCCESS
    Iterations complete therefore state = SUCCESS, iteration_no = 4.

    """

    if states.is_stopped_or_unsuccessful_finish(state) or not \
            task_spec.is_repeater_task():
        return state, task_runtime_context

    if task_runtime_context is None:
        task_runtime_context = {}
    if outbound_context is None:
        outbound_context = {}

    iteration_no = -1
    if "iteration_no" in task_runtime_context:
        iteration_no = task_runtime_context["iteration_no"]
    iterations, break_on, delay = task_spec.get_repeat_task_parameters()

    iterations_incomplete = iteration_no + 1 < iterations
    break_early = expressions.evaluate(break_on, outbound_context) if \
        break_on and outbound_context else False

    if iterations_incomplete and break_early:
        state = states.SUCCESS
    elif iterations_incomplete:
        state = states.DELAYED if delay > 0 else states.IDLE
        iteration_no += 1
    elif not iterations_incomplete and state == states.IDLE:
        # This is the case where the iterations are complete but task is still
        # IDLE which implies SUCCESS. Can happen if repeat is specified but
        # 0 iterations are requested.
        state = states.SUCCESS

    task_runtime_context["iteration_no"] = iteration_no

    return state, task_runtime_context
