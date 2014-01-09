# Copyright (c) 2013 Mirantis Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from mistral import dsl as parser
from mistral.engine import states
from mistral.engine.single import workflow as wf
from mistral.db import api as db_api


def start_workflow_execution(workbook_name, target_task_name):
    workflow = _get_workflow(workbook_name, target_task_name)

    db_api.start_tx()

    try:
        execution = db_api.execution_create(workbook_name, {
            'target_task': target_task_name,
            'state': states.RUNNING
        })
        workflow.execution = execution
        workflow.create_tasks()
        workflow.run_resolved_tasks()

        db_api.commit_tx()

    finally:

        db_api.end_tx()

    return execution


def stop_workflow_execution(workbook_name, execution_id):
    return db_api.execution_update(workbook_name,
                                   execution_id, {'state': states.STOPPED})


def convey_task_result(workbook_name, execution_id, task_id, state, result):

    db_api.start_tx()

    try:
        task = db_api.task_update(workbook_name, execution_id,
                                  task_id, {'state': state})
        if task["state"] == states.ERROR:
            db_api.execution_update(workbook_name, execution_id, {
                "state": states.ERROR
            })

            db_api.commit_tx()

            return task
        execution = db_api.execution_get(workbook_name, execution_id)

        if states.is_stopped_or_finished(execution["state"]):

            db_api.commit_tx()

            return task

        workflow = _get_workflow(
            workbook_name, execution['target_task'])
        workflow.execution = execution
        if task['name'] == execution['target_task']:
            db_api.execution_update(workbook_name,
                                    execution_id, {'state': state})
        else:
            workflow.run_resolved_tasks()

        db_api.commit_tx()

        return task
    finally:
        db_api.end_tx()


def get_workflow_execution_state(workbook_name, execution_id):
    return db_api.execution_get(workbook_name,
                                execution_id)['state']


def get_task_state(workbook_name, execution_id, task_id):
    return db_api.task_get(workbook_name,
                           execution_id,
                           task_id)['state']


def _get_workflow(workbook_name, task_name):
    workbook = db_api.workbook_get(workbook_name)
    dsl_parser = parser.Parser(workbook['definition'])
    tasks = dsl_parser.get_tasks()
    workflow = wf.MistralWorkflow(task_name)
    for name, data in tasks.items():
        workflow.add(wf.create_task(name, data, dsl_parser))
    workflow.freeze()
    return workflow
