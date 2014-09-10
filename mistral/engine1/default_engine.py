# Copyright 2014 - Mirantis, Inc.
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
from oslo.config import cfg

from mistral.db.v2 import api as db_api
from mistral.engine1 import base
from mistral.engine1 import policies
from mistral import exceptions as exc
from mistral.openstack.common import log as logging
from mistral.services import action_manager as a_m
from mistral.workbook import parser as spec_parser
from mistral.workflow import base as wf_base
from mistral.workflow import data_flow
from mistral.workflow import states
from mistral.workflow import workflow_handler_factory as wfh_factory

LOG = logging.getLogger(__name__)

# Submodules of mistral.engine will throw NoSuchOptError if configuration
# options required at top level of this  __init__.py are not imported before
# the submodules are referenced.
cfg.CONF.import_opt('workflow_trace_log_name', 'mistral.config')

WF_TRACE = logging.getLogger(cfg.CONF.workflow_trace_log_name)

# TODO(rakhmerov): Add necessary logging including WF_TRACE.


class DefaultEngine(base.Engine):
    def __init__(self, engine_client, executor_client):
        self._engine_client = engine_client
        self._executor_client = executor_client

    def start_workflow(self, workflow_name, workflow_input, **params):
        with db_api.transaction():
            wf_db = db_api.get_workflow(workflow_name)

            wf_spec = spec_parser.get_workflow_spec(wf_db.spec)

            exec_db = self._create_db_execution(
                wf_db,
                wf_spec,
                workflow_input,
                params
            )

            wf_handler = wfh_factory.create_workflow_handler(exec_db, wf_spec)

            # Calculate tasks to process next.
            task_specs = wf_handler.start_workflow(**params)

            if task_specs:
                self._process_task_specs(task_specs, exec_db, wf_handler)

        return exec_db

    def on_task_result(self, task_id, raw_result):
        with db_api.transaction():
            task_db = db_api.get_task(task_id)
            exec_db = db_api.get_execution(task_db.execution_id)

            self._after_task_complete(
                task_db,
                spec_parser.get_task_spec(task_db.spec),
                raw_result
            )

            if task_db.state == states.DELAYED:
                return task_db

            wf_handler = wfh_factory.create_workflow_handler(exec_db)

            # Calculate tasks to process next.
            task_specs = wf_handler.on_task_result(task_db, raw_result)

            if task_specs:
                self._process_task_specs(task_specs, exec_db, wf_handler)

            self._check_subworkflow_completion(exec_db)

        return task_db

    def stop_workflow(self, execution_id):
        with db_api.transaction():
            exec_db = db_api.get_execution(execution_id)

            wf_handler = wfh_factory.create_workflow_handler(exec_db)

            wf_handler.stop_workflow()

        return exec_db

    def resume_workflow(self, execution_id):
        with db_api.transaction():
            exec_db = db_api.get_execution(execution_id)

            wf_handler = wfh_factory.create_workflow_handler(exec_db)

            # Calculate tasks to process next.
            task_specs = wf_handler.resume_workflow()

            if task_specs:
                self._process_task_specs(task_specs, exec_db, wf_handler)

        return exec_db

    def rollback_workflow(self, execution_id):
        # TODO(rakhmerov): Implement.
        raise NotImplementedError

    def _process_task_specs(self, task_specs, exec_db, wf_handler):
        LOG.debug('Processing workflow tasks: %s' % task_specs)

        # DB tasks & Data Flow properties
        db_tasks = self._prepare_db_tasks(task_specs, exec_db, wf_handler)

        # Running actions/workflows.
        self._run_tasks(db_tasks, task_specs)

    def _prepare_db_tasks(self, task_specs, exec_db, wf_handler):
        wf_spec = spec_parser.get_workflow_spec(exec_db.wf_spec)

        new_db_tasks = self._create_db_tasks(exec_db, task_specs)

        # Evaluate Data Flow properties ('parameters', 'in_context').
        for t_db in new_db_tasks:
            task_spec = wf_spec.get_tasks()[t_db.name]

            data_flow.prepare_db_task(
                t_db,
                task_spec,
                wf_handler.get_upstream_tasks(task_spec),
                exec_db
            )

        return new_db_tasks

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
    def _create_db_tasks(exec_db, task_specs):
        new_db_tasks = []

        for task_spec in task_specs:
            t = db_api.create_task({
                'execution_id': exec_db.id,
                'name': task_spec.get_name(),
                'state': states.RUNNING,
                'spec': task_spec.to_dict(),
                'parameters': None,
                'in_context': None,
                'output': None,
                'runtime_context': None
            })

            new_db_tasks.append(t)

        return new_db_tasks

    @staticmethod
    def _before_task_start(task_db, task_spec):
        for p in policies.build_policies(task_spec.get_policies()):
            p.before_task_start(task_db, task_spec)

    @staticmethod
    def _after_task_complete(task_db, task_spec, raw_result):
        for p in policies.build_policies(task_spec.get_policies()):
            p.after_task_complete(task_db, task_spec, raw_result)

    def _run_tasks(self, db_tasks, task_specs):
        for t_db, t_spec in zip(db_tasks, task_specs):
            self._before_task_start(t_db, t_spec)

            # Policies could possibly change task state.
            if t_db.state == states.RUNNING:
                self._run_task(t_db, t_spec)

    def _run_task(self, t_db, t_spec):
        if t_spec.get_action_name():
            self._run_action(t_db, t_spec)
        elif t_spec.get_workflow_name():
            self._run_workflow(t_db, t_spec)

    def run_task(self, task_id):
        with db_api.transaction():
            task_db = db_api.update_task(task_id, {'state': states.RUNNING})
            task_spec = spec_parser.get_task_spec(task_db.spec)

            self._run_task(task_db, task_spec)

    def _run_action(self, task_db, task_spec):
        action_name = task_spec.get_action_name()
        action = a_m.get_action_db(action_name)

        if not action:
            raise exc.InvalidActionException(
                "Failed to find Action [action_name=%s]" % action_name
            )

        self._executor_client.run_action(
            task_db.id,
            action.action_class,
            action.attributes or {},
            task_db.parameters or {}
        )

    @staticmethod
    def _resolve_workflow(parent_wf_name, parent_wf_spec_name, wf_spec_name):
        wf_db = None

        if parent_wf_name != parent_wf_spec_name:
            # If parent workflow belongs to a workbook then
            # check child workflow within the same workbook
            # (to be able to use short names within workbooks).
            # If it doesn't exist then use a name from spec
            # to find a workflow in DB.
            wb_name = parent_wf_name.rstrip(parent_wf_spec_name)[:-1]

            wf_full_name = "%s.%s" % (wb_name, wf_spec_name)

            wf_db = db_api.load_workflow(wf_full_name)

        if not wf_db:
            wf_db = db_api.load_workflow(wf_spec_name)

        return wf_db

    def _run_workflow(self, task_db, task_spec):
        parent_exec_db = task_db.execution
        parent_wf_spec = spec_parser.get_workflow_spec(parent_exec_db.wf_spec)

        wf_spec_name = task_spec.get_workflow_name()

        wf_db = self._resolve_workflow(
            parent_exec_db.wf_name,
            parent_wf_spec.get_name(),
            wf_spec_name
        )

        if not wf_db:
            msg = 'Workflow not found [name=%s]' % wf_spec_name
            raise exc.WorkflowException(msg)

        wf_spec = spec_parser.get_workflow_spec(wf_db.spec)

        wf_input = task_db.parameters

        start_params = {'parent_task_id': task_db.id}

        for k, v in wf_input.items():
            if k not in wf_spec.get_parameters():
                start_params[k] = v
                del wf_input[k]

        self._engine_client.start_workflow(
            wf_db.name,
            wf_input,
            **start_params
        )

    def _check_subworkflow_completion(self, exec_db):
        if not exec_db.parent_task_id:
            return

        if exec_db.state == states.SUCCESS:
            self._engine_client.on_task_result(
                exec_db.parent_task_id,
                wf_base.TaskResult(data=exec_db.output)
            )
        elif exec_db.state == states.ERROR:
            err_msg = 'Failed subworkflow [execution_id=%s]' % exec_db.id

            self._engine_client.on_task_result(
                exec_db.parent_task_id,
                wf_base.TaskResult(error=err_msg)
            )
