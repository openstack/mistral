# Copyright 2014 - Mirantis, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
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
from oslo.config import cfg

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
cfg.CONF.import_opt('workflow_trace_log_name', 'mistral.config')

WF_TRACE = logging.getLogger(cfg.CONF.workflow_trace_log_name)

# TODO(rakhmerov): Add necessary logging including WF_TRACE.


class DefaultEngine(base.Engine):
    def __init__(self, engine_client):
        self._engine_client = engine_client

    @u.log_exec(LOG)
    def start_workflow(self, workflow_name, workflow_input, **params):
        WF_TRACE.info(
            "Starting the execution of workflow '%s'"
            % workflow_name
        )

        with db_api.transaction():
            wf_db = db_api.get_workflow(workflow_name)

            wf_spec = spec_parser.get_workflow_spec(wf_db.spec)

            utils.validate_workflow_input(wf_db, wf_spec, workflow_input)

            exec_db = self._create_db_execution(
                wf_db,
                wf_spec,
                workflow_input,
                params
            )

            wf_handler = wfh_factory.create_workflow_handler(exec_db, wf_spec)

            # Calculate commands to process next.
            commands = wf_handler.start_workflow(**params)

            self._run_commands(commands, exec_db, wf_handler)

        return exec_db

    @u.log_exec(LOG)
    def on_task_result(self, task_id, raw_result):
        with db_api.transaction():
            task_db = db_api.get_task(task_id)
            exec_db = db_api.get_execution(task_db.execution_id)

            raw_result = utils.transform_result(exec_db, task_db, raw_result)
            wf_handler = wfh_factory.create_workflow_handler(exec_db)

            self._after_task_complete(
                task_db,
                spec_parser.get_task_spec(task_db.spec),
                raw_result,
                wf_handler.wf_spec
            )

            if task_db.state == states.DELAYED:
                return task_db

            # Calculate commands to process next.
            commands = wf_handler.on_task_result(task_db, raw_result)

            self._run_commands(commands, exec_db, wf_handler, task_db)

            self._check_subworkflow_completion(exec_db)

        return task_db

    @u.log_exec(LOG)
    def pause_workflow(self, execution_id):
        with db_api.transaction():
            exec_db = db_api.get_execution(execution_id)

            wf_handler = wfh_factory.create_workflow_handler(exec_db)

            wf_handler.pause_workflow()

        return exec_db

    @u.log_exec(LOG)
    def resume_workflow(self, execution_id):
        with db_api.transaction():
            exec_db = db_api.get_execution(execution_id)

            wf_handler = wfh_factory.create_workflow_handler(exec_db)

            # Calculate commands to process next.
            commands = wf_handler.resume_workflow()

            self._run_commands(commands, exec_db, wf_handler)

        return exec_db

    def rollback_workflow(self, execution_id):
        # TODO(rakhmerov): Implement.
        raise NotImplementedError

    @staticmethod
    def _run_commands(commands, exec_db, wf_handler, cause_task_db=None):
        if not commands:
            return

        for cmd in commands:
            if not cmd.run(exec_db, wf_handler, cause_task_db):
                break

    @staticmethod
    def _create_db_execution(wf_db, wf_spec, wf_input, params):
        exec_db = db_api.create_execution({
            'wf_name': wf_db.name,
            'wf_spec': wf_spec.to_dict(),
            'start_params': params or {},
            'state': states.RUNNING,
            'input': wf_input or {},
            'output': {},
            'context': copy.copy(wf_input) or {},
            'parent_task_id': params.get('parent_task_id')
        })

        data_flow.add_openstack_data_to_context(wf_db, exec_db.context)
        data_flow.add_execution_to_context(exec_db, exec_db.context)

        return exec_db

    @staticmethod
    def _after_task_complete(task_db, task_spec, raw_result, wf_spec):
        for p in policies.build_policies(task_spec.get_policies(), wf_spec):
            p.after_task_complete(task_db, task_spec, raw_result)

    @u.log_exec(LOG)
    def run_task(self, task_id):
        with db_api.transaction():
            task_db = db_api.get_task(task_id)

            WF_TRACE.info(
                "Task '%s' [%s -> %s]"
                % (task_db.name, task_db.state, states.RUNNING)
            )

            task_db = db_api.update_task(task_id, {'state': states.RUNNING})
            task_spec = spec_parser.get_task_spec(task_db.spec)

            exec_db = task_db.execution

            wf_handler = wfh_factory.create_workflow_handler(exec_db)

            commands.RunTask(task_spec, task_db).run(exec_db, wf_handler)

    def _check_subworkflow_completion(self, exec_db):
        if not exec_db.parent_task_id:
            return

        if exec_db.state == states.SUCCESS:
            self._engine_client.on_task_result(
                exec_db.parent_task_id,
                wf_utils.TaskResult(data=exec_db.output)
            )
        elif exec_db.state == states.ERROR:
            err_msg = 'Failed subworkflow [execution_id=%s]' % exec_db.id

            self._engine_client.on_task_result(
                exec_db.parent_task_id,
                wf_utils.TaskResult(error=err_msg)
            )
