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
from mistral import exceptions
from mistral.engine import states
from mistral.engine import workflow as wf
from mistral.engine.actions import action_factory as a_f
from mistral.db import api as db_api
from mistral.openstack.common import log as logging


LOG = logging.getLogger(__name__)


def start_workflow_execution(workbook_name, target_task_name):
    workbook = db_api.workbook_get(workbook_name)
    wb_dsl = parser.Parser(workbook["definition"])
    tasks_dsl = wf.find_workflow_tasks(wb_dsl, target_task_name)

    db_api.start_tx()

    try:
        execution = db_api.execution_create(workbook_name, {
            'target_task': target_task_name,
            'state': states.RUNNING
        })
        tasks = []
        for task_dsl in tasks_dsl:
            task = db_api.task_create(workbook_name, execution["id"], {
                "name": task_dsl["name"],
                "dependencies": task_dsl.get("dependsOn", []),
                "task_dsl": task_dsl,
                "service_dsl": wb_dsl.get_service(task_dsl["service_name"]),
                "state": states.IDLE,
                "tags": task_dsl.get("tags", None)
            })

            tasks.append(task)
        db_api.commit_tx()
    except Exception as e:
        raise exceptions.EngineException("Failed to create "
                                         "necessary DB objects: %s" % e)
    finally:
        db_api.end_tx()

    if tasks:
        _run_tasks(wf.find_tasks_to_start(tasks))

    return execution


def stop_workflow_execution(workbook_name, execution_id):
    return db_api.execution_update(workbook_name,
                                   execution_id, {'state': states.STOPPED})


def convey_task_result(workbook_name, execution_id, task_id, state, result):
    db_api.start_tx()

    try:
        task = db_api.task_update(workbook_name, execution_id,
                                  task_id, {'state': state, 'result': result})
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

        tasks = db_api.tasks_get(workbook_name, execution_id)
        if task['name'] == execution['target_task']:
            db_api.execution_update(workbook_name,
                                    execution_id, {'state': state})
        db_api.commit_tx()
    except Exception:
        raise exceptions.EngineException("Cannot perform task or"
                                         " execution updating in DB")
    finally:
        db_api.end_tx()

    if tasks:
        _run_tasks(wf.find_tasks_to_start(tasks))

    return task


def get_workflow_execution_state(workbook_name, execution_id):
    return db_api.execution_get(workbook_name,
                                execution_id)['state']


def get_task_state(workbook_name, execution_id, task_id):
    return db_api.task_get(workbook_name,
                           execution_id,
                           task_id)['state']


def _run_tasks(tasks):
    LOG.info("Workflow is running, tasks to run: %s" % tasks)
    for t in tasks:
        _run_task(t)


def _run_task(task):
    action = a_f.create_action(task)
    LOG.info("Task is started - %s" % task['name'])
    return action.run()
