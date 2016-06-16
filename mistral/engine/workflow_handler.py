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
from mistral.db.v2.sqlalchemy import models as db_models
from mistral.engine import workflows
from mistral import exceptions as exc
from mistral.workflow import states


LOG = logging.getLogger(__name__)


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


def fail_workflow(wf_ex, msg=None):
    stop_workflow(wf_ex, states.ERROR, msg)


@profiler.trace('workflow-handler-on-task-complete')
def on_task_complete(task_ex):
    wf_ex = task_ex.workflow_execution

    wf = workflows.Workflow(
        db_api.get_workflow_definition(wf_ex.workflow_id),
        wf_ex=wf_ex
    )

    try:
        wf.on_task_complete(task_ex)
    except exc.MistralException as e:
        msg = (
            "Failed to handle task completion [wf_ex=%s, task_ex=%s]: %s\n%s"
            % (wf_ex, task_ex, e, tb.format_exc())
        )

        LOG.error(msg)

        fail_workflow(wf.wf_ex, msg)


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


@profiler.trace('workflow-handler-lock-execution')
def lock_workflow_execution(wf_ex_id):
    # Locks a workflow execution using the db_api.acquire_lock function.
    # The method expires all session objects and returns the up-to-date
    # workflow execution from the DB.
    return db_api.acquire_lock(db_models.WorkflowExecution, wf_ex_id)
