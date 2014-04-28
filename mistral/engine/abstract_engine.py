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
import copy
import eventlet

from oslo.config import cfg

from mistral.openstack.common import log as logging
from mistral.db import api as db_api
from mistral import dsl_parser as parser
from mistral import exceptions as exc
from mistral.engine import states
from mistral.engine import workflow
from mistral.engine import data_flow
from mistral.engine import retry


LOG = logging.getLogger(__name__)
WORKFLOW_TRACE = logging.getLogger(cfg.CONF.workflow_trace_log_name)


class AbstractEngine(object):
    transport = None

    @classmethod
    @abc.abstractmethod
    def _run_tasks(cls, tasks):
        pass

    @classmethod
    def start_workflow_execution(cls, workbook_name, task_name, context):
        context = copy.copy(context) if context else {}

        db_api.start_tx()

        WORKFLOW_TRACE.info("New execution started - [workbook_name = '%s', "
                            "task_name = '%s']" % (workbook_name, task_name))

        # Persist execution and tasks in DB.
        try:
            workbook = cls._get_workbook(workbook_name)
            execution = cls._create_execution(workbook_name,
                                              task_name,
                                              context)

            tasks = cls._create_tasks(
                workflow.find_workflow_tasks(workbook, task_name),
                workbook,
                workbook_name, execution['id']
            )

            tasks_to_start, delayed_tasks = workflow.find_resolved_tasks(tasks)

            cls._add_variables_to_data_flow_context(context, execution)

            data_flow.prepare_tasks(tasks_to_start, context)

            db_api.commit_tx()
        except Exception as e:
            LOG.exception("Failed to create necessary DB objects.")
            raise exc.EngineException("Failed to create necessary DB objects:"
                                      " %s" % e)
        finally:
            db_api.end_tx()

        for task in delayed_tasks:
            cls._schedule_run(workbook, task, context)

        cls._run_tasks(tasks_to_start)

        return execution

    @classmethod
    def convey_task_result(cls, workbook_name, execution_id,
                           task_id, state, result):
        db_api.start_tx()

        try:
            workbook = cls._get_workbook(workbook_name)
            #TODO(rakhmerov): validate state transition
            task = db_api.task_get(workbook_name, execution_id, task_id)

            wf_trace_msg = "Task '%s' [%s -> %s" % \
                           (task['name'], task['state'], state)

            wf_trace_msg += ']' if state == states.ERROR \
                else ", result = %s]" % result
            WORKFLOW_TRACE.info(wf_trace_msg)

            task_output = data_flow.get_task_output(task, result)

            # Update task state.
            task, outbound_context = cls._update_task(workbook, task, state,
                                                      task_output)

            execution = db_api.execution_get(workbook_name, execution_id)

            cls._create_next_tasks(task, workbook)

            # Determine what tasks need to be started.
            tasks = db_api.tasks_get(workbook_name, execution_id)

            new_exec_state = cls._determine_execution_state(execution, tasks)

            if execution['state'] != new_exec_state:
                wf_trace_msg = \
                    "Execution '%s' [%s -> %s]" % \
                    (execution_id, execution['state'], new_exec_state)
                WORKFLOW_TRACE.info(wf_trace_msg)

                execution = \
                    db_api.execution_update(workbook_name, execution_id, {
                        "state": new_exec_state
                    })

                LOG.info("Changed execution state: %s" % execution)

            tasks_to_start, delayed_tasks = workflow.find_resolved_tasks(tasks)

            cls._add_variables_to_data_flow_context(outbound_context,
                                                    execution)

            data_flow.prepare_tasks(tasks_to_start, outbound_context)

            db_api.commit_tx()
        except Exception as e:
            LOG.exception("Failed to create necessary DB objects.")
            raise exc.EngineException("Failed to create necessary DB objects:"
                                      " %s" % e)
        finally:
            db_api.end_tx()

        if states.is_stopped_or_finished(execution["state"]):
            return task

        for task in delayed_tasks:
            cls._schedule_run(workbook, task, outbound_context)

        if tasks_to_start:
            cls._run_tasks(tasks_to_start)

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
    def _create_execution(cls, workbook_name, task_name, context):
        return db_api.execution_create(workbook_name, {
            "workbook_name": workbook_name,
            "task": task_name,
            "state": states.RUNNING,
            "context": context
        })

    @classmethod
    def _add_variables_to_data_flow_context(cls, context, execution):
        db_workbook = db_api.workbook_get(execution['workbook_name'])

        data_flow.add_token_to_context(context, db_workbook)
        data_flow.add_execution_to_context(context, execution)

    @classmethod
    def _create_next_tasks(cls, task, workbook):
        tasks = workflow.find_tasks_after_completion(task, workbook)

        db_tasks = cls._create_tasks(tasks, workbook, task['workbook_name'],
                                     task['execution_id'])
        return workflow.find_resolved_tasks(db_tasks)

    @classmethod
    def _create_tasks(cls, task_list, workbook, workbook_name, execution_id):
        tasks = []

        for task in task_list:
            state, task_runtime_context = retry.get_task_runtime(task)
            action_ns = workbook.namespaces.get(task.get_action_namespace())

            action_spec = None
            if action_ns:
                action_spec = \
                    action_ns.actions.get(task.get_action_name())

            db_task = db_api.task_create(workbook_name, execution_id, {
                "name": task.name,
                "requires": task.requires,
                "task_spec": task.to_dict(),
                "action_spec": {} if not action_spec
                else action_spec.to_dict(),
                "state": state,
                "tags": task.get_property("tags", None),
                "task_runtime_context": task_runtime_context
            })

            tasks.append(db_task)

        return tasks

    @classmethod
    def _get_workbook(cls, workbook_name):
        wb = db_api.workbook_get(workbook_name)
        return parser.get_workbook(wb["definition"])

    @classmethod
    def _determine_execution_state(cls, execution, tasks):
        if workflow.is_error(tasks):
            return states.ERROR

        if workflow.is_success(tasks) or workflow.is_finished(tasks):
            return states.SUCCESS

        return execution['state']

    @classmethod
    def _update_task(cls, workbook, task, state, task_output):
        """
        Update the task with the runtime information. The outbound_context
        for this task is also calculated.
        :return: task, outbound_context. task is the updated task and
        computed outbound context.
        """
        workbook_name = task['workbook_name']
        execution_id = task['execution_id']
        task_spec = workbook.tasks.get(task["name"])
        task_runtime_context = task["task_runtime_context"]

        # Compute the outbound_context, state and exec_flow_context.
        outbound_context = data_flow.get_outbound_context(task, task_output)
        state, task_runtime_context = retry.get_task_runtime(
            task_spec, state, outbound_context, task_runtime_context)

        # Update the task.
        update_values = {"state": state,
                         "output": task_output,
                         "task_runtime_context": task_runtime_context}
        task = db_api.task_update(workbook_name, execution_id, task["id"],
                                  update_values)

        return task, outbound_context

    @classmethod
    def _schedule_run(cls, workbook, task, outbound_context):
        """
        Schedules task to run after the delay defined in the task
        specification. If no delay is specified this method is a no-op.
        """

        def run_delayed_task():
            """
            Runs the delayed task. Performs all the steps required to setup
            a task to run which are not already done. This is mostly code
            copied over from convey_task_result.
            """
            db_api.start_tx()
            try:
                workbook_name = task['workbook_name']
                execution_id = task['execution_id']
                execution = db_api.execution_get(workbook_name, execution_id)

                # Change state from DELAYED to IDLE to unblock processing.

                WORKFLOW_TRACE.info("Task '%s' [%s -> %s]"
                                    % (task['name'],
                                       task['state'], states.IDLE))

                db_task = db_api.task_update(workbook_name,
                                             execution_id,
                                             task['id'],
                                             {"state": states.IDLE})
                task_to_start = [db_task]
                data_flow.prepare_tasks(task_to_start, outbound_context)
                db_api.commit_tx()
            finally:
                db_api.end_tx()

            if not states.is_stopped_or_finished(execution["state"]):
                cls._run_tasks(task_to_start)

        task_spec = workbook.tasks.get(task['name'])
        retries, break_on, delay_sec = task_spec.get_retry_parameters()
        if delay_sec > 0:
            # Run the task after the specified delay.
            eventlet.spawn_after(delay_sec, run_delayed_task)
        else:
            LOG.warn("No delay specified for task(id=%s) name=%s. Not "
                     "scheduling for execution." % (task['id'], task['name']))
