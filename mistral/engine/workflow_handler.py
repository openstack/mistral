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

from mistral.db.v2 import api as db_api
from mistral.db.v2.sqlalchemy import models as db_models
from mistral.engine import rpc
from mistral.engine import task_handler
from mistral import exceptions as exc
from mistral.services import scheduler
from mistral.utils import wf_trace
from mistral.workbook import parser as spec_parser
from mistral.workflow import data_flow
from mistral.workflow import states
from mistral.workflow import utils as wf_utils


def succeed_workflow(wf_ex, final_context, state_info=None):
    wf_spec = spec_parser.get_workflow_spec(wf_ex.spec)

    # Fail workflow if output is not successfully evaluated.
    try:
        wf_ex.output = data_flow.evaluate_workflow_output(
            wf_spec,
            final_context
        )
    except Exception as e:
        return fail_workflow(wf_ex, e.message)

    # Set workflow execution to success until after output is evaluated.
    set_execution_state(wf_ex, states.SUCCESS, state_info)

    if wf_ex.task_execution_id:
        _schedule_send_result_to_parent_workflow(wf_ex)

    return wf_ex


def fail_workflow(wf_ex, state_info):
    if states.is_paused_or_completed(wf_ex.state):
        return wf_ex

    set_execution_state(wf_ex, states.ERROR, state_info)

    if wf_ex.task_execution_id:
        _schedule_send_result_to_parent_workflow(wf_ex)

    return wf_ex


def _schedule_send_result_to_parent_workflow(wf_ex):
    scheduler.schedule_call(
        None,
        'mistral.engine.workflow_handler.send_result_to_parent_workflow',
        0,
        wf_ex_id=wf_ex.id
    )


def send_result_to_parent_workflow(wf_ex_id):
    wf_ex = db_api.get_workflow_execution(wf_ex_id)

    if wf_ex.state == states.SUCCESS:
        rpc.get_engine_client().on_action_complete(
            wf_ex.id,
            wf_utils.Result(data=wf_ex.output)
        )
    elif wf_ex.state == states.ERROR:
        err_msg = (
            wf_ex.state_info or
            'Failed subworkflow [execution_id=%s]' % wf_ex.id
        )

        rpc.get_engine_client().on_action_complete(
            wf_ex.id,
            wf_utils.Result(error=err_msg)
        )


def set_execution_state(wf_ex, state, state_info=None, set_upstream=False):
    cur_state = wf_ex.state

    if states.is_valid_transition(cur_state, state):
        wf_ex.state = state
        wf_ex.state_info = state_info

        wf_trace.info(
            wf_ex,
            "Execution of workflow '%s' [%s -> %s]"
            % (wf_ex.workflow_name, cur_state, state)
        )
    else:
        msg = ("Can't change workflow execution state from %s to %s. "
               "[workflow=%s, execution_id=%s]" %
               (cur_state, state, wf_ex.name, wf_ex.id))
        raise exc.WorkflowException(msg)

    # Workflow result should be accepted by parent workflows (if any)
    # only if it completed successfully.
    wf_ex.accepted = wf_ex.state == states.SUCCESS

    # If specified, then recursively set the state of the parent workflow
    # executions to the same state. Only changing state to RUNNING is
    # supported.
    if set_upstream and state == states.RUNNING and wf_ex.task_execution_id:
        task_ex = db_api.get_task_execution(wf_ex.task_execution_id)

        parent_wf_ex = lock_workflow_execution(task_ex.workflow_execution_id)

        set_execution_state(
            parent_wf_ex,
            state,
            state_info=state_info,
            set_upstream=set_upstream
        )

        task_handler.set_task_state(
            task_ex,
            state,
            state_info=None,
            processed=False
        )


def lock_workflow_execution(wf_ex_id):
    # Locks a workflow execution using the db_api.acquire_lock function.
    # The method expires all session objects and returns the up-to-date
    # workflow execution from the DB.
    return db_api.acquire_lock(db_models.WorkflowExecution, wf_ex_id)
