# -*- coding: utf-8 -*-
#
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
from mistral import exceptions as exc
from mistral.openstack.common import log as logging
from mistral.workbook import parser as spec_parser
from mistral.workflow import data_flow
from mistral.workflow import selector as wf_selector
from mistral.workflow import states

LOG = logging.getLogger(__name__)

# Submodules of mistral.engine will throw NoSuchOptError if configuration
# options required at top level of this  __init__.py are not imported before
# the submodules are referenced.
cfg.CONF.import_opt('workflow_trace_log_name', 'mistral.config')

WF_TRACE = logging.getLogger(cfg.CONF.workflow_trace_log_name)

# TODO(rakhmerov): Add necessary logging including WF_TRACE.


def _select_workflow_handler(exec_db):
    wf_spec = spec_parser.get_workflow_spec(exec_db['wf_spec'])

    handler_cls = wf_selector.select_workflow_handler(wf_spec)

    if not handler_cls:
        msg = 'Failed to find a workflow handler [workflow=%s.%s]' % \
              (exec_db['wb_spec'].name, exec_db['wf_name'])
        raise exc.EngineException(msg)

    return handler_cls(exec_db)


def _create_db_execution(wf_spec, input, start_params):
    return db_api.create_execution({
        'wf_spec': wf_spec.to_dict(),
        'start_params': start_params,
        'state': states.RUNNING,
        'input': input,
        'context': copy.copy(input) or {}
    })


def _create_db_tasks(exec_db, task_specs):
    for task_spec in task_specs:
        db_api.create_task({
            'execution_id': exec_db.id,
            'name': task_spec.get_name(),
            'state': states.RUNNING,
            'spec': task_spec.to_dict(),
            'parameters': None,
            'in_context': None,
            'output': None,
            'runtime_context': None
        })

    return exec_db.tasks


def _apply_task_policies(task_db):
    # TODO(rakhmerov): Implement.
    pass


def _apply_workflow_policies(exec_db, task_db):
    # TODO(rakhmerov): Implement.
    pass


def _run_action(t):
    # TODO(rakhmerov): Implement.
    pass


def _run_workflow(t):
    # TODO(rakhmerov): Implement.
    pass


def _process(exec_db, task_specs):
    LOG.debug('Processing workflow tasks: %s' % task_specs)

    _create_db_tasks(exec_db, task_specs)

    # Evaluate Data Flow properties ('parameters', 'in_context').
    data_flow.prepare_db_tasks(exec_db.tasks, task_specs, exec_db.context)

    for t in task_specs:
        if t.get_action_name():
            _run_action(t)
        elif t.get_workflow_name():
            _run_workflow(t)
        else:
            msg = "Neither 'action' nor 'workflow' is defined in task" \
                  " specification [task_spec=%s]" % t
            raise exc.WorkflowException(msg)


class DefaultEngine(base.Engine):
    def start_workflow(self, workbook_name, workflow_name, input, **kwargs):
        db_api.start_tx()

        try:
            wb_db = db_api.get_workbook(workbook_name)

            wb_spec = \
                spec_parser.get_workbook_spec_from_yaml(wb_db.definition)

            exec_db = _create_db_execution(
                wb_spec.get_workflows()[workflow_name],
                input,
                kwargs
            )

            wf_handler = _select_workflow_handler(exec_db)

            task_specs = wf_handler.start_workflow(**kwargs)

            if task_specs:
                _process(exec_db, task_specs)

            db_api.commit_tx()
        finally:
            db_api.end_tx()

        return exec_db

    def on_task_result(self, task_id, task_result):
        db_api.start_tx()

        try:
            task_db = db_api.get_task(task_id)
            exec_db = db_api.get_execution(task_db.execution_id)

            wf_handler = _select_workflow_handler(exec_db)

            task_specs = wf_handler.on_task_result(
                task_db,
                task_result
            )

            if task_specs:
                _apply_task_policies(task_db)
                _apply_workflow_policies(exec_db, task_db)

                _process(exec_db, task_specs)

            db_api.commit_tx()
        finally:
            db_api.end_tx()

        return task_db

    def stop_workflow(self, execution_id):
        db_api.start_tx()

        try:
            exec_db = db_api.get_execution(execution_id)

            wf_handler = _select_workflow_handler(exec_db)

            wf_handler.stop_workflow()

            db_api.commit_tx()
        finally:
            db_api.end_tx()

        return exec_db

    def resume_workflow(self, execution_id):
        db_api.start_tx()

        try:
            exec_db = db_api.get_execution(execution_id)

            wf_handler = _select_workflow_handler(exec_db)

            task_specs = wf_handler.resume_workflow()

            if task_specs:
                _process(exec_db, task_specs)

            db_api.commit_tx()
        finally:
            db_api.end_tx()

        return exec_db

    def rollback_workflow(self, execution_id):
        # TODO(rakhmerov): Implement.
        raise NotImplementedError
