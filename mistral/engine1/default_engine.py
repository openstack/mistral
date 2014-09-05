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
from mistral.openstack.common import log as logging
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
        db_api.start_tx()

        try:
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

            db_api.commit_tx()
        finally:
            db_api.end_tx()

        return exec_db

    def on_task_result(self, task_id, raw_result):
        db_api.start_tx()

        try:
            task_db = db_api.get_task(task_id)
            exec_db = db_api.get_execution(task_db.execution_id)

            wf_handler = wfh_factory.create_workflow_handler(exec_db)

            # Calculate tasks to process next.
            task_specs = wf_handler.on_task_result(task_db, raw_result)

            if task_specs:
                self._apply_task_policies(task_db)
                self._apply_workflow_policies(exec_db, task_db)

                self._process_task_specs(task_specs, exec_db, wf_handler)

            self._check_subworkflow_completion(exec_db)

            db_api.commit_tx()
        finally:
            db_api.end_tx()

        return task_db

    def stop_workflow(self, execution_id):
        db_api.start_tx()

        try:
            exec_db = db_api.get_execution(execution_id)

            wf_handler = wfh_factory.create_workflow_handler(exec_db)

            wf_handler.stop_workflow()

            db_api.commit_tx()
        finally:
            db_api.end_tx()

        return exec_db

    def resume_workflow(self, execution_id):
        db_api.start_tx()

        try:
            exec_db = db_api.get_execution(execution_id)

            wf_handler = wfh_factory.create_workflow_handler(exec_db)

            # Calculate tasks to process next.
            task_specs = wf_handler.resume_workflow()

            if task_specs:
                self._process_task_specs(task_specs, exec_db, wf_handler)

            db_api.commit_tx()
        finally:
            db_api.end_tx()

        return exec_db

    def rollback_workflow(self, execution_id):
        # TODO(rakhmerov): Implement.
        raise NotImplementedError

    def _apply_task_policies(self, task_db):
        # TODO(rakhmerov): Implement.
        pass

    def _apply_workflow_policies(self, exec_db, task_db):
        # TODO(rakhmerov): Implement.
        pass

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

    def _create_db_execution(self, wf_db, wf_spec, wf_input, params):
        exec_db = db_api.create_execution({
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

    def _create_db_tasks(self, exec_db, task_specs):
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

    def _run_tasks(self, db_tasks, task_specs):
        for t_db, t_spec in zip(db_tasks, task_specs):
            if t_spec.get_action_name():
                self._run_action(t_db, t_spec)
            elif t_spec.get_workflow_name():
                self._run_workflow(t_db, t_spec)

    def _run_action(self, task_db, task_spec):
        # TODO(rakhmerov): Take care of ad-hoc actions.
        action_name = task_spec.get_action_name()

        self._executor_client.run_action(
            task_db.id,
            action_name,
            task_db.parameters or {}
        )

    def _run_workflow(self, task_db, task_spec):
        wf_name = task_spec.get_workflow_name()
        wf_input = task_db.parameters

        start_params = copy.copy(task_spec.get_workflow_parameters())
        start_params.update({'parent_task_id': task_db.id})

        self._engine_client.start_workflow(
            wf_name,
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
