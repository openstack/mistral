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

import copy
import traceback

from mistral.db.v2 import api as db_api
from mistral.engine1 import base
from mistral.engine1 import task_handler
from mistral.engine1 import utils
from mistral.engine1 import workflow_handler as wf_handler
from mistral.openstack.common import log as logging
from mistral import utils as u
from mistral.utils import wf_trace
from mistral.workbook import parser as spec_parser
from mistral.workflow import commands
from mistral.workflow import data_flow
from mistral.workflow import states
from mistral.workflow import utils as wf_utils
from mistral.workflow import workflow_controller_factory as wfc_factory


LOG = logging.getLogger(__name__)

# Submodules of mistral.engine will throw NoSuchOptError if configuration
# options required at top level of this  __init__.py are not imported before
# the submodules are referenced.


class DefaultEngine(base.Engine):
    def __init__(self, engine_client):
        self._engine_client = engine_client

    @u.log_exec(LOG)
    def start_workflow(self, wf_name, wf_input, **params):
        wf_exec_id = None

        try:
            params = self._canonize_workflow_params(params)

            with db_api.transaction():
                wf_def = db_api.get_workflow_definition(wf_name)
                wf_spec = spec_parser.get_workflow_spec(wf_def.spec)

                utils.validate_workflow_input(wf_def, wf_spec, wf_input)

                wf_ex = self._create_workflow_execution(
                    wf_def,
                    wf_spec,
                    wf_input,
                    params
                )
                wf_exec_id = wf_ex.id

                wf_trace.info(wf_ex, "Starting workflow: '%s'" % wf_name)

                wf_ctrl = wfc_factory.create_workflow_controller(
                    wf_ex,
                    wf_spec
                )

                self._dispatch_workflow_commands(
                    wf_ex,
                    wf_ctrl.continue_workflow()
                )

                return wf_ex
        except Exception as e:
            LOG.error(
                "Failed to start workflow '%s' id=%s: %s\n%s",
                wf_name, wf_exec_id, e, traceback.format_exc()
            )
            self._fail_workflow(wf_exec_id, e)
            raise e

    @u.log_exec(LOG)
    def on_action_complete(self, action_ex_id, result):
        wf_exec_id = None

        try:
            with db_api.transaction():
                action_ex = db_api.get_action_execution(action_ex_id)

                wf_ex = action_ex.task_execution.workflow_execution
                wf_exec_id = wf_ex.id

                task_ex = task_handler.on_action_complete(action_ex, result)

                # If workflow is on pause or completed then there's no
                # need to continue workflow.
                if states.is_paused_or_completed(wf_ex.state):
                    return action_ex

                if states.is_completed(task_ex.state):
                    wf_ctrl = wfc_factory.create_workflow_controller(wf_ex)

                    # Calculate commands to process next.
                    cmds = wf_ctrl.continue_workflow()

                    task_ex.processed = True

                    if not cmds:
                        # TODO(rakhmerov): Think of a better way to determine
                        # workflow state than analyzing last task state.
                        if task_ex.state == states.SUCCESS:
                            if not wf_utils.find_running_tasks(wf_ex):
                                wf_handler.succeed_workflow(
                                    wf_ex,
                                    wf_ctrl.evaluate_workflow_final_context()
                                )
                        else:
                            wf_handler.fail_workflow(wf_ex, task_ex, action_ex)
                    else:
                        self._dispatch_workflow_commands(wf_ex, cmds)

                return action_ex
        except Exception as e:
            # TODO(dzimine): try to find out which command caused failure.
            # TODO(rakhmerov): Need to refactor logging in a more elegant way.
            LOG.error(
                "Failed to handle action execution result [id=%s]: %s\n%s",
                action_ex_id, e, traceback.format_exc()
            )
            self._fail_workflow(wf_exec_id, e)
            raise e

    @u.log_exec(LOG)
    def pause_workflow(self, execution_id):
        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(execution_id)

            wf_handler.set_execution_state(wf_ex, states.PAUSED)

        return wf_ex

    @u.log_exec(LOG)
    def resume_workflow(self, execution_id):
        try:
            with db_api.transaction():
                wf_ex = db_api.get_workflow_execution(execution_id)

                if wf_ex.state != states.PAUSED:
                    return

                wf_handler.set_execution_state(wf_ex, states.RUNNING)

                wf_ctrl = wfc_factory.create_workflow_controller(wf_ex)

                # Calculate commands to process next.
                cmds = wf_ctrl.continue_workflow()

                # When resuming a workflow we need to ignore all 'pause'
                # commands because workflow controller takes tasks that
                # completed within the period when the workflow was pause.
                cmds = filter(
                    lambda c: not isinstance(c, commands.PauseWorkflow),
                    cmds
                )

                # Since there's no explicit task causing the operation
                # we need to mark all not processed tasks as processed
                # because workflow controller takes only completed tasks
                # with flag 'processed' equal to False.
                for t_ex in wf_ex.task_executions:
                    if states.is_completed(t_ex.state) and not t_ex.processed:
                        t_ex.processed = True

                if not cmds:
                    if not wf_utils.find_running_tasks(wf_ex):
                        wf_handler.succeed_workflow(
                            wf_ex,
                            wf_ctrl.evaluate_workflow_final_context()
                        )
                else:
                    self._dispatch_workflow_commands(wf_ex, cmds)

                return wf_ex
        except Exception as e:
            LOG.error(
                "Failed to resume execution id=%s: %s\n%s",
                execution_id, e, traceback.format_exc()
            )
            self._fail_workflow(execution_id, e)
            raise e

    @u.log_exec(LOG)
    def stop_workflow(self, execution_id, state, message=None):
        with db_api.transaction():
            wf_ex = db_api.get_execution(execution_id)

            wf_handler.set_execution_state(wf_ex, state, message)

            return wf_ex

    @u.log_exec(LOG)
    def rollback_workflow(self, execution_id):
        # TODO(rakhmerov): Implement.
        raise NotImplementedError

    @staticmethod
    def _dispatch_workflow_commands(wf_ex, wf_cmds):
        if not wf_cmds:
            return

        for cmd in wf_cmds:
            if isinstance(cmd, commands.RunTask):
                task_handler.run_task(cmd)
            elif isinstance(cmd, commands.SetWorkflowState):
                # TODO(rakhmerov): Special commands should be persisted too.
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
        with db_api.transaction():
            err_msg = str(err)

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
                    wf_ex,
                    action_ex,
                    wf_utils.Result(error=err_msg)
                )

    @staticmethod
    def _canonize_workflow_params(params):
        # Resolve environment parameter.
        env = params.get('env', {})

        if not isinstance(env, dict) and not isinstance(env, basestring):
            raise ValueError(
                'Unexpected type for environment [environment=%s]' % str(env)
            )

        if isinstance(env, basestring):
            env_db = db_api.get_environment(env)
            env = env_db.variables
            params['env'] = env

        return params

    @staticmethod
    def _create_workflow_execution(wf_def, wf_spec, wf_input, params):
        wf_ex = db_api.create_workflow_execution({
            'name': wf_def.name,
            'workflow_name': wf_def.name,
            'spec': wf_spec.to_dict(),
            'params': params or {},
            'state': states.RUNNING,
            'input': wf_input or {},
            'output': {},
            'context': copy.copy(wf_input) or {},
            'task_execution_id': params.get('task_execution_id'),
        })

        data_flow.add_openstack_data_to_context(wf_ex.context)
        data_flow.add_execution_to_context(wf_ex, wf_ex.context)
        data_flow.add_environment_to_context(wf_ex, wf_ex.context)

        return wf_ex
