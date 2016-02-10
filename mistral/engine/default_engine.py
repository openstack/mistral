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

import traceback

from oslo_log import log as logging

from mistral import coordination
from mistral.db.v2 import api as db_api
from mistral.db.v2.sqlalchemy import models as db_models
from mistral.engine import action_handler
from mistral.engine import base
from mistral.engine import task_handler
from mistral.engine import workflow_handler as wf_handler
from mistral.services import action_manager as a_m
from mistral.services import executions as wf_ex_service
from mistral.services import workflows as wf_service
from mistral import utils as u
from mistral.utils import wf_trace
from mistral.workbook import parser as spec_parser
from mistral.workflow import base as wf_base
from mistral.workflow import commands
from mistral.workflow import states
from mistral.workflow import utils as wf_utils

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
        wf_ex_id = None

        try:
            with db_api.transaction():
                # The new workflow execution will be in an IDLE
                # state on initial record creation.
                wf_ex_id = wf_ex_service.create_workflow_execution(
                    wf_identifier,
                    wf_input,
                    description,
                    params
                )

            # Separate workflow execution creation and dispatching command
            # transactions in order to be able to return workflow execution
            # with corresponding error message in state_info when error occurs
            # at dispatching commands.
            with db_api.transaction():
                wf_ex = db_api.get_workflow_execution(wf_ex_id)
                wf_spec = spec_parser.get_workflow_spec(wf_ex.spec)
                wf_handler.set_execution_state(wf_ex, states.RUNNING)

                wf_ctrl = wf_base.WorkflowController.get_controller(
                    wf_ex,
                    wf_spec
                )

                self._dispatch_workflow_commands(
                    wf_ex,
                    wf_ctrl.continue_workflow()
                )

                return wf_ex.get_clone()
        except Exception as e:
            LOG.error(
                "Failed to start workflow '%s' id=%s: %s\n%s",
                wf_identifier, wf_ex_id, e, traceback.format_exc()
            )

            wf_ex = self._fail_workflow(wf_ex_id, e)

            if wf_ex:
                return wf_ex.get_clone()

            raise e

    @u.log_exec(LOG)
    def start_action(self, action_name, action_input,
                     description=None, **params):
        with db_api.transaction():
            action_def = action_handler.resolve_definition(action_name)
            resolved_action_input = action_handler.get_action_input(
                action_name,
                action_input
            )
            action = a_m.get_action_class(action_def.name)(
                **resolved_action_input
            )

            # If we see action is asynchronous, then we enforce 'save_result'.
            if params.get('save_result') or not action.is_sync():
                action_ex = action_handler.create_action_execution(
                    action_def,
                    resolved_action_input,
                    description=description
                )

                action_handler.run_action(
                    action_def,
                    resolved_action_input,
                    action_ex.id,
                    params.get('target')
                )

                return action_ex.get_clone()
            else:
                output = action_handler.run_action(
                    action_def,
                    resolved_action_input,
                    target=params.get('target'),
                    async=False
                )

                return db_models.ActionExecution(
                    name=action_name,
                    description=description,
                    input=action_input,
                    output=output
                )

    def on_task_state_change(self, task_ex_id, state, state_info=None):
        with db_api.transaction():
            task_ex = db_api.get_task_execution(task_ex_id)
            # TODO(rakhmerov): The method is mostly needed for policy and
            # we are supposed to get the same action execution as when the
            # policy worked.

            wf_ex_id = task_ex.workflow_execution_id
            wf_ex = wf_handler.lock_workflow_execution(wf_ex_id)

            wf_trace.info(
                task_ex,
                "Task '%s' [%s -> %s] state_info : %s"
                % (task_ex.name, task_ex.state, state, state_info)
            )

            task_ex.state = state
            task_ex.state_info = state_info

            self._on_task_state_change(task_ex, wf_ex)

    def _on_task_state_change(self, task_ex, wf_ex, task_state=states.SUCCESS):
        task_spec = spec_parser.get_task_spec(task_ex.spec)
        wf_spec = spec_parser.get_workflow_spec(wf_ex.spec)

        # We must be sure that if task is completed,
        # it was also completed in previous transaction.
        if (task_handler.is_task_completed(task_ex, task_spec)
                and states.is_completed(task_state)):
            task_handler.after_task_complete(task_ex, task_spec, wf_spec)

            # Ignore DELAYED state.
            if task_ex.state == states.RUNNING_DELAYED:
                return

            wf_ctrl = wf_base.WorkflowController.get_controller(wf_ex, wf_spec)

            # Calculate commands to process next.
            cmds = wf_ctrl.continue_workflow()

            task_ex.processed = True

            self._dispatch_workflow_commands(wf_ex, cmds)

            self._check_workflow_completion(wf_ex, wf_ctrl)
        elif task_handler.need_to_continue(task_ex, task_spec):
            # Re-run existing task.
            cmds = [commands.RunExistingTask(task_ex, reset=False)]

            self._dispatch_workflow_commands(wf_ex, cmds)

    @staticmethod
    def _check_workflow_completion(wf_ex, wf_ctrl):
        if states.is_paused_or_completed(wf_ex.state):
            return

        # Workflow is not completed if there are any incomplete task
        # executions that are not in WAITING state. If all incomplete
        # tasks are waiting and there are unhandled errors, then these
        # tasks will not reach completion. In this case, mark the
        # workflow complete.
        incomplete_tasks = wf_utils.find_incomplete_task_executions(wf_ex)

        if any(not states.is_waiting(t.state) for t in incomplete_tasks):
            return

        if wf_ctrl.all_errors_handled():
            wf_handler.succeed_workflow(
                wf_ex,
                wf_ctrl.evaluate_workflow_final_context()
            )
        else:
            state_info = wf_utils.construct_fail_info_message(wf_ctrl, wf_ex)

            wf_handler.fail_workflow(wf_ex, state_info)

    @u.log_exec(LOG)
    def on_action_complete(self, action_ex_id, result):
        wf_ex_id = None

        try:
            with db_api.transaction():
                action_ex = db_api.get_action_execution(action_ex_id)

                # In case of single action execution there is no
                # assigned task execution.
                if not action_ex.task_execution:
                    return action_handler.store_action_result(
                        action_ex,
                        result
                    ).get_clone()

                wf_ex_id = action_ex.task_execution.workflow_execution_id
                wf_ex = wf_handler.lock_workflow_execution(wf_ex_id)

                task_ex = task_handler.on_action_complete(action_ex, result)

                # If workflow is on pause or completed then there's no
                # need to continue workflow.
                if states.is_paused_or_completed(wf_ex.state):
                    return action_ex.get_clone()

            prev_task_state = task_ex.state

            # Separate the task transition in a separate transaction. The task
            # has already completed for better or worst. The task state should
            # not be affected by errors during transition on conditions such as
            # on-success and on-error.
            with db_api.transaction():
                wf_ex = wf_handler.lock_workflow_execution(wf_ex_id)
                action_ex = db_api.get_action_execution(action_ex_id)
                task_ex = action_ex.task_execution

                self._on_task_state_change(
                    task_ex,
                    wf_ex,
                    task_state=prev_task_state
                )

                return action_ex.get_clone()
        except Exception as e:
            # TODO(dzimine): try to find out which command caused failure.
            # TODO(rakhmerov): Need to refactor logging in a more elegant way.
            LOG.error(
                "Failed to handle action execution result [id=%s]: %s\n%s",
                action_ex_id, e, traceback.format_exc()
            )

            # If an exception was thrown after we got the wf_ex_id
            if wf_ex_id:
                self._fail_workflow(wf_ex_id, e)

            raise e

    @u.log_exec(LOG)
    def pause_workflow(self, execution_id):
        with db_api.transaction():
            wf_ex = wf_handler.lock_workflow_execution(execution_id)

            wf_handler.set_execution_state(wf_ex, states.PAUSED)

        return wf_ex

    def _continue_workflow(self, wf_ex, task_ex=None, reset=True, env=None):
        wf_ex = wf_service.update_workflow_execution_env(wf_ex, env)

        wf_handler.set_execution_state(
            wf_ex,
            states.RUNNING,
            set_upstream=True
        )

        wf_ctrl = wf_base.WorkflowController.get_controller(wf_ex)

        # Calculate commands to process next.
        cmds = wf_ctrl.continue_workflow(task_ex=task_ex, reset=reset, env=env)

        # When resuming a workflow we need to ignore all 'pause'
        # commands because workflow controller takes tasks that
        # completed within the period when the workflow was pause.
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

        self._dispatch_workflow_commands(wf_ex, cmds)

        if not cmds:
            if not wf_utils.find_incomplete_task_executions(wf_ex):
                wf_handler.succeed_workflow(
                    wf_ex,
                    wf_ctrl.evaluate_workflow_final_context()
                )

        return wf_ex.get_clone()

    @u.log_exec(LOG)
    def rerun_workflow(self, wf_ex_id, task_ex_id, reset=True, env=None):
        try:
            with db_api.transaction():
                wf_ex = wf_handler.lock_workflow_execution(wf_ex_id)

                task_ex = db_api.get_task_execution(task_ex_id)

                if task_ex.workflow_execution.id != wf_ex_id:
                    raise ValueError('Workflow execution ID does not match.')

                if wf_ex.state == states.PAUSED:
                    return wf_ex.get_clone()

                return self._continue_workflow(wf_ex, task_ex, reset, env=env)
        except Exception as e:
            LOG.error(
                "Failed to rerun execution id=%s at task=%s: %s\n%s",
                wf_ex_id, task_ex_id, e, traceback.format_exc()
            )
            self._fail_workflow(wf_ex_id, e)
            raise e

    @u.log_exec(LOG)
    def resume_workflow(self, wf_ex_id, env=None):
        try:
            with db_api.transaction():
                wf_ex = wf_handler.lock_workflow_execution(wf_ex_id)

                if (not states.is_paused(wf_ex.state) and
                        not states.is_idle(wf_ex.state)):
                    return wf_ex.get_clone()

                return self._continue_workflow(wf_ex, env=env)
        except Exception as e:
            LOG.error(
                "Failed to resume execution id=%s: %s\n%s",
                wf_ex_id, e, traceback.format_exc()
            )
            self._fail_workflow(wf_ex_id, e)
            raise e

    @u.log_exec(LOG)
    def stop_workflow(self, execution_id, state, message=None):
        with db_api.transaction():
            wf_ex = wf_handler.lock_workflow_execution(execution_id)

            return self._stop_workflow(wf_ex, state, message)

    @staticmethod
    def _stop_workflow(wf_ex, state, message=None):
        if state == states.SUCCESS:
            wf_ctrl = wf_base.WorkflowController.get_controller(wf_ex)

            final_context = {}
            try:
                final_context = wf_ctrl.evaluate_workflow_final_context()
            except Exception as e:
                LOG.warning(
                    "Failed to get final context for %s: %s" % (wf_ex, e)
                )
            return wf_handler.succeed_workflow(
                wf_ex,
                final_context,
                message
            )
        elif state == states.ERROR:
            return wf_handler.fail_workflow(wf_ex, message)

        return wf_ex

    @u.log_exec(LOG)
    def rollback_workflow(self, execution_id):
        # TODO(rakhmerov): Implement.
        raise NotImplementedError

    def _dispatch_workflow_commands(self, wf_ex, wf_cmds):
        if not wf_cmds:
            return

        for cmd in wf_cmds:
            if isinstance(cmd, commands.RunTask) and cmd.is_waiting():
                task_handler.defer_task(cmd)
            elif isinstance(cmd, commands.RunTask):
                task_handler.run_new_task(cmd)
            elif isinstance(cmd, commands.RunExistingTask):
                task_handler.run_existing_task(
                    cmd.task_ex.id,
                    reset=cmd.reset
                )
            elif isinstance(cmd, commands.SetWorkflowState):
                if states.is_completed(cmd.new_state):
                    self._stop_workflow(cmd.wf_ex, cmd.new_state, cmd.msg)
                else:
                    wf_handler.set_execution_state(wf_ex, cmd.new_state)
            elif isinstance(cmd, commands.Noop):
                # Do nothing.
                pass
            else:
                raise RuntimeError('Unsupported workflow command: %s' % cmd)

            if wf_ex.state != states.RUNNING:
                break

    @staticmethod
    def _fail_workflow(wf_ex_id, err, action_ex_id=None):
        """Private helper to fail workflow on exceptions."""
        err_msg = str(err)

        with db_api.transaction():
            wf_ex = db_api.load_workflow_execution(wf_ex_id)

            if wf_ex is None:
                LOG.error(
                    "Cant fail workflow execution with id='%s': not found.",
                    wf_ex_id
                )
                return

            wf_handler.set_execution_state(wf_ex, states.ERROR, err_msg)

            if action_ex_id:
                # Note(dzimine): Don't call self.engine_client:
                # 1) to avoid computing and triggering next tasks
                # 2) to avoid a loop in case of error in transport
                action_ex = db_api.get_action_execution(action_ex_id)

                task_handler.on_action_complete(
                    action_ex,
                    wf_utils.Result(error=err_msg)
                )

            return wf_ex
