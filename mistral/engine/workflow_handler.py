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
from mistral.engine import workflows
from mistral import exceptions as exc
from mistral.services import scheduler
from mistral.workflow import states


LOG = logging.getLogger(__name__)


_ON_TASK_COMPLETE_PATH = 'mistral.engine.workflow_handler._on_task_complete'


@profiler.trace('workflow-handler-start-workflow')
def start_workflow(wf_identifier, wf_input, desc, params):
    wf = workflows.Workflow(
        db_api.get_workflow_definition(wf_identifier)
    )

    wf.start(wf_input, desc=desc, params=params)

    return wf.wf_ex


def stop_workflow(wf_ex, state, msg=None):
    wf = workflows.Workflow(
        db_api.get_workflow_definition(wf_ex.workflow_id),
        wf_ex=wf_ex
    )

    # In this case we should not try to handle possible errors. Instead,
    # we need to let them pop up since the typical way of failing objects
    # doesn't work here. Failing a workflow is the same as stopping it
    # with ERROR state.
    wf.stop(state, msg)

    # Cancels subworkflows.
    if state == states.CANCELLED:
        for task_ex in wf_ex.task_executions:
            sub_wf_exs = db_api.get_workflow_executions(
                task_execution_id=task_ex.id
            )

            for sub_wf_ex in sub_wf_exs:
                if not states.is_completed(sub_wf_ex.state):
                    stop_workflow(sub_wf_ex, state, msg=msg)


def fail_workflow(wf_ex, msg=None):
    stop_workflow(wf_ex, states.ERROR, msg)


def cancel_workflow(wf_ex, msg=None):
    stop_workflow(wf_ex, states.CANCELLED, msg)


@profiler.trace('workflow-handler-on-task-complete')
def _on_task_complete(task_ex_id):
    # Note: This method can only be called via scheduler.
    with db_api.transaction():
        task_ex = db_api.get_task_execution(task_ex_id)

        wf_ex = task_ex.workflow_execution

        wf = workflows.Workflow(
            db_api.get_workflow_definition(wf_ex.workflow_id),
            wf_ex=wf_ex
        )

        try:
            wf.on_task_complete(task_ex)
        except exc.MistralException as e:
            msg = (
                "Failed to handle task completion [wf_ex=%s, task_ex=%s]:"
                " %s\n%s" % (wf_ex, task_ex, e, tb.format_exc())
            )

            LOG.error(msg)

            fail_workflow(wf.wf_ex, msg)

            return

        if not states.is_completed(wf_ex.state):
            # TODO(rakhmerov): Moving forward we can implement some more fancy
            # algorithm for increasing delay for rescheduling so that we don't
            # put too serious load onto scheduler.
            delay = 1
            schedule_on_task_complete(task_ex, delay)


def pause_workflow(wf_ex, msg=None):
    wf = workflows.Workflow(
        db_api.get_workflow_definition(wf_ex.workflow_id),
        wf_ex=wf_ex
    )

    wf.set_state(states.PAUSED, msg)


def rerun_workflow(wf_ex, task_ex, reset=True, env=None):
    if wf_ex.state == states.PAUSED:
        return wf_ex.get_clone()

    wf = workflows.Workflow(
        db_api.get_workflow_definition(wf_ex.workflow_id),
        wf_ex=wf_ex
    )

    wf.rerun(task_ex, reset=reset, env=env)


def resume_workflow(wf_ex, env=None):
    if not states.is_paused_or_idle(wf_ex.state):
        return wf_ex.get_clone()

    wf = workflows.Workflow(
        db_api.get_workflow_definition(wf_ex.workflow_id),
        wf_ex=wf_ex
    )

    wf.resume(env=env)


@profiler.trace('workflow-handler-set-state')
def set_workflow_state(wf_ex, state, msg=None):
    if states.is_completed(state):
        stop_workflow(wf_ex, state, msg)
    elif states.is_paused(state):
        pause_workflow(wf_ex, msg)
    else:
        raise exc.MistralError(
            'Invalid workflow state [wf_ex=%s, state=%s]' % (wf_ex, state)
        )


@profiler.trace('workflow-handler-schedule-on-task-complete')
def schedule_on_task_complete(task_ex, delay=0):
    """Schedules task completion check.

    This method provides transactional decoupling of task completion from
    workflow completion check. It's needed in non-locking model in order to
    avoid 'phantom read' phenomena when reading state of multiple tasks
    to see if a workflow is completed. Just starting a separate transaction
    without using scheduler is not safe due to concurrency window that we'll
    have in this case (time between transactions) whereas scheduler is a
    special component that is designed to be resistant to failures.

    :param task_ex: Task execution.
    :param delay: Minimum amount of time before task completion check
        should be made.
    """
    key = 'wfh_on_t_c-%s' % task_ex.workflow_execution_id

    scheduler.schedule_call(
        None,
        _ON_TASK_COMPLETE_PATH,
        delay,
        unique_key=key,
        task_ex_id=task_ex.id
    )
