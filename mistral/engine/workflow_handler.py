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


_CHECK_AND_COMPLETE_PATH = (
    'mistral.engine.workflow_handler._check_and_complete'
)


@profiler.trace('workflow-handler-start-workflow')
def start_workflow(wf_identifier, wf_input, desc, params):
    wf = workflows.Workflow(
        db_api.get_workflow_definition(wf_identifier)
    )

    wf.start(wf_input, desc=desc, params=params)

    _schedule_check_and_complete(wf.wf_ex)

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


@profiler.trace('workflow-handler-check-and-complete')
def _check_and_complete(wf_ex_id):
    # Note: This method can only be called via scheduler.
    with db_api.transaction():
        wf_ex = db_api.load_workflow_execution(wf_ex_id)

        if not wf_ex or states.is_completed(wf_ex.state):
            return

        wf = workflows.Workflow(
            db_api.get_workflow_definition(wf_ex.workflow_id),
            wf_ex=wf_ex
        )

        try:
            incomplete_tasks_count = wf.check_and_complete()
        except exc.MistralException as e:
            msg = (
                "Failed to check and complete [wf_ex=%s]:"
                " %s\n%s" % (wf_ex, e, tb.format_exc())
            )

            LOG.error(msg)

            fail_workflow(wf.wf_ex, msg)

            return

        if not states.is_completed(wf_ex.state):
            # Let's assume that a task takes 0.01 sec in average to complete
            # and based on this assumption calculate a time of the next check.
            # The estimation is very rough but this delay will be decreasing
            # as tasks will be completing which will give a decent
            # approximation.
            # For example, if a workflow has 100 incomplete tasks then the
            # next check call will happen in 10 seconds. For 500 tasks it will
            # be 50 seconds. The larger the workflow is, the more beneficial
            # this mechanism will be.
            delay = int(incomplete_tasks_count * 0.01)

            _schedule_check_and_complete(wf_ex, delay)


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

    _schedule_check_and_complete(wf_ex)

    if wf_ex.task_execution_id:
        _schedule_check_and_complete(wf_ex.task_execution.workflow_execution)


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


def _get_completion_check_key(wf_ex):
    return 'wfh_on_c_a_c-%s' % wf_ex.id


@profiler.trace('workflow-handler-schedule-check-and-complete')
def _schedule_check_and_complete(wf_ex, delay=0):
    """Schedules workflow completion check.

    This method provides transactional decoupling of task completion from
    workflow completion check. It's needed in non-locking model in order to
    avoid 'phantom read' phenomena when reading state of multiple tasks
    to see if a workflow is completed. Just starting a separate transaction
    without using scheduler is not safe due to concurrency window that we'll
    have in this case (time between transactions) whereas scheduler is a
    special component that is designed to be resistant to failures.

    :param wf_ex: Workflow execution.
    :param delay: Minimum amount of time before task completion check
        should be made.
    """
    key = _get_completion_check_key(wf_ex)

    scheduler.schedule_call(
        None,
        _CHECK_AND_COMPLETE_PATH,
        delay,
        key=key,
        wf_ex_id=wf_ex.id
    )
