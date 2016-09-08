# Copyright 2016 - Nokia Networks
# Copyright 2016 - Brocade Communications Systems, Inc.
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

import functools
from osprofiler import profiler

from mistral import exceptions as exc
from mistral.workflow import commands
from mistral.workflow import states


def _compare_task_commands(a, b):
    if not isinstance(a, commands.RunTask) or not a.is_waiting():
        return -1

    if not isinstance(b, commands.RunTask) or not b.is_waiting():
        return 1

    if a.unique_key == b.unique_key:
        return 0

    if a.unique_key < b.unique_key:
        return -1

    return 1


def _rearrange_commands(cmds):
    """Takes workflow commands and does required pre-processing.

    The main idea of the method is to sort task commands with 'waiting'
    flag by 'unique_key' property in order guarantee the same locking
    order for them in parallel transactions and thereby prevent deadlocks.
    It also removes commands that don't make sense. For example, if
    there are some commands after a command that changes a workflow state
    then they must not be dispatched.
    """

    # Remove all 'noop' commands.
    cmds = list(filter(lambda c: not isinstance(c, commands.Noop), cmds))

    state_cmd_idx = -1
    state_cmd = None

    for i, cmd in enumerate(cmds):
        if isinstance(cmd, commands.SetWorkflowState):
            state_cmd_idx = i
            state_cmd = cmd

            break

    # Find a position of a 'fail|succeed|pause' command
    # and sort all task commands before it.
    if state_cmd_idx < 0:
        cmds.sort(key=functools.cmp_to_key(_compare_task_commands))

        return cmds
    elif state_cmd_idx == 0:
        return cmds[0:1]

    res = cmds[0:state_cmd_idx]

    res.sort(key=functools.cmp_to_key(_compare_task_commands))

    res.append(state_cmd)

    return res


@profiler.trace('dispatcher-dispatch-commands')
def dispatch_workflow_commands(wf_ex, wf_cmds):
    # TODO(rakhmerov): I don't like these imports but otherwise we have
    # import cycles.
    from mistral.engine import task_handler
    from mistral.engine import workflow_handler as wf_handler

    if not wf_cmds:
        return

    for cmd in _rearrange_commands(wf_cmds):
        if isinstance(cmd, (commands.RunTask, commands.RunExistingTask)):
            task_handler.run_task(cmd)
        elif isinstance(cmd, commands.SetWorkflowState):
            wf_handler.set_workflow_state(wf_ex, cmd.new_state, cmd.msg)
        else:
            raise exc.MistralError('Unsupported workflow command: %s' % cmd)

        if wf_ex.state != states.RUNNING:
            break
