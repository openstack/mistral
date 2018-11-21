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

from mistral.db import utils as db_utils
from mistral.db.v2 import api as db_api
from mistral.db.v2.sqlalchemy import models
from mistral.engine import post_tx_queue
from mistral.engine import tasks
from mistral.engine import workflow_handler as wf_handler
from mistral import exceptions as exc
from mistral.lang import parser as spec_parser
from mistral.services import scheduler
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

_SCHEDULED_ON_ACTION_UPDATE_PATH = (
    'mistral.engine.task_handler._scheduled_on_action_update'
)


@profiler.trace('task-handler-run-task', hide_args=True)
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
            "Failed to run task [error=%s, wf=%s, task=%s]:\n%s" %
            (e, wf_ex.name, task_spec.get_name(), tb.format_exc())
        )

        force_fail_task(task.task_ex, msg, task=task)

        return

    _check_affected_tasks(task)


def rerun_task(task_ex, wf_spec):
    task = _build_task_from_execution(wf_spec, task_ex)

    old_task_state = task_ex.state
    task.set_state(states.RUNNING, None, False)
    task.notify(old_task_state, states.RUNNING)


@profiler.trace('task-handler-on-action-complete', hide_args=True)
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

        msg = ("Failed to handle action completion [error=%s, wf=%s, task=%s,"
               " action=%s]:\n%s" %
               (e, wf_ex.name, task_ex.name, action_ex.name, tb.format_exc()))

        force_fail_task(task_ex, msg, task=task)

        return

    _check_affected_tasks(task)


