# Copyright 2015 - Mirantis, Inc.
# Copyright 2015 - StackStorm, Inc.
# Copyright 2016 - Nokia Networks.
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

from oslo_log import log as logging
from osprofiler import profiler
import traceback as tb

from mistral.db.v2 import api as db_api
from mistral.db.v2.sqlalchemy import models
from mistral.engine import tasks
from mistral.engine import workflow_handler as wf_handler
from mistral import exceptions as exc
from mistral.services import scheduler
from mistral.workbook import parser as spec_parser
from mistral.workflow import base as wf_base
from mistral.workflow import commands as wf_cmds
from mistral.workflow import states


"""Responsible for running tasks and handling results."""

LOG = logging.getLogger(__name__)

_REFRESH_TASK_STATE_PATH = (
    'mistral.engine.task_handler._refresh_task_state'
)

_SCHEDULED_ON_ACTION_COMPLETE_PATH = (
    'mistral.engine.task_handler._scheduled_on_action_complete'
)


@profiler.trace('task-handler-run-task')
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

    if task.is_waiting() and (task.is_created() or task.is_state_changed()):
        _schedule_refresh_task_state(task.task_ex, 1)


@profiler.trace('task-handler-on-action-complete')
def _on_action_complete(action_ex):
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
        spec_parser.get_workflow_spec_by_execution_id(wf_ex.id),
        task_spec,
        task_ex.in_context,
        task_ex
    )

    try:
        task.on_action_complete(action_ex)
    except exc.MistralException as e:
        wf_ex = task_ex.workflow_execution

        msg = ("Failed to handle action completion [wf=%s, task=%s,"
               " action=%s]: %s\n%s" %
               (wf_ex.name, task_ex.name, action_ex.name, e, tb.format_exc()))

        LOG.error(msg)

        task.set_state(states.ERROR, msg)

        wf_handler.fail_workflow(wf_ex, msg)

        return


def fail_task(task_ex, msg):
    wf_spec = spec_parser.get_workflow_spec_by_execution_id(
        task_ex.workflow_execution_id
    )

    task = _build_task_from_execution(wf_spec, task_ex)

    task.set_state(states.ERROR, msg)

    wf_handler.fail_workflow(task_ex.workflow_execution, msg)


def continue_task(task_ex):
    wf_spec = spec_parser.get_workflow_spec_by_execution_id(
        task_ex.workflow_execution_id
    )

    task = _build_task_from_execution(wf_spec, task_ex)

    try:
        task.set_state(states.RUNNING, None)

        task.run()
    except exc.MistralException as e:
        wf_ex = task_ex.workflow_execution

        msg = (
            "Failed to run task [wf=%s, task=%s]: %s\n%s" %
            (wf_ex, task_ex.name, e, tb.format_exc())
        )

        LOG.error(msg)

        task.set_state(states.ERROR, msg)

        wf_handler.fail_workflow(wf_ex, msg)

        return


def complete_task(task_ex, state, state_info):
    wf_spec = spec_parser.get_workflow_spec_by_execution_id(
        task_ex.workflow_execution_id
    )

    task = _build_task_from_execution(wf_spec, task_ex)

    try:
        task.complete(state, state_info)
    except exc.MistralException as e:
        wf_ex = task_ex.workflow_execution

        msg = (
            "Failed to complete task [wf=%s, task=%s]: %s\n%s" %
            (wf_ex, task_ex.name, e, tb.format_exc())
        )

        LOG.error(msg)

        task.set_state(states.ERROR, msg)

        wf_handler.fail_workflow(wf_ex, msg)

        return


def _build_task_from_execution(wf_spec, task_ex):
    return _create_task(
        task_ex.workflow_execution,
        wf_spec,
        wf_spec.get_task(task_ex.name),
        task_ex.in_context,
        task_ex
    )


@profiler.trace('task-handler-build-task-from-command')
def _build_task_from_command(cmd):
    if isinstance(cmd, wf_cmds.RunExistingTask):
        task = _create_task(
            cmd.wf_ex,
            cmd.wf_spec,
            spec_parser.get_task_spec(cmd.task_ex.spec),
            cmd.ctx,
            task_ex=cmd.task_ex,
            unique_key=cmd.task_ex.unique_key,
            waiting=cmd.task_ex.state == states.WAITING
        )

        if cmd.reset:
            task.reset()

        return task

    if isinstance(cmd, wf_cmds.RunTask):
        task = _create_task(
            cmd.wf_ex,
            cmd.wf_spec,
            cmd.task_spec,
            cmd.ctx,
            unique_key=cmd.unique_key,
            waiting=cmd.is_waiting()
        )

        return task

    raise exc.MistralError('Unsupported workflow command: %s' % cmd)


