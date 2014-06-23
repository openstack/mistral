# -*- coding: utf-8 -*-
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
from oslo import messaging
import six
from stevedore import driver

# Submoules of mistral.engine will throw NoSuchOptError if configuration
# options required at top level of this  __init__.py are not imported before
# the submodules are referenced.
cfg.CONF.import_opt('workflow_trace_log_name', 'mistral.config')

from mistral import context as auth_context
from mistral.db import api as db_api
from mistral import dsl_parser as parser
from mistral.engine import data_flow
from mistral.engine import retry
from mistral.engine import states
from mistral.engine import workflow
from mistral import exceptions as exc
from mistral.openstack.common import log as logging


LOG = logging.getLogger(__name__)
WORKFLOW_TRACE = logging.getLogger(cfg.CONF.workflow_trace_log_name)


def get_transport(transport=None):
    return (transport if transport else messaging.get_transport(cfg.CONF))


def get_engine(name, transport):
    mgr = driver.DriverManager(
        namespace='mistral.engine.drivers',
        name=name,
        invoke_on_load=True,
        invoke_kwds={'transport': transport})
    return mgr.driver


@six.add_metaclass(abc.ABCMeta)
class Engine(object):
    """Abstract engine for workflow execution."""

    transport = None

    def __init__(self, transport=None):
        self.transport = get_transport(transport)

    @abc.abstractmethod
    def _run_tasks(cls, tasks):
        raise NotImplementedError()

    def start_workflow_execution(self, cntx, **kwargs):
        """Starts a workflow execution based on the specified workbook name
        and target task.

        :param cntx: a request context dict
        :type cntx: MistralContext
        :param kwargs: a dict of method arguments
        :type kwargs: dict
        :return: Workflow execution.
        """
        workbook_name = kwargs.get('workbook_name')
        task_name = kwargs.get('task_name')
        context = kwargs.get('context', None)

        context = copy.copy(context) if context else {}

        WORKFLOW_TRACE.info("New execution started - [workbook_name = '%s', "
                            "task_name = '%s']" % (workbook_name, task_name))

        db_api.start_tx()

        # Persist execution and tasks in DB.
        try:
            workbook = self._get_workbook(workbook_name)
            execution = self._create_execution(workbook_name,
                                               task_name,
                                               context)

            tasks = self._create_tasks(
                workflow.find_workflow_tasks(workbook, task_name),
                workbook,
                workbook_name, execution['id']
            )

            tasks_to_start, delayed_tasks = workflow.find_resolved_tasks(tasks)

            self._add_variables_to_data_flow_context(context, execution)

            data_flow.prepare_tasks(tasks_to_start, context)

            db_api.commit_tx()
        except Exception as e:
            msg = "Failed to create necessary DB objects: %s" % e
            LOG.exception(msg)
            raise exc.EngineException(msg)
        finally:
            db_api.end_tx()

        for task in delayed_tasks:
            self._schedule_run(workbook, task, context)

        self._run_tasks(tasks_to_start)

        return execution

    def stop_workflow_execution(self, cntx, **kwargs):
        """Stops the workflow execution with the given id.

        :param cntx: a request context dict
        :type cntx: dict
        :param kwargs: a dict of method arguments
        :type kwargs: dict
        :return: Workflow execution.
        """
        execution_id = kwargs.get('execution_id')

        return db_api.execution_update(execution_id,
                                       {"state": states.STOPPED})

    def convey_task_result(self, cntx, **kwargs):
        """Conveys task result to Mistral Engine.

        This method should be used by clients of Mistral Engine to update
        state of a task once task action has been performed. One of the
        clients of this method is Mistral REST API server that receives
        task result from the outside action handlers.

        Note: calling this method serves an event notifying Mistral that
        it possibly needs to move the workflow on, i.e. run other workflow
        tasks for which all dependencies are satisfied.

        :param cntx: a request context dict
        :type cntx: dict
        :param kwargs: a dict of method arguments
        :type kwargs: dict
        :return: Task.
        """
        task_id = kwargs.get('task_id')
        state = kwargs.get('state')
        result = kwargs.get('result')

        db_api.start_tx()

        try:
            # TODO(rakhmerov): validate state transition
            task = db_api.task_get(task_id)
            workbook = self._get_workbook(task['workbook_name'])

            wf_trace_msg = "Task '%s' [%s -> %s" % \
                           (task['name'], task['state'], state)

            wf_trace_msg += ']' if state == states.ERROR \
                else ", result = %s]" % result
            WORKFLOW_TRACE.info(wf_trace_msg)

            task_output = data_flow.get_task_output(task, result)

            # Update task state.
            task, outbound_context = self._update_task(workbook, task, state,
                                                       task_output)

            execution = db_api.execution_get(task['execution_id'])

            self._create_next_tasks(task, workbook)

            # Determine what tasks need to be started.
            tasks = db_api.tasks_get(workbook_name=task['workbook_name'],
                                     execution_id=task['execution_id'])

            new_exec_state = self._determine_execution_state(execution, tasks)

            if execution['state'] != new_exec_state:
                wf_trace_msg = \
                    "Execution '%s' [%s -> %s]" % \
                    (execution['id'], execution['state'], new_exec_state)
                WORKFLOW_TRACE.info(wf_trace_msg)

                execution = \
                    db_api.execution_update(execution['id'], {
                        "state": new_exec_state
                    })

                LOG.info("Changed execution state: %s" % execution)

            tasks_to_start, delayed_tasks = workflow.find_resolved_tasks(tasks)

            self._add_variables_to_data_flow_context(outbound_context,
                                                     execution)

            data_flow.prepare_tasks(tasks_to_start, outbound_context)

            db_api.commit_tx()
        except Exception as e:
            msg = "Failed to create necessary DB objects: %s" % e
            LOG.exception(msg)
            raise exc.EngineException(msg)
        finally:
            db_api.end_tx()

        if states.is_stopped_or_finished(execution["state"]):
            return task

        for task in delayed_tasks:
            self._schedule_run(workbook, task, outbound_context)

        if tasks_to_start:
            self._run_tasks(tasks_to_start)

        return task

    def get_workflow_execution_state(self, cntx, **kwargs):
        """Gets the workflow execution state.

        :param cntx: a request context dict
        :type cntx: dict
        :param kwargs: a dict of method arguments
        :type kwargs: dict
        :return: Current workflow state.
        """
        workbook_name = kwargs.get('workbook_name')
        execution_id = kwargs.get('execution_id')

        execution = db_api.execution_get(execution_id)

        if not execution:
            raise exc.EngineException("Workflow execution not found "
                                      "[workbook_name=%s, execution_id=%s]"
                                      % (workbook_name, execution_id))

        return execution["state"]

    def get_task_state(self, cntx, **kwargs):
        """Gets task state.

        :param cntx: a request context dict
        :type cntx: dict
        :param kwargs: a dict of method arguments
        :type kwargs: dict
        :return: Current task state.
        """
        task_id = kwargs.get('task_id')

        task = db_api.task_get(task_id)

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
    def _add_variables_to_data_flow_context(cls, df_ctx, execution):
        db_workbook = db_api.workbook_get(execution['workbook_name'])

        data_flow.add_openstack_data_to_context(df_ctx, db_workbook)
        data_flow.add_execution_to_context(df_ctx, execution)

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
            action_spec = workbook.get_action(task.get_full_action_name())

            db_task = db_api.task_create(execution_id, {
                "name": task.name,
                "requires": task.get_requires(),
                "task_spec": task.to_dict(),
                "action_spec": {} if not action_spec
                else action_spec.to_dict(),
                "state": state,
                "tags": task.get_property("tags", None),
                "task_runtime_context": task_runtime_context,
                "workbook_name": workbook_name
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
        """Update the task with the runtime information. The outbound_context
        for this task is also calculated.
        :return: task, outbound_context. task is the updated task and
        computed outbound context.
        """
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
        task = db_api.task_update(task["id"], update_values)

        return task, outbound_context

    def _schedule_run(cls, workbook, task, outbound_context):
        """Schedules task to run after the delay defined in the task
        specification. If no delay is specified this method is a no-op.
        """

        # TODO(rakhmerov): Reavaluate parameter 'context' once it's clear
        # how to work with trust chains correctly in keystone
        # (waiting for corresponding changes to be made).
        def run_delayed_task(context):
            """Runs the delayed task. Performs all the steps required to setup
            a task to run which are not already done. This is mostly code
            copied over from convey_task_result.

            :param context Mistral authentication context inherited from a
                caller thread.
            """
            auth_context.set_ctx(context)

            db_api.start_tx()

            try:
                execution_id = task['execution_id']
                execution = db_api.execution_get(execution_id)

                # Change state from DELAYED to IDLE to unblock processing.

                WORKFLOW_TRACE.info("Task '%s' [%s -> %s]"
                                    % (task['name'],
                                       task['state'], states.IDLE))

                db_task = db_api.task_update(task['id'],
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
            eventlet.spawn_after(delay_sec, run_delayed_task,
                                 context=auth_context.ctx())
        else:
            LOG.warn("No delay specified for task(id=%s) name=%s. Not "
                     "scheduling for execution." % (task['id'], task['name']))


class EngineClient(object):
    """RPC client for the Engine."""

    def __init__(self, transport):
        """Construct an RPC client for the Engine.

        :param transport: a messaging transport handle
        :type transport: Transport
        """
        serializer = auth_context.RpcContextSerializer(
            auth_context.JsonPayloadSerializer())
        target = messaging.Target(topic=cfg.CONF.engine.topic)
        self._client = messaging.RPCClient(transport, target,
                                           serializer=serializer)

    def start_workflow_execution(self, workbook_name, task_name, context=None):
        """Starts a workflow execution based on the specified workbook name
        and target task.

        :param workbook_name: Workbook name
        :param task_name: Target task name
        :param context: Execution context which defines a workflow input
        :return: Workflow execution.
        """
        cntx = auth_context.ctx()
        kwargs = {'workbook_name': workbook_name,
                  'task_name': task_name,
                  'context': context}
        return self._client.call(cntx, 'start_workflow_execution', **kwargs)

    def stop_workflow_execution(self, workbook_name, execution_id):
        """Stops the workflow execution with the given id.

        :param workbook_name: Workbook name.
        :param execution_id: Workflow execution id.
        :return: Workflow execution.
        """
        cntx = auth_context.ctx()
        kwargs = {'workbook_name': workbook_name,
                  'execution_id': execution_id}
        return self._client.call(cntx, 'stop_workflow_execution', **kwargs)

    def convey_task_result(self, task_id, state, result):
        """Conveys task result to Mistral Engine.

        This method should be used by clients of Mistral Engine to update
        state of a task once task action has been performed. One of the
        clients of this method is Mistral REST API server that receives
        task result from the outside action handlers.

        Note: calling this method serves an event notifying Mistral that
        it possibly needs to move the workflow on, i.e. run other workflow
        tasks for which all dependencies are satisfied.

        :param task_id: Task id.
        :param state: New task state.
        :param result: Task result data.
        :return: Task.
        """
        cntx = auth_context.ctx()
        kwargs = {'task_id': task_id,
                  'state': state,
                  'result': result}
        return self._client.call(cntx, 'convey_task_result', **kwargs)

    def get_workflow_execution_state(self, workbook_name, execution_id):
        """Gets the workflow execution state.

        :param workbook_name: Workbook name.
        :param execution_id: Workflow execution id.
        :return: Current workflow state.
        """
        cntx = auth_context.ctx()
        kwargs = {'workbook_name': workbook_name,
                  'execution_id': execution_id}
        return self._client.call(
            cntx, 'get_workflow_execution_state', **kwargs)

    def get_task_state(self, workbook_name, execution_id, task_id):
        """Gets task state.

        :param workbook_name: Workbook name.
        :param execution_id: Workflow execution id.
        :param task_id: Task id.
        :return: Current task state.
        """
        cntx = auth_context.ctx()
        kwargs = {'workbook_name': workbook_name,
                  'executioin_id': execution_id,
                  'task_id': task_id}
        return self._client.call(cntx, 'get_task_state', **kwargs)
