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

from mistral.workbook import parser as spec_parser
from mistral.workflow import states


class WorkflowCommand(object):
    """Workflow command.

    A set of workflow commands form a communication protocol between workflow
    handler and its clients. When workflow handler makes a decision about
    how to continue a workflow it returns a set of commands so that a caller
    knows what to do next.
    """

    def __init__(self, wf_ex, task_spec, ctx):
        self.wf_ex = wf_ex
        self.task_spec = task_spec
        self.ctx = ctx or {}


class Noop(WorkflowCommand):
    """No-operation command."""

    def __repr__(self):
        return "NOOP [workflow=%s]" % self.wf_ex.name


class RunTask(WorkflowCommand):
    """Instruction to run a workflow task."""

    def __repr__(self):
        return (
            "Run task [workflow=%s, task=%s]"
            % (self.wf_ex.name, self.task_spec.get_name())
        )


class RunExistingTask(WorkflowCommand):
    """Command for running already existent task."""

    def __init__(self, task_ex):
        wf_ex = task_ex.workflow_execution
        task_spec = spec_parser.get_task_spec(task_ex.spec)
        self.task_ex = task_ex

        super(RunExistingTask, self).__init__(
            wf_ex, task_spec, task_ex.in_context
        )


class SetWorkflowState(WorkflowCommand):
    """Instruction to change a workflow state."""

    def __init__(self, wf_ex, task_spec, ctx, new_state, msg):
        super(SetWorkflowState, self).__init__(wf_ex, task_spec, ctx)

        self.new_state = new_state
        self.msg = msg


class FailWorkflow(SetWorkflowState):
    """Instruction to fail a workflow."""

    def __init__(self, wf_ex, task_spec, ctx, msg=None):
        super(FailWorkflow, self).__init__(
            wf_ex,
            task_spec,
            ctx,
            states.ERROR,
            msg
        )

    def __repr__(self):
        return "Fail [workflow=%s]" % self.wf_ex.name


class SucceedWorkflow(SetWorkflowState):
    """Instruction to succeed a workflow."""

    def __init__(self, wf_ex, task_spec, ctx, msg=None):
        super(SucceedWorkflow, self).__init__(
            wf_ex,
            task_spec,
            ctx,
            states.SUCCESS,
            msg
        )

    def __repr__(self):
        return "Succeed [workflow=%s]" % self.wf_ex.name


class PauseWorkflow(SetWorkflowState):
    """Instruction to pause a workflow."""

    def __init__(self, wf_ex, task_spec, ctx, msg=None):
        super(PauseWorkflow, self).__init__(
            wf_ex,
            task_spec,
            ctx,
            states.PAUSED,
            msg
        )

    def __repr__(self):
        return "Pause [workflow=%s]" % self.wf_ex.name


RESERVED_CMDS = {
    'noop': Noop,
    'fail': FailWorkflow,
    'succeed': SucceedWorkflow,
    'pause': PauseWorkflow
}


def get_command_class(cmd_name):
    return RESERVED_CMDS[cmd_name] if cmd_name in RESERVED_CMDS else None


def create_command(cmd_name, wf_ex, task_spec, ctx):
    cmd_cls = get_command_class(cmd_name) or RunTask

    return cmd_cls(wf_ex, task_spec, ctx)
