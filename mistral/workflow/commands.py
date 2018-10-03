# Copyright 2015 - Mirantis, Inc.
# Copyright 2015 - StackStorm, Inc.
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

from mistral.lang import parser as spec_parser
from mistral.lang.v2 import workflows
from mistral.workflow import states


class WorkflowCommand(object):
    """Workflow command.

    A set of workflow commands form a communication protocol between workflow
    controller and its clients. When workflow controller makes a decision about
    how to continue a workflow it returns a set of commands so that a caller
    knows what to do next.
    """

    def __init__(self, wf_ex, wf_spec, task_spec, ctx, triggered_by=None):
        self.wf_ex = wf_ex
        self.wf_spec = wf_spec
        self.task_spec = task_spec
        self.ctx = ctx or {}
        self.triggered_by = triggered_by

    def to_dict(self):
        return {
            'task_name': self.task_spec.get_name(),
            'ctx': self.ctx,
            'triggered_by': self.triggered_by
        }


class Noop(WorkflowCommand):
    """No-operation command."""

    def __repr__(self):
        return "NOOP [workflow=%s]" % self.wf_ex.name

    def to_dict(self):
        d = super(Noop, self).to_dict()

        d['cmd_name'] = 'noop'

        return d


class RunTask(WorkflowCommand):
    """Instruction to run a workflow task."""

    def __init__(self, wf_ex, wf_spec, task_spec, ctx, triggered_by=None):
        super(RunTask, self).__init__(
            wf_ex,
            wf_spec,
            task_spec,
            ctx,
            triggered_by=triggered_by
        )

        self.wait = False
        self.unique_key = None

    def is_waiting(self):
        return self.wait

    def get_unique_key(self):
        return self.unique_key

    def __repr__(self):
        return (
            "Run task [workflow=%s, task=%s, waif_flag=%s, triggered_by=%s]" %
            (
                self.wf_ex.name,
                self.task_spec.get_name(),
                self.wait,
                self.triggered_by
            )
        )

    def to_dict(self):
        d = super(RunTask, self).to_dict()

        d['cmd_name'] = self.task_spec.get_name()
        d['wait'] = self.wait
        d['unique_key'] = self.unique_key

        return d


class RunExistingTask(WorkflowCommand):
    """Command to run an existing workflow task."""

    def __init__(self, wf_ex, wf_spec, task_ex, reset=True, triggered_by=None,
                 rerun=False):
        super(RunExistingTask, self).__init__(
            wf_ex,
            wf_spec,
            spec_parser.get_task_spec(task_ex.spec),
            task_ex.in_context,
            triggered_by=triggered_by
        )

        self.task_ex = task_ex
        self.reset = reset
        self.unique_key = task_ex.unique_key
        self.rerun = rerun

    def to_dict(self):
        d = super(RunExistingTask, self).to_dict()

        d['cmd_name'] = 'run_existing_task'
        d['task_ex_id'] = self.task_ex.id
        d['reset'] = self.reset
        d['unique_key'] = self.unique_key

        return d


class SetWorkflowState(WorkflowCommand):
    """Instruction to change a workflow state."""

    def __init__(self, wf_ex, wf_spec, task_spec, ctx, new_state, msg=None,
                 triggered_by=None):
        super(SetWorkflowState, self).__init__(
            wf_ex,
            wf_spec,
            task_spec,
            ctx,
            triggered_by=triggered_by
        )

        self.new_state = new_state
        self.msg = msg

    def to_dict(self):
        d = super(SetWorkflowState, self).to_dict()

        d['new_state'] = self.new_state
        d['msg'] = self.msg

        return d


class FailWorkflow(SetWorkflowState):
    """Instruction to fail a workflow."""

    def __init__(self, wf_ex, wf_spec, task_spec, ctx, msg=None,
                 triggered_by=None):
        super(FailWorkflow, self).__init__(
            wf_ex,
            wf_spec,
            task_spec,
            ctx,
            states.ERROR,
            msg=msg,
            triggered_by=triggered_by
        )

    def __repr__(self):
        return "Fail [workflow=%s]" % self.wf_ex.name

    def to_dict(self):
        d = super(FailWorkflow, self).to_dict()

        d['cmd_name'] = 'fail'

        return d


class SucceedWorkflow(SetWorkflowState):
    """Instruction to succeed a workflow."""

    def __init__(self, wf_ex, wf_spec, task_spec, ctx, msg=None,
                 triggered_by=None):
        super(SucceedWorkflow, self).__init__(
            wf_ex,
            wf_spec,
            task_spec,
            ctx,
            states.SUCCESS,
            msg=msg,
            triggered_by=triggered_by
        )

    def __repr__(self):
        return "Succeed [workflow=%s]" % self.wf_ex.name

    def to_dict(self):
        d = super(SucceedWorkflow, self).to_dict()

        d['cmd_name'] = 'succeed'

        return d


class PauseWorkflow(SetWorkflowState):
    """Instruction to pause a workflow."""

    def __init__(self, wf_ex, wf_spec, task_spec, ctx, msg=None,
                 triggered_by=None):
        super(PauseWorkflow, self).__init__(
            wf_ex,
            wf_spec,
            task_spec,
            ctx,
            states.PAUSED,
            msg=msg,
            triggered_by=triggered_by
        )

    def __repr__(self):
        return "Pause [workflow=%s]" % self.wf_ex.name

    def to_dict(self):
        d = super(PauseWorkflow, self).to_dict()

        d['cmd_name'] = 'pause'

        return d


ENGINE_CMD_CLS = {
    workflows.NOOP_COMMAND: Noop,
    workflows.FAIL_COMMAND: FailWorkflow,
    workflows.SUCCEED_COMMAND: SucceedWorkflow,
    workflows.PAUSE_COMMAND: PauseWorkflow
}


def get_command_class(cmd_name):
    return ENGINE_CMD_CLS[cmd_name] if cmd_name in ENGINE_CMD_CLS else None


# TODO(rakhmerov): IMO the way how we instantiate commands is weird.
# If we look at how we implement the logic of saving commands to
# dicts (to_dict) and restoring back from dicts then we'll see
# the lack of symmetry and unified way to do that depending on a
# command. Also RunExistingTask turns to be a special case that
# is not processed with this method at all. Might be a 'bad smell'.
# This all makes me think that we need to do some refactoring here.
def create_command(cmd_name, wf_ex, wf_spec, task_spec, ctx,
                   params=None, triggered_by=None):
    cmd_cls = get_command_class(cmd_name) or RunTask

    if issubclass(cmd_cls, SetWorkflowState):
        return cmd_cls(
            wf_ex,
            wf_spec,
            task_spec,
            ctx,
            msg=params.get('msg'),
            triggered_by=triggered_by
        )
    else:
        return cmd_cls(
            wf_ex,
            wf_spec,
            task_spec,
            ctx,
            triggered_by=triggered_by
        )


def restore_command_from_dict(wf_ex, cmd_dict):
    cmd_name = cmd_dict['cmd_name']

    wf_spec = spec_parser.get_workflow_spec_by_execution_id(wf_ex.id)
    task_spec = wf_spec.get_tasks()[cmd_dict['task_name']]
    ctx = cmd_dict['ctx']
    params = {'msg': cmd_dict.get('msg')} if 'msg' in cmd_dict else None
    triggered_by = cmd_dict.get('triggered_by')

    return create_command(
        cmd_name,
        wf_ex,
        wf_spec,
        task_spec,
        ctx,
        params,
        triggered_by
    )