def _create_task(wf_ex, wf_spec, task_spec, ctx, task_ex=None,
                 unique_key=None, waiting=False):
    if task_spec.get_with_items():
        cls = tasks.WithItemsTask
    else:
        cls = tasks.RegularTask

    return cls(wf_ex, wf_spec, task_spec, ctx, task_ex, unique_key, waiting)


@profiler.trace('task-handler-refresh-task-state')
def _refresh_task_state(task_ex_id):
    with db_api.transaction():
        task_ex = db_api.load_task_execution(task_ex_id)

        if not task_ex:
            return

        wf_ex = task_ex.workflow_execution

        if states.is_completed(wf_ex.state):
            return

        wf_spec = spec_parser.get_workflow_spec_by_execution_id(
            task_ex.workflow_execution_id
        )

        wf_ctrl = wf_base.get_controller(wf_ex, wf_spec)

        state, state_info, cardinality = wf_ctrl.get_logical_task_state(
            task_ex
        )

        if state == states.RUNNING:
            continue_task(task_ex)
        elif state == states.ERROR:
            fail_task(task_ex, state_info)
        elif state == states.WAITING:
            # Let's assume that a task takes 0.01 sec in average to complete
            # and based on this assumption calculate a time of the next check.
            # The estimation is very rough, of course, but this delay will be
            # decreasing as task preconditions will be completing which will
            # give a decent asymptotic approximation.
            # For example, if a 'join' task has 100 inbound incomplete tasks
            # then the next 'refresh_task_state' call will happen in 10
            # seconds. For 500 tasks it will be 50 seconds. The larger the
            # workflow is, the more beneficial this mechanism will be.
            delay = int(cardinality * 0.01)

            _schedule_refresh_task_state(task_ex, max(1, delay))
        else:
            # Must never get here.
            raise RuntimeError(
                'Unexpected logical task state [task_ex=%s, state=%s]' %
                (task_ex, state)
            )


def _schedule_refresh_task_state(task_ex, delay=0):
    """Schedules task preconditions check.

    This method provides transactional decoupling of task preconditions
    check from events that can potentially satisfy those preconditions.

    It's needed in non-locking model in order to avoid 'phantom read'
    phenomena when reading state of multiple tasks to see if a task that
    depends on them can start. Just starting a separate transaction
    without using scheduler is not safe due to concurrency window that
    we'll have in this case (time between transactions) whereas scheduler
    is a special component that is designed to be resistant to failures.

    :param task_ex: Task execution.
    :param delay: Delay.
    """
    key = 'th_c_t_s_a-%s' % task_ex.id

    scheduler.schedule_call(
        None,
        _REFRESH_TASK_STATE_PATH,
        delay,
        key=key,
        task_ex_id=task_ex.id
    )


def _scheduled_on_action_complete(action_ex_id, wf_action):
    with db_api.transaction():
        if wf_action:
            action_ex = db_api.get_workflow_execution(action_ex_id)
        else:
            action_ex = db_api.get_action_execution(action_ex_id)

        _on_action_complete(action_ex)


def schedule_on_action_complete(action_ex, delay=0):
    """Schedules task completion check.

    This method provides transactional decoupling of action completion from
    task completion check. It's needed in non-locking model in order to
    avoid 'phantom read' phenomena when reading state of multiple actions
    to see if a task is completed. Just starting a separate transaction
    without using scheduler is not safe due to concurrency window that we'll
    have in this case (time between transactions) whereas scheduler is a
    special component that is designed to be resistant to failures.

    :param action_ex: Action execution.
    :param delay: Minimum amount of time before task completion check
        should be made.
    """

    # Optimization to avoid opening a new transaction if it's not needed.
    if not action_ex.task_execution.spec.get('with-items'):
        _on_action_complete(action_ex)

        return

    key = 'th_on_a_c-%s' % action_ex.task_execution_id

    scheduler.schedule_call(
        None,
        _SCHEDULED_ON_ACTION_COMPLETE_PATH,
        delay,
        key=key,
        action_ex_id=action_ex.id,
        wf_action=isinstance(action_ex, models.WorkflowExecution)
    )
