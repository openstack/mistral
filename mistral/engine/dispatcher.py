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

BACKLOG_KEY = 'backlog_commands'


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
    cmds = list([c for c in cmds if not isinstance(c, commands.Noop)])

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
    elif (state_cmd_idx == 0 and
            not isinstance(state_cmd, commands.PauseWorkflow)):
        return cmds[0:1]

    res = cmds[0:state_cmd_idx]

    res.sort(key=functools.cmp_to_key(_compare_task_commands))

    res.append(state_cmd)

    # If the previously found state changing command is 'pause' then we need
    # to also add a tail of the initial command list to the result so that
    # we can save them to the command backlog.
    if isinstance(state_cmd, commands.PauseWorkflow):
        res.extend(cmds[state_cmd_idx + 1:])

    return res


def _save_command_to_backlog(wf_ex, cmd):
    backlog_cmds = wf_ex.runtime_context.get(BACKLOG_KEY, [])

    if not backlog_cmds:
        wf_ex.runtime_context[BACKLOG_KEY] = backlog_cmds

    backlog_cmds.append(cmd.to_dict())


def _poll_commands_from_backlog(wf_ex):
    # NOTE: We need to always use a guard condition that checks
    # if a persistent structure is empty and, as in this case,
    # return immediately w/o doing any further manipulations.
    # Otherwise, if we do pop() operation with a default value
    # then the ORM framework will consider it a modification of
    # the persistent object and generate a corresponding SQL
    # UPDATE operation. In this particular case it will increase
    # contention for workflow executions table drastically and
    # decrease performance.
    if not wf_ex.runtime_context.get(BACKLOG_KEY):
        return []

    backlog_cmds = wf_ex.runtime_context.pop(BACKLOG_KEY)

    return [
        commands.restore_command_from_dict(wf_ex, cmd_dict)
        for cmd_dict in backlog_cmds
    ]


@profiler.trace('dispatcher-dispatch-commands', hide_args=True)
def dispatch_workflow_commands(wf_ex, wf_cmds):
    # Run commands from the backlog.
    _process_commands(wf_ex, _poll_commands_from_backlog(wf_ex))

    # Run new commands.
    _process_commands(wf_ex, wf_cmds)


def _process_commands(wf_ex, cmds):
    if not cmds:
        return

    from mistral.engine import task_handler
    from mistral.engine import workflow_handler as wf_handler

    for cmd in _rearrange_commands(cmds):
        if states.is_completed(wf_ex.state):
            break

        if wf_ex.state == states.PAUSED:
            # Save all commands after 'pause' to the backlog so that
            # they can be processed after the workflow is resumed.
            _save_command_to_backlog(wf_ex, cmd)

            continue

        if isinstance(cmd, (commands.RunTask, commands.RunExistingTask)):
            task_handler.run_task(cmd)
        elif isinstance(cmd, commands.SetWorkflowState):
            wf_handler.set_workflow_state(wf_ex, cmd.new_state, cmd.msg)
        else:
            raise exc.MistralError('Unsupported workflow command: %s' % cmd)
