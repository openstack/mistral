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

from oslo_config import cfg
from oslo_log import log as logging

from mistral.db.v2 import api as db_api
from mistral.db.v2.sqlalchemy import models as db_models
from mistral.engine import rpc
from mistral import exceptions as exc
from mistral.services import scheduler
from mistral import utils
from mistral.utils import wf_trace
from mistral.workbook import parser as spec_parser
from mistral.workflow import base as wf_base
from mistral.workflow import data_flow
from mistral.workflow import states
from mistral.workflow import utils as wf_utils


LOG = logging.getLogger(__name__)


def on_task_complete(task_ex):
    wf_ex = task_ex.workflow_execution

    check_workflow_completion(wf_ex)


def check_workflow_completion(wf_ex):
    if states.is_paused_or_completed(wf_ex.state):
        return

    # Workflow is not completed if there are any incomplete task
    # executions that are not in WAITING state. If all incomplete
    # tasks are waiting and there are no unhandled errors, then these
    # tasks will not reach completion. In this case, mark the
    # workflow complete.
    incomplete_tasks = wf_utils.find_incomplete_task_executions(wf_ex)

    if any(not states.is_waiting(t.state) for t in incomplete_tasks):
        return

    wf_spec = spec_parser.get_workflow_spec(wf_ex.spec)

    wf_ctrl = wf_base.get_controller(wf_ex, wf_spec)

    if wf_ctrl.all_errors_handled():
        succeed_workflow(
            wf_ex,
            wf_ctrl.evaluate_workflow_final_context(),
            wf_spec
        )
    else:
        state_info = wf_utils.construct_fail_info_message(wf_ctrl, wf_ex)

        fail_workflow(wf_ex, state_info)


def stop_workflow(wf_ex, state, message=None):
    if state == states.SUCCESS:
        wf_ctrl = wf_base.get_controller(wf_ex)

        final_context = {}

        try:
            final_context = wf_ctrl.evaluate_workflow_final_context()
        except Exception as e:
            LOG.warning(
                'Failed to get final context for %s: %s' % (wf_ex, e)
            )

        wf_spec = spec_parser.get_workflow_spec(wf_ex.spec)

        return succeed_workflow(
            wf_ex,
            final_context,
            wf_spec,
            message
        )
    elif state == states.ERROR:
        return fail_workflow(wf_ex, message)

    return wf_ex


def succeed_workflow(wf_ex, final_context, wf_spec, state_info=None):
    # Fail workflow if output is not successfully evaluated.
    try:
        wf_ex.output = data_flow.evaluate_workflow_output(
            wf_spec,
            final_context
        )
    except Exception as e:
        return fail_workflow(wf_ex, e.message)

    # Set workflow execution to success until after output is evaluated.
    set_workflow_state(wf_ex, states.SUCCESS, state_info)

    if wf_ex.task_execution_id:
        _schedule_send_result_to_parent_workflow(wf_ex)

    return wf_ex


def fail_workflow(wf_ex, state_info):
    if states.is_paused_or_completed(wf_ex.state):
        return wf_ex

    set_workflow_state(wf_ex, states.ERROR, state_info)

    # When we set an ERROR state we should safely set output value getting
    # w/o exceptions due to field size limitations.
    state_info = utils.cut_by_kb(
        state_info,
        cfg.CONF.engine.execution_field_size_limit_kb
    )

    wf_ex.output = {'result': state_info}

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


# TODO(rakhmerov): Should not be public, should be encapsulated inside Workflow
# abstraction.
def set_workflow_state(wf_ex, state, state_info=None, set_upstream=False):
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
    # only if it completed successfully or failed.
    wf_ex.accepted = wf_ex.state in (states.SUCCESS, states.ERROR)

    # If specified, then recursively set the state of the parent workflow
    # executions to the same state. Only changing state to RUNNING is
    # supported.
    # TODO(rakhmerov): I don't like this hardcoded special case. It's
    # used only to continue the workflow (rerun) but at the first glance
    # seems like a generic behavior. Need to handle it differently.
    if set_upstream and state == states.RUNNING and wf_ex.task_execution_id:
        task_ex = db_api.get_task_execution(wf_ex.task_execution_id)

        parent_wf_ex = lock_workflow_execution(task_ex.workflow_execution_id)

        set_workflow_state(
            parent_wf_ex,
            state,
            state_info=state_info,
            set_upstream=set_upstream
        )

        # TODO(rakhmerov): How do we need to set task state properly?
        # It doesn't seem right to intervene into the parent workflow
        # internals. We just need to communicate changes back to parent
        # worklfow and it should do what's needed itself.
        task_ex.state = state
        task_ex.state_info = None
        task_ex.processed = False


def lock_workflow_execution(wf_ex_id):
    # Locks a workflow execution using the db_api.acquire_lock function.
    # The method expires all session objects and returns the up-to-date
    # workflow execution from the DB.
    return db_api.acquire_lock(db_models.WorkflowExecution, wf_ex_id)
