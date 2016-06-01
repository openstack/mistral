# Copyright 2015 - Mirantis, Inc.
# Copyright 2015 - StackStorm, Inc.
# Copyright 2016 - Nokia Networks.
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

from oslo_log import log as logging
import traceback as tb

from mistral.engine import tasks
from mistral.engine import workflow_handler as wf_handler
from mistral import exceptions as exc
from mistral.workbook import parser as spec_parser
from mistral.workflow import commands as wf_cmds
from mistral.workflow import states


"""Responsible for running tasks and handling results."""

LOG = logging.getLogger(__name__)


def run_task(wf_cmd):
    """Runs workflow task.

    :param wf_cmd: Workflow command.
    """

    task = _build_task_from_command(wf_cmd)

    try:
        task.run()
    except exc.MistralException as e:
        wf_ex = wf_cmd.wf_ex
        task_spec = wf_cmd.task_spec

        msg = (
            "Failed to run task [wf=%s, task=%s]: %s\n%s" %
            (wf_ex, task_spec.get_name(), e, tb.format_exc())
        )

        LOG.error(msg)

        task.set_state(states.ERROR, msg)

        wf_handler.fail_workflow(wf_ex, msg)

        return

    if task.is_completed():
        wf_handler.check_workflow_completion(wf_cmd.wf_ex)


def on_action_complete(action_ex):
    """Handles action completion event.

    :param action_ex: Action execution.
    """

    task_ex = action_ex.task_execution

    if not task_ex:
        return

    task_spec = spec_parser.get_task_spec(task_ex.spec)

    wf_ex = task_ex.workflow_execution

    task = _create_task(
        wf_ex,
        task_spec,
        task_ex.in_context,
        task_ex
    )

    try:
        task.on_action_complete(action_ex)
    except exc.MistralException as e:
        task_ex = action_ex.task_execution
        wf_ex = task_ex.workflow_execution

        msg = ("Failed to handle action completion [wf=%s, task=%s,"
               " action=%s]: %s\n%s" %
               (wf_ex.name, task_ex.name, action_ex.name, e, tb.format_exc()))

        LOG.error(msg)

        task.set_state(states.ERROR, msg)

        wf_handler.fail_workflow(wf_ex, msg)

        return

    if task.is_completed():
        wf_handler.check_workflow_completion(wf_ex)


def fail_task(task_ex, msg):
    task = _build_task_from_execution(task_ex)

    task.set_state(states.ERROR, msg)

    wf_handler.fail_workflow(task_ex.workflow_execution, msg)


def continue_task(task_ex):
    task = _build_task_from_execution(task_ex)

    # TODO(rakhmerov): Error handling.
    task.run()

    if task.is_completed():
        wf_handler.check_workflow_completion(task_ex.workflow_execution)


def complete_task(task_ex, state, state_info):
    task = _build_task_from_execution(task_ex)

    # TODO(rakhmerov): Error handling.
    task.complete(state, state_info)

    if task.is_completed():
        wf_handler.check_workflow_completion(task_ex.workflow_execution)


def _build_task_from_execution(task_ex, task_spec=None):
    return _create_task(
        task_ex.workflow_execution,
        task_spec or spec_parser.get_task_spec(task_ex.spec),
        task_ex.in_context,
        task_ex
    )


def _build_task_from_command(cmd):
    if isinstance(cmd, wf_cmds.RunExistingTask):
        task = _create_task(
            cmd.wf_ex,
            spec_parser.get_task_spec(cmd.task_ex.spec),
            cmd.ctx,
            cmd.task_ex
        )

        if cmd.reset:
            task.reset()

        return task

    if isinstance(cmd, wf_cmds.RunTask):
        task = _create_task(cmd.wf_ex, cmd.task_spec, cmd.ctx)

        if cmd.is_waiting():
            task.defer()

        return task

    raise exc.MistralError('Unsupported workflow command: %s' % cmd)


def _create_task(wf_ex, task_spec, ctx, task_ex=None):
    if task_spec.get_with_items():
        return tasks.WithItemsTask(wf_ex, task_spec, ctx, task_ex)

    return tasks.RegularTask(wf_ex, task_spec, ctx, task_ex)
