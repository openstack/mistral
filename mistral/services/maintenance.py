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
import time

from mistral import context as auth_ctx
from mistral.db.v2 import api as db_api
from mistral.engine import post_tx_queue
from mistral.engine import workflow_handler
from mistral import exceptions
from mistral.scheduler import base as sched_base
from mistral.workflow import states

PAUSING = 'PAUSING'
PAUSED = 'PAUSED'
RUNNING = 'RUNNING'

_VALID_TRANSITIONS = {
    PAUSING: [PAUSED],
    PAUSED: [PAUSED, RUNNING],
    RUNNING: [PAUSED, RUNNING]
}

_ALL_STATES = [
    PAUSING,
    PAUSED,
    RUNNING
]

LOG = logging.getLogger(__name__)

_PAUSE_EXECUTIONS_PATH = 'mistral.services.maintenance._pause_executions'
_RESUME_EXECUTIONS_PATH = 'mistral.services.maintenance._resume_executions'


def is_valid_transition(old_state, new_state):
    return new_state in _VALID_TRANSITIONS.get(old_state, [])


def pause_running_executions():
    execution_ids = [(ex.id, ex.project_id) for ex in
                     db_api.get_workflow_executions(state=states.RUNNING,
                     insecure=True)]

    LOG.info("Number of find workflow executions is %s", len(execution_ids))

    for wf_ex_id, project_id in execution_ids:
        try:
            with db_api.transaction():
                _pause_execution(wf_ex_id, project_id)
        except BaseException as e:
            LOG.error(str(e))

    return True


def _pause_execution(wf_ex_id, project_id):
    auth_ctx.set_ctx(
        auth_ctx.MistralContext(
            user=None,
            auth_token=None,
            project_id=project_id,
            is_admin=True
        )
    )

    current_state = db_api.get_maintenance_status()

    if current_state != PAUSING:
        return False

    wf_ex = db_api.get_workflow_execution(wf_ex_id)

    if states.is_running(wf_ex.state):
        workflow_handler.pause_workflow(wf_ex)
        LOG.info('Execution %s was paused', wf_ex_id)


def await_pause_executions():
    auth_ctx.set_ctx(
        auth_ctx.MistralContext(
            user=None,
            auth_token=None,
            is_admin=True
        )
    )

    while True:
        with db_api.transaction():
            current_state = db_api.get_maintenance_status()

            if current_state != PAUSING:
                return False

            tasks = db_api.get_task_executions(
                state=states.RUNNING, insecure=True
            )

            if not tasks:
                return True

            LOG.info('The following tasks have RUNNING state: %s',
                     [task.id for task in tasks])
            time.sleep(1)


def change_maintenance_mode(new_state):
    if new_state not in _ALL_STATES:
        raise exceptions.MaintenanceException(
            'Not found {} maintenance state. List of states: {}'.format(
                new_state, _ALL_STATES
            )
        )

    if new_state == PAUSING:
        raise exceptions.MaintenanceException(
            'PAUSING is intermediate state. Consider PAUSED, RUNNING as new '
            'state')

    with db_api.transaction():
        current_state = db_api.get_maintenance_status()

        if current_state == new_state:
            LOG.info('State was already changed. Skip')
            return current_state

        sched = sched_base.get_system_scheduler()

        if new_state == PAUSED:
            job = sched_base.SchedulerJob(func_name=_PAUSE_EXECUTIONS_PATH)
            sched.schedule(job)
            db_api.update_maintenance_status(PAUSING)

            return PAUSING
        elif new_state == RUNNING:
            job = sched_base.SchedulerJob(func_name=_RESUME_EXECUTIONS_PATH)
            sched.schedule(job)
            db_api.update_maintenance_status(RUNNING)

            return RUNNING


@post_tx_queue.run
def _pause_executions():
    auth_ctx.set_ctx(
        auth_ctx.MistralContext(
            user=None,
            auth_token=None,
            is_admin=True
        )
    )

    if pause_running_executions() and await_pause_executions():
        with db_api.transaction():
            if db_api.get_maintenance_status() == PAUSING:
                db_api.update_maintenance_status(PAUSED)


@post_tx_queue.run
def _resume_executions():
    auth_ctx.set_ctx(
        auth_ctx.MistralContext(
            user=None,
            auth_token=None,
            is_admin=True
        )
    )

    with db_api.transaction():
        current_state = db_api.get_maintenance_status()

        if current_state != RUNNING:
            return

        paused_executions = db_api.get_workflow_executions(
            state=states.PAUSED, insecure=True
        )

        if not paused_executions:
            return

        for ex in paused_executions:
            _resume_execution(wf_ex_id=ex.id)


def _resume_execution(wf_ex_id):
    wf_ex = db_api.get_workflow_execution(wf_ex_id)

    auth_ctx.set_ctx(
        auth_ctx.MistralContext(
            project_id=wf_ex.project_id
        )
    )

    workflow_handler.resume_workflow(wf_ex)

    LOG.info('The following execution was resumed: %s', [wf_ex.id])
