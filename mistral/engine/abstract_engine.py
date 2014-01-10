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
from mistral import exceptions as ex
from mistral.engine import states


LOG = logging.getLogger(__name__)


class AbstractEngine(object):
    @abc.abstractmethod
    def start_workflow_execution(self, workbook_name, target_task_name):
        pass

    @abc.abstractmethod
    def convey_task_result(self, workbook_name, execution_id, task_id,
                           state, result):
        pass

    @classmethod
    def stop_workflow_execution(cls, workbook_name, execution_id):
        return db_api.execution_update(workbook_name, execution_id,
                                       {"state": states.STOPPED})

    @classmethod
    def get_workflow_execution_state(cls, workbook_name, execution_id):
        execution = db_api.execution_get(workbook_name, execution_id)

        if not execution:
            raise ex.EngineException("Workflow execution not found "
                                     "[workbook_name=%s, execution_id=%s]"
                                     % (workbook_name, execution_id))

        return execution["state"]

    @classmethod
    def get_task_state(cls, workbook_name, execution_id, task_id):
        task = db_api.task_get(workbook_name, execution_id, task_id)

        if not task:
            raise ex.EngineException("Task not found.")

        return task["state"]

    @classmethod
    def _create_execution(cls, workbook_name, target_task_name):
        return db_api.execution_create(workbook_name, {
            "workbook_name": workbook_name,
            "target_task": target_task_name,
            "state": states.RUNNING
        })

    @classmethod
    def _create_tasks(cls, dsl_tasks, wb_dsl, workbook_name, execution_id):
        tasks = []
        for dsl_task in dsl_tasks:
            task = db_api.task_create(workbook_name, execution_id, {
                "name": dsl_task["name"],
                "dependencies": dsl_task.get("dependsOn", []),
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
    def _determine_workflow_is_finished(cls, workbook_name, execution, task):
        if task["state"] == states.ERROR:
            execution = db_api.execution_update(workbook_name,
                                                execution['id'],
                                                {"state": states.ERROR})

            LOG.info("Execution finished with error: %s" % execution)

            return True

        if states.is_stopped_or_finished(execution["state"]):
            # The execution has finished or stopped temporarily.
            return True

        return None