@profiler.trace('task-handler-on-action-update', hide_args=True)
def _on_action_update(action_ex):
    """Handles action update event.

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
        task.on_action_update(action_ex)

        if states.is_paused(action_ex.state):
            wf_handler.pause_workflow(wf_ex)

        if states.is_running(action_ex.state):
            # If any subworkflow of the parent workflow is paused,
            # then keep the parent workflow execution paused.
            for task_ex in wf_ex.task_executions:
                if states.is_paused(task_ex.state):
                    return

            # Otherwise if no other subworkflow is paused,
            # then resume the parent workflow execution.
            wf_handler.resume_workflow(wf_ex)

    except exc.MistralException as e:
        wf_ex = task_ex.workflow_execution

        msg = ("Failed to handle action update [error=%s, wf=%s, task=%s,"
               " action=%s]:\n%s" %
               (e, wf_ex.name, task_ex.name, action_ex.name, tb.format_exc()))

        force_fail_task(task_ex, msg, task=task)

        return

    _check_affected_tasks(task)


def force_fail_task(task_ex, msg, task=None):
    """Forces the given task to fail.

    This method implements the 'forced' task fail without giving a chance
    to a workflow controller to handle the error. Its main purpose is to
    reflect errors caused by workflow structure (errors 'publish', 'on-xxx'
    clauses etc.) rather than failed actions. If such an error happens
    we should also force the entire workflow to fail. I.e., this kind of
    error must be propagated to a higher level, to the workflow.

    :param task_ex: Task execution.
    :param msg: Error message.
    :param task: Task object. Optional.
    """

    LOG.error(msg)

    if not task:
        wf_spec = spec_parser.get_workflow_spec_by_execution_id(
            task_ex.workflow_execution_id
        )

        task = _build_task_from_execution(wf_spec, task_ex)

    old_task_state = task_ex.state
    task.set_state(states.ERROR, msg)
    task.notify(old_task_state, states.ERROR)

    task.save_finished_time()

    wf_handler.force_fail_workflow(task_ex.workflow_execution, msg)


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
            "Failed to run task [error=%s, wf=%s, task=%s]:\n%s" %
            (e, wf_ex.name, task_ex.name, tb.format_exc())
        )

        force_fail_task(task_ex, msg, task=task)

        return

    _check_affected_tasks(task)


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
            "Failed to complete task [error=%s, wf=%s, task=%s]:\n%s" %
            (e, wf_ex.name, task_ex.name, tb.format_exc())
        )

        force_fail_task(task_ex, msg, task=task)

        return

    _check_affected_tasks(task)


@profiler.trace('task-handler-check-affected-tasks', hide_args=True)
def _check_affected_tasks(task):
    if not task.is_completed():
        return

    task_ex = task.task_ex

    wf_ex = task_ex.workflow_execution

    if states.is_completed(wf_ex.state):
        return

    wf_spec = spec_parser.get_workflow_spec_by_execution_id(
        task_ex.workflow_execution_id
    )

    wf_ctrl = wf_base.get_controller(wf_ex, wf_spec)

    affected_task_execs = wf_ctrl.find_indirectly_affected_task_executions(
        task_ex.name
    )

    def _schedule_if_needed(t_ex_id):
        # NOTE(rakhmerov): we need to minimize the number of delayed calls
        # that refresh state of "join" tasks. We'll check if corresponding
        # calls are already scheduled. Note that we must ignore delayed calls
        # that are currently being processed because of a possible race with
        # the transaction that deletes delayed calls, i.e. the call may still
        # exist in DB (the deleting transaction didn't commit yet) but it has
        # already been processed and the task state hasn't changed.
        cnt = db_api.get_delayed_calls_count(
            key=_get_refresh_state_job_key(t_ex_id),
            processing=False
        )

        if cnt == 0:
            _schedule_refresh_task_state(t_ex_id)

    for t_ex in affected_task_execs:
        post_tx_queue.register_operation(
            _schedule_if_needed,
            args=[t_ex.id],
            in_tx=True
        )


def _build_task_from_execution(wf_spec, task_ex):
    return _create_task(
        task_ex.workflow_execution,
        wf_spec,
        wf_spec.get_task(task_ex.name),
        task_ex.in_context,
        task_ex
    )


@profiler.trace('task-handler-build-task-from-command', hide_args=True)
def _build_task_from_command(cmd):
    if isinstance(cmd, wf_cmds.RunExistingTask):
        task = _create_task(
            cmd.wf_ex,
            cmd.wf_spec,
            spec_parser.get_task_spec(cmd.task_ex.spec),
            cmd.ctx,
            task_ex=cmd.task_ex,
            unique_key=cmd.task_ex.unique_key,
            waiting=cmd.task_ex.state == states.WAITING,
            triggered_by=cmd.triggered_by,
            rerun=cmd.rerun
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
            waiting=cmd.is_waiting(),
            triggered_by=cmd.triggered_by
        )

        return task

    raise exc.MistralError('Unsupported workflow command: %s' % cmd)


def _create_task(wf_ex, wf_spec, task_spec, ctx, task_ex=None,
                 unique_key=None, waiting=False, triggered_by=None,
                 rerun=False):
    if task_spec.get_with_items():
        cls = tasks.WithItemsTask
    else:
        cls = tasks.RegularTask

    return cls(
        wf_ex,
        wf_spec,
        task_spec,
        ctx,
        task_ex=task_ex,
        unique_key=unique_key,
        waiting=waiting,
        triggered_by=triggered_by,
        rerun=rerun
    )


@db_utils.retry_on_db_error
@post_tx_queue.run
@profiler.trace('task-handler-refresh-task-state', hide_args=True)
def _refresh_task_state(task_ex_id):
    with db_api.transaction():
        task_ex = db_api.load_task_execution(task_ex_id)

        if not task_ex:
            return

        if (states.is_completed(task_ex.state)
                or task_ex.state == states.RUNNING):
            return

        wf_ex = task_ex.workflow_execution

        if states.is_completed(wf_ex.state):
            return

        wf_spec = spec_parser.get_workflow_spec_by_execution_id(
            task_ex.workflow_execution_id
        )

        wf_ctrl = wf_base.get_controller(wf_ex, wf_spec)

        with db_api.named_lock(task_ex.id):
            # NOTE: we have to use this lock to prevent two (or more) such
            # methods from changing task state and starting its action or
            # workflow. Checking task state outside of this section is a
            # performance optimization because locking is pretty expensive.
            db_api.refresh(task_ex)

            if (states.is_completed(task_ex.state)
                    or task_ex.state == states.RUNNING):
                return

            log_state = wf_ctrl.get_logical_task_state(task_ex)

            state = log_state.state
            state_info = log_state.state_info

            # Update 'triggered_by' because it could have changed.
            task_ex.runtime_context['triggered_by'] = log_state.triggered_by

            if state == states.RUNNING:
                continue_task(task_ex)
            elif state == states.ERROR:
                complete_task(task_ex, state, state_info)
            elif state == states.WAITING:
                LOG.info(
                    "Task execution is still in WAITING state"
                    " [task_ex_id=%s, task_name=%s]",
                    task_ex_id,
                    task_ex.name
                )
            else:
                # Must never get here.
                raise RuntimeError(
                    'Unexpected logical task state [task_ex_id=%s, '
                    'task_name=%s, state=%s]' %
                    (task_ex_id, task_ex.name, state)
                )


def _schedule_refresh_task_state(task_ex_id, delay=0):
    """Schedules task preconditions check.

    This method provides transactional decoupling of task preconditions
    check from events that can potentially satisfy those preconditions.

    It's needed in non-locking model in order to avoid 'phantom read'
    phenomena when reading state of multiple tasks to see if a task that
    depends on them can start. Just starting a separate transaction
    without using scheduler is not safe due to concurrency window that
    we'll have in this case (time between transactions) whereas scheduler
    is a special component that is designed to be resistant to failures.

    :param task_ex_id: Task execution ID.
    :param delay: Delay.
    """
    key = _get_refresh_state_job_key(task_ex_id)

    scheduler.schedule_call(
        None,
        _REFRESH_TASK_STATE_PATH,
        delay,
        key=key,
        task_ex_id=task_ex_id
    )


def _get_refresh_state_job_key(task_ex_id):
    return 'th_r_t_s-%s' % task_ex_id


@db_utils.retry_on_db_error
@post_tx_queue.run
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


@db_utils.retry_on_db_error
@post_tx_queue.run
def _scheduled_on_action_update(action_ex_id, wf_action):
    with db_api.transaction():
        if wf_action:
            action_ex = db_api.get_workflow_execution(action_ex_id)
        else:
            action_ex = db_api.get_action_execution(action_ex_id)

        _on_action_update(action_ex)


def schedule_on_action_update(action_ex, delay=0):
    """Schedules task update check.

    This method provides transactional decoupling of action update from
    task update check. It's needed in non-locking model in order to
    avoid 'phantom read' phenomena when reading state of multiple actions
    to see if a task is updated. Just starting a separate transaction
    without using scheduler is not safe due to concurrency window that we'll
    have in this case (time between transactions) whereas scheduler is a
    special component that is designed to be resistant to failures.

    :param action_ex: Action execution.
    :param delay: Minimum amount of time before task update check
        should be made.
    """

    # Optimization to avoid opening a new transaction if it's not needed.
    if not action_ex.task_execution.spec.get('with-items'):
        _on_action_update(action_ex)

        return

    key = 'th_on_a_u-%s' % action_ex.task_execution_id

    scheduler.schedule_call(
        None,
        _SCHEDULED_ON_ACTION_UPDATE_PATH,
        delay,
        key=key,
        action_ex_id=action_ex.id,
        wf_action=isinstance(action_ex, models.WorkflowExecution)
    )
