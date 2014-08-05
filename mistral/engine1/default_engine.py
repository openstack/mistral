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

from oslo.config import cfg

from mistral.db import api as db_api
from mistral.engine1 import base
from mistral.engine1 import states
from mistral import exceptions as exc
from mistral.openstack.common import log as logging
from mistral.workflow import selector as wf_selector

LOG = logging.getLogger(__name__)
WF_TRACE = logging.getLogger(cfg.CONF.workflow_trace_log_name)

# TODO(rakhmerov): Add necessary logging including WF_TRACE.
# TODO(rakhmerov): All is written here assuming data models are not dicts.


def _select_workflow_handler(exec_db):
    handler_cls = wf_selector.select_workflow_handler(exec_db['wf_spec'])

    if not handler_cls:
        msg = 'Failed to find a workflow handler [workflow=%s.%s]' % \
              (exec_db['wb_spec'].name, exec_db['wf_name'])
        raise exc.EngineException(msg)

    return handler_cls(exec_db)


def _create_db_execution(workbook_name, workflow_name, task_name, input):
    # TODO(rakhmerov): Change DB model attributes.
    return db_api.execution_create(workbook_name, {
        "workbook_name": workbook_name,
        "workflow_name": workflow_name,
        "task": task_name,
        "state": states.RUNNING,
        "input": input
    })


def _create_db_tasks(exec_db, task_specs):
    tasks_db = []

    for task_spec in task_specs:
        task_db = db_api.task_create(exec_db.id, {
            'execution_id': exec_db.id,
            'name': task_spec.name,
            'state': states.IDLE,
            'specification': task_spec.to_dict(),
            'parameters': {},  # TODO(rakhmerov): Evaluate.
            'in_context': {},  # TODO(rakhmerov): Evaluate.
            'output': {},  # TODO(rakhmerov): Evaluate.
            'runtime_context': None
        })

        tasks_db.append(task_db)

    return tasks_db


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

    tasks_db = _create_db_tasks(exec_db, task_specs)

    for t in tasks_db:
        if t.action:
            _run_action(t)
        elif t.workflow:
            _run_workflow(t)
        else:
            msg = "Neither 'action' nor 'workflow' is defined in task" \
                  " specification [task_spec=%s]" % t
            raise exc.WorkflowException(msg)


class DefaultEngine(base.Engine):
    def start_workflow(self, workbook_name, workflow_name, task_name, input):
        db_api.start_tx()

        try:
            exec_db = _create_db_execution(
                workbook_name,
                workflow_name,
                task_name,
                input
            )

            wf_handler = _select_workflow_handler(exec_db)

            task_specs = wf_handler.start_workflow(task_name=task_name)

            if len(task_specs) > 0:
                _process(exec_db, task_specs)

            db_api.commit_tx()
        finally:
            db_api.end_tx()

        return exec_db

    def on_task_result(self, task_id, task_result):
        db_api.start_tx()

        try:
            task_db = db_api.task_get(task_id)
            exec_db = db_api.execution_get(task_db.execution_id)

            wf_handler = _select_workflow_handler(exec_db)

            task_specs = wf_handler.on_task_result(
                task_db,
                task_result
            )

            if len(task_specs) > 0:
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
            exec_db = db_api.execution_get(execution_id)

            wf_handler = _select_workflow_handler(exec_db)

            wf_handler.stop_workflow()

            db_api.commit_tx()
        finally:
            db_api.end_tx()

        return exec_db

    def resume_workflow(self, execution_id):
        db_api.start_tx()

        try:
            exec_db = db_api.execution_get(execution_id)

            wf_handler = _select_workflow_handler(exec_db)

            task_specs = wf_handler.resume_workflow()

            if len(task_specs) > 0:
                _process(exec_db, task_specs)

            db_api.commit_tx()
        finally:
            db_api.end_tx()

        return exec_db

    def rollback_workflow(self, execution_id):
        # TODO(rakhmerov): Implement.
        raise NotImplementedError
