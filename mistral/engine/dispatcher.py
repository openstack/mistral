# Copyright 2016 - Nokia Networks
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


from mistral import exceptions as exc
from mistral.workflow import commands
from mistral.workflow import states


def dispatch_workflow_commands(wf_ex, wf_cmds):
    # TODO(rakhmerov): I don't like these imports but otherwise we have
    # import cycles.
    from mistral.engine import task_handler
    from mistral.engine import workflow_handler as wf_handler

    if not wf_cmds:
        return

    for cmd in wf_cmds:
        if isinstance(cmd, (commands.RunTask, commands.RunExistingTask)):
            task_handler.run_task(cmd)
        elif isinstance(cmd, commands.SetWorkflowState):
            # TODO(rakhmerov): Make just a single call to workflow_handler
            if states.is_completed(cmd.new_state):
                wf_handler.stop_workflow(cmd.wf_ex, cmd.new_state, cmd.msg)
            else:
                wf_handler.set_workflow_state(wf_ex, cmd.new_state, cmd.msg)
        elif isinstance(cmd, commands.Noop):
            # Do nothing.
            pass
        else:
            raise exc.MistralError('Unsupported workflow command: %s' % cmd)

        if wf_ex.state != states.RUNNING:
            break
