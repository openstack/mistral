# Copyright 2013 - Mirantis, Inc.
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

from oslo_log import log as logging

from mistral import coordination
from mistral.db.v2 import api as db_api
from mistral.db.v2.sqlalchemy import models as db_models
from mistral.engine import action_handler
from mistral.engine import base
from mistral.engine import dispatcher
from mistral.engine import workflow_handler as wf_handler
from mistral.services import executions as wf_ex_service
from mistral.services import workflows as wf_service
from mistral import utils as u
from mistral.workflow import base as wf_base
from mistral.workflow import commands
from mistral.workflow import states

LOG = logging.getLogger(__name__)


# Submodules of mistral.engine will throw NoSuchOptError if configuration
# options required at top level of this  __init__.py are not imported before
# the submodules are referenced.


class DefaultEngine(base.Engine, coordination.Service):
    def __init__(self, engine_client):
        self._engine_client = engine_client

        coordination.Service.__init__(self, 'engine_group')

    @u.log_exec(LOG)
    def start_workflow(self, wf_identifier, wf_input, description='',
                       **params):
        with db_api.transaction():
            # TODO(rakhmerov): It needs to be hidden in workflow_handler and
            # Workflow abstraction.
            # The new workflow execution will be in an IDLE
            # state on initial record creation.
            wf_ex, wf_spec = wf_ex_service.create_workflow_execution(
                wf_identifier,
                wf_input,
                description,
                params
            )
            wf_handler.set_workflow_state(wf_ex, states.RUNNING)

            wf_ctrl = wf_base.get_controller(wf_ex, wf_spec)

            cmds = wf_ctrl.continue_workflow()

            dispatcher.dispatch_workflow_commands(wf_ex, cmds)

            return wf_ex.get_clone()

    @u.log_exec(LOG)
    def start_action(self, action_name, action_input,
                     description=None, **params):
        with db_api.transaction():
            action = action_handler.build_action_by_name(action_name)

            action.validate_input(action_input)

            save = params.get('save_result')
            target = params.get('target')

            if save or not action.is_sync(action_input):
                action.schedule(action_input, target)

                return action.action_ex.get_clone()

            output = action.run(action_input, target, save=save)

            # Action execution is not created but we need to return similar
            # object to a client anyway.
            return db_models.ActionExecution(
                name=action_name,
                description=description,
                input=action_input,
                output=output
            )

    @u.log_exec(LOG)
    def on_action_complete(self, action_ex_id, result):
        with db_api.transaction():
            action_ex = db_api.get_action_execution(action_ex_id)

            task_ex = action_ex.task_execution

            if task_ex:
                wf_handler.lock_workflow_execution(
                    task_ex.workflow_execution_id
                )

            action_handler.on_action_complete(action_ex, result)

            return action_ex.get_clone()

    @u.log_exec(LOG)
    def pause_workflow(self, wf_ex_id):
        with db_api.transaction():
            wf_ex = wf_handler.lock_workflow_execution(wf_ex_id)

            wf_handler.set_workflow_state(wf_ex, states.PAUSED)

        return wf_ex

    @staticmethod
    def _continue_workflow(wf_ex, task_ex=None, reset=True, env=None):
        wf_ex = wf_service.update_workflow_execution_env(wf_ex, env)

        wf_handler.set_workflow_state(
            wf_ex,
            states.RUNNING,
            set_upstream=True
        )

        wf_ctrl = wf_base.get_controller(wf_ex)

        # TODO(rakhmerov): Add error handling.
        # Calculate commands to process next.
        cmds = wf_ctrl.continue_workflow(task_ex=task_ex, reset=reset, env=env)

        # When resuming a workflow we need to ignore all 'pause'
        # commands because workflow controller takes tasks that
        # completed within the period when the workflow was paused.
        # TODO(rakhmerov): This all should be in workflow handler, it's too
        # specific for engine level.
        cmds = list(
            filter(
                lambda c: not isinstance(c, commands.PauseWorkflow),
                cmds
            )
        )

        # Since there's no explicit task causing the operation
        # we need to mark all not processed tasks as processed
        # because workflow controller takes only completed tasks
        # with flag 'processed' equal to False.
        for t_ex in wf_ex.task_executions:
            if states.is_completed(t_ex.state) and not t_ex.processed:
                t_ex.processed = True

        dispatcher.dispatch_workflow_commands(wf_ex, cmds)

        if not cmds:
            wf_handler.check_workflow_completion(wf_ex)

        return wf_ex.get_clone()

    @u.log_exec(LOG)
    def rerun_workflow(self, wf_ex_id, task_ex_id, reset=True, env=None):
        # TODO(rakhmerov): Rewrite this functionality with Task abstraction.
        with db_api.transaction():
            wf_ex = wf_handler.lock_workflow_execution(wf_ex_id)

            task_ex = db_api.get_task_execution(task_ex_id)

            if task_ex.workflow_execution.id != wf_ex_id:
                raise ValueError('Workflow execution ID does not match.')

            if wf_ex.state == states.PAUSED:
                return wf_ex.get_clone()

            # TODO(rakhmerov): This should be a call to workflow handler.
            return self._continue_workflow(wf_ex, task_ex, reset, env=env)

    @u.log_exec(LOG)
    def resume_workflow(self, wf_ex_id, env=None):
        # TODO(rakhmerov): Rewrite this functionality with Task abstraction.
        with db_api.transaction():
            wf_ex = wf_handler.lock_workflow_execution(wf_ex_id)

            if (not states.is_paused(wf_ex.state) and
                    not states.is_idle(wf_ex.state)):
                return wf_ex.get_clone()

            return self._continue_workflow(wf_ex, env=env)

    @u.log_exec(LOG)
    def stop_workflow(self, wf_ex_id, state, message=None):
        with db_api.transaction():
            wf_ex = wf_handler.lock_workflow_execution(wf_ex_id)

            return wf_handler.stop_workflow(wf_ex, state, message)

    @u.log_exec(LOG)
    def rollback_workflow(self, wf_ex_id):
        # TODO(rakhmerov): Implement.
        raise NotImplementedError
