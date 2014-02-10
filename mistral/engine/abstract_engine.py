# -*- coding: utf-8 -*-
#
# Copyright 2013 - Mirantis, Inc.
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

import abc

from mistral.openstack.common import log as logging
from mistral.db import api as db_api
from mistral import dsl
from mistral import exceptions as exc
from mistral.engine import states
from mistral.engine import workflow


LOG = logging.getLogger(__name__)


class AbstractEngine(object):
    @classmethod
    @abc.abstractmethod
    def _run_tasks(cls, tasks):
        pass

    @classmethod
    def start_workflow_execution(cls, workbook_name, task_name):
        wb_dsl = cls._get_wb_dsl(workbook_name)
        dsl_tasks = workflow.find_workflow_tasks(wb_dsl, task_name)
        db_api.start_tx()

        # Persist execution and tasks in DB.
        try:
            execution = cls._create_execution(workbook_name, task_name)

            tasks = cls._create_tasks(dsl_tasks, wb_dsl,
                                      workbook_name, execution['id'])

            db_api.commit_tx()
        except Exception as e:
            raise exc.EngineException("Failed to create necessary DB objects:"
                                      " %s" % e)
        finally:
            db_api.end_tx()

        cls._run_tasks(workflow.find_resolved_tasks(tasks))

        return execution

    @classmethod
    def convey_task_result(cls, workbook_name, execution_id,
                           task_id, state, result):
        db_api.start_tx()
        wb_dsl = cls._get_wb_dsl(workbook_name)
        #TODO(rakhmerov): validate state transition

        # Update task state.
        task = db_api.task_update(workbook_name, execution_id, task_id,
                                  {"state": state, "result": result})
        execution = db_api.execution_get(workbook_name, execution_id)
        cls._create_next_tasks(task,
                               wb_dsl,
                               workbook_name,
                               execution_id)

        # Determine what tasks need to be started.
        tasks = db_api.tasks_get(workbook_name, execution_id)
        # TODO(nmakhotkin) merge result into context

        try:
            new_exec_state = cls._determine_execution_state(execution, tasks)

            if execution['state'] != new_exec_state:
                db_api.execution_update(workbook_name, execution_id, {
                    "state": new_exec_state
                })

                LOG.info("Changed execution state: %s" % execution)

            db_api.commit_tx()
        except Exception as e:
            raise exc.EngineException("Failed to create necessary DB objects:"
                                      " %s" % e)
        finally:
            db_api.end_tx()

        if states.is_stopped_or_finished(execution["state"]):
            return task

        if tasks:
            cls._run_tasks(workflow.find_resolved_tasks(tasks))

        return task

    @classmethod
    def stop_workflow_execution(cls, workbook_name, execution_id):
        return db_api.execution_update(workbook_name, execution_id,
                                       {"state": states.STOPPED})

    @classmethod
    def get_workflow_execution_state(cls, workbook_name, execution_id):
        execution = db_api.execution_get(workbook_name, execution_id)

        if not execution:
            raise exc.EngineException("Workflow execution not found "
                                      "[workbook_name=%s, execution_id=%s]"
                                      % (workbook_name, execution_id))

        return execution["state"]

    @classmethod
    def get_task_state(cls, workbook_name, execution_id, task_id):
        task = db_api.task_get(workbook_name, execution_id, task_id)

        if not task:
            raise exc.EngineException("Task not found.")

        return task["state"]

    @classmethod
    def _create_execution(cls, workbook_name, task_name):
        return db_api.execution_create(workbook_name, {
            "workbook_name": workbook_name,
            "task": task_name,
            "state": states.RUNNING
        })

    @classmethod
    def _create_next_tasks(cls, task, wb_dsl,
                           workbook_name, execution_id):
        dsl_tasks = workflow.find_tasks_after_completion(task, wb_dsl)
        tasks = cls._create_tasks(dsl_tasks, wb_dsl,
                                  workbook_name, execution_id)
        return workflow.find_resolved_tasks(tasks)

    @classmethod
    def _create_tasks(cls, dsl_tasks, wb_dsl, workbook_name, execution_id):
        tasks = []
        for dsl_task in dsl_tasks:
            task = db_api.task_create(workbook_name, execution_id, {
                "name": dsl_task["name"],
                "requires": dsl_task.get("requires", {}),
                "task_dsl": dsl_task,
                "service_dsl": wb_dsl.get_service(dsl_task["service_name"]),
                "state": states.IDLE,
                "tags": dsl_task.get("tags", None)
            })

            tasks.append(task)
        return tasks

    @classmethod
    def _get_wb_dsl(cls, workbook_name):
        wb = db_api.workbook_get(workbook_name)
        wb_dsl = dsl.Parser(wb["definition"])

        return wb_dsl

    @classmethod
    def _determine_execution_state(cls, execution, tasks):
        if workflow.is_error(tasks):
            return states.ERROR

        if workflow.is_success(tasks) or workflow.is_finished(tasks):
            return states.SUCCESS

        return execution['state']
