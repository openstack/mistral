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
from mistral.engine1 import commands
from mistral.engine1 import policies
from mistral.engine1 import utils
from mistral.openstack.common import log as logging
from mistral import utils as u
from mistral.workbook import parser as spec_parser
from mistral.workflow import data_flow
from mistral.workflow import states
from mistral.workflow import utils as wf_utils
from mistral.workflow import workflow_handler_factory as wfh_factory


LOG = logging.getLogger(__name__)

# Submodules of mistral.engine will throw NoSuchOptError if configuration
# options required at top level of this  __init__.py are not imported before
# the submodules are referenced.


class DefaultEngine(base.Engine):
    def __init__(self, engine_client):
        self._engine_client = engine_client

    @u.log_exec(LOG)
    def start_workflow(self, workflow_name, workflow_input, **params):
        exec_id = None

        try:
            params = self._canonize_workflow_params(params)

            with db_api.transaction():
                wf_db = db_api.get_workflow_definition(workflow_name)

                wf_spec = spec_parser.get_workflow_spec(wf_db.spec)

                utils.validate_workflow_input(wf_db, wf_spec, workflow_input)

                wf_ex = self._create_db_execution(
                    wf_db,
                    wf_spec,
                    workflow_input,
                    params
                )
                exec_id = wf_ex.id

                u.wf_trace.info(
                    wf_ex,
                    "Starting the execution of workflow '%s'" % workflow_name
                )

                wf_handler = wfh_factory.create_workflow_handler(
                    wf_ex,
                    wf_spec
                )

                # Calculate commands to process next.
                cmds = wf_handler.start_workflow(**params)

                self._run_local_commands(cmds, wf_ex, wf_handler)

            self._run_remote_commands(cmds, wf_ex, wf_handler)

        except Exception as e:
            LOG.error(
                "Failed to start workflow '%s' id=%s: %s\n%s",
                workflow_name, exec_id, e, traceback.format_exc()
            )
            self._fail_workflow(exec_id, e)
            raise e

        return wf_ex

    @u.log_exec(LOG)
    def on_task_result(self, task_id, result):
        task_name = "Unknown"
        exec_id = None

        try:
            with db_api.transaction():
                task_ex = db_api.get_task_execution(task_id)
                task_name = task_ex.name
                wf_ex = db_api.get_workflow_execution(
                    task_ex.workflow_execution_id
                )
                exec_id = wf_ex.id

                result = utils.transform_result(wf_ex, task_ex, result)
                wf_handler = wfh_factory.create_workflow_handler(wf_ex)

                self._after_task_complete(
                    task_ex,
                    spec_parser.get_task_spec(task_ex.spec),
                    result,
                    wf_handler.wf_spec
                )

                if task_ex.state == states.DELAYED:
                    return task_ex

                # Calculate commands to process next.
                cmds = wf_handler.on_task_result(task_ex, result)

                self._run_local_commands(
                    cmds,
                    wf_ex,
                    wf_handler,
                    task_ex
                )

            self._run_remote_commands(cmds, wf_ex, wf_handler)
            self._check_subworkflow_completion(wf_ex)

        except Exception as e:
            LOG.error(
                "Failed to handle results for task '%s' id=%s: %s\n%s",
                task_name, task_id, e, traceback.format_exc()
            )
            # TODO(dzimine): try to find out which command caused failure.
            self._fail_workflow(exec_id, e)
            raise e

        return task_ex

    @u.log_exec(LOG)
    def run_task(self, task_id):
        task_name = "Unknown"
        exec_id = None

        try:
            with db_api.transaction():
                task_ex = db_api.get_task_execution(task_id)
                task_name = task_ex.name

                u.wf_trace.info(
                    task_ex,
                    "Task '%s' [%s -> %s]"
                    % (task_ex.name, task_ex.state, states.RUNNING)
                )

                task_ex = db_api.update_task_execution(
                    task_id,
                    {'state': states.RUNNING}
                )

                task_spec = spec_parser.get_task_spec(task_ex.spec)

                wf_ex = task_ex.workflow_execution
                exec_id = wf_ex.id

                wf_handler = wfh_factory.create_workflow_handler(wf_ex)

                cmd = commands.RunTask(task_spec, task_ex)

                cmd.run_local(wf_ex, wf_handler)

            cmd.run_remote(wf_ex, wf_handler)

        except Exception as e:
            LOG.error(
                "Failed to run task '%s': %s\n%s",
                task_name, e, traceback.format_exc()
            )
            self._fail_workflow(exec_id, e, task_id)
            raise e

    @u.log_exec(LOG)
    def pause_workflow(self, execution_id):
        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(execution_id)

            wf_handler = wfh_factory.create_workflow_handler(wf_ex)

            wf_handler.pause_workflow()

        return wf_ex

    @u.log_exec(LOG)
    def resume_workflow(self, execution_id):
        try:
            with db_api.transaction():
                wf_ex = db_api.get_workflow_execution(execution_id)

                wf_handler = wfh_factory.create_workflow_handler(wf_ex)

                # Calculate commands to process next.
                cmds = wf_handler.resume_workflow()

                self._run_local_commands(cmds, wf_ex, wf_handler)

            self._run_remote_commands(cmds, wf_ex, wf_handler)

        except Exception as e:
            LOG.error("Failed to resume execution id=%s: %s\n%s",
                      execution_id, e, traceback.format_exc())
            self._fail_workflow(execution_id, e)
            raise e

        return wf_ex

    @u.log_exec(LOG)
    def stop_workflow(self, execution_id, state, message=None):
        with db_api.transaction():
            wf_ex = db_api.get_execution(execution_id)
            wf_handler = wfh_factory.create_workflow_handler(wf_ex)

            return wf_handler.stop_workflow(state, message)

    @u.log_exec(LOG)
    def rollback_workflow(self, execution_id):
        # TODO(rakhmerov): Implement.
        raise NotImplementedError

    def _fail_workflow(self, execution_id, err, task_id=None):
        """Private helper to fail workflow on exceptions."""
        with db_api.transaction():
            err_msg = str(err)

            wf_ex = db_api.load_workflow_execution(execution_id)

            if wf_ex is None:
                LOG.error("Cant fail workflow execution id='%s': not found.",
                          execution_id)
                return

            wf_handler = wfh_factory.create_workflow_handler(wf_ex)
            wf_handler.stop_workflow(states.ERROR, err_msg)

            if task_id:
                # Note(dzimine): Don't call self.engine_client:
                # 1) to avoid computing and triggering next tasks
                # 2) to avoid a loop in case of error in transport
                wf_handler.on_task_result(
                    db_api.get_task_execution(task_id),
                    wf_utils.TaskResult(error=err_msg)
                )

    @staticmethod
    def _canonize_workflow_params(params):
        # Resolve environment parameter.
        env = params.get('env', {})

        if not isinstance(env, dict) and not isinstance(env, basestring):
            raise ValueError('Unexpected type for environment. '
                             '[environment=%s]' % str(env))

        if isinstance(env, basestring):
            env_db = db_api.get_environment(env)
            env = env_db.variables
            params['env'] = env

        return params

    @staticmethod
    def _run_local_commands(cmds, wf_ex, wf_handler, cause_task_ex=None):
        if not cmds:
            return

        for cmd in cmds:
            if not cmd.run_local(wf_ex, wf_handler, cause_task_ex):
                return False

        return True

    @staticmethod
    def _run_remote_commands(cmds, wf_ex, wf_handler, cause_task_ex=None):
        if not cmds:
            return

        for cmd in cmds:
            if not cmd.run_remote(wf_ex, wf_handler, cause_task_ex):
                return False

        return True

    @staticmethod
    def _create_db_execution(wf_db, wf_spec, wf_input, params):
        wf_ex = db_api.create_workflow_execution({
            'workflow_name': wf_db.name,
            'spec': wf_spec.to_dict(),
            'start_params': params or {},
            'state': states.RUNNING,
            'input': wf_input or {},
            'output': {},
            'context': copy.copy(wf_input) or {},
            'task_execution_id': params.get('parent_task_id'),
        })

        data_flow.add_openstack_data_to_context(wf_ex.context)
        data_flow.add_execution_to_context(wf_ex, wf_ex.context)
        data_flow.add_environment_to_context(wf_ex, wf_ex.context)

        return wf_ex

    @staticmethod
    def _after_task_complete(task_ex, task_spec, result, wf_spec):
        for p in policies.build_policies(task_spec.get_policies(), wf_spec):
            p.after_task_complete(task_ex, task_spec, result)

    def _check_subworkflow_completion(self, wf_ex):
        if not wf_ex.task_execution_id:
            return

        if wf_ex.state == states.SUCCESS:
            self._engine_client.on_task_result(
                wf_ex.task_execution_id,
                wf_utils.TaskResult(data=wf_ex.output)
            )
        elif wf_ex.state == states.ERROR:
            err_msg = 'Failed subworkflow [execution_id=%s]' % wf_ex.id

            self._engine_client.on_task_result(
                wf_ex.task_execution_id,
                wf_utils.TaskResult(error=err_msg)
            )
