# Copyright 2014 - Mirantis, Inc.
# Copyright 2015 - StackStorm, Inc.
# Copyright 2017 - Brocade Communications Systems, Inc.
# Copyright 2018 - Extreme Networks, Inc.
# Copyright 2020 Nokia Software.
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

from oslo_config import cfg
from oslo_log import log as logging
from osprofiler import profiler
import threading

from mistral import context as auth_ctx
from mistral.engine import base as eng
from mistral.event_engine import base as evt_eng
from mistral.executors import base as exe
from mistral.notifiers import base as notif
from mistral.rpc import base


LOG = logging.getLogger(__name__)

_ENGINE_CLIENT = None
_ENGINE_CLIENT_LOCK = threading.Lock()

_EXECUTOR_CLIENT = None
_EXECUTOR_CLIENT_LOCK = threading.Lock()

_EVENT_ENGINE_CLIENT = None
_EVENT_ENGINE_CLIENT_LOCK = threading.Lock()

_NOTIFIER_CLIENT = None
_NOTIFIER_CLIENT_LOCK = threading.Lock()


def cleanup():
    """Clean all the RPC clients.

    Intended to be used by tests to recreate all RPC related objects.
    Another usage is forking a child API process. In this case we must
    recreate all RPC objects so that they function properly.
    """

    global _ENGINE_CLIENT
    global _EXECUTOR_CLIENT
    global _EVENT_ENGINE_CLIENT
    global _NOTIFIER_CLIENT

    _ENGINE_CLIENT = None
    _EXECUTOR_CLIENT = None
    _EVENT_ENGINE_CLIENT = None
    _NOTIFIER_CLIENT = None

    base.cleanup()


def get_engine_client():
    global _ENGINE_CLIENT
    global _ENGINE_CLIENT_LOCK

    with _ENGINE_CLIENT_LOCK:
        if not _ENGINE_CLIENT:
            _ENGINE_CLIENT = EngineClient(cfg.CONF.engine)

    return _ENGINE_CLIENT


def get_executor_client():
    global _EXECUTOR_CLIENT
    global _EXECUTOR_CLIENT_LOCK

    with _EXECUTOR_CLIENT_LOCK:
        if not _EXECUTOR_CLIENT:
            _EXECUTOR_CLIENT = ExecutorClient(cfg.CONF.executor)

    return _EXECUTOR_CLIENT


def get_event_engine_client():
    global _EVENT_ENGINE_CLIENT
    global _EVENT_ENGINE_CLIENT_LOCK

    with _EVENT_ENGINE_CLIENT_LOCK:
        if not _EVENT_ENGINE_CLIENT:
            _EVENT_ENGINE_CLIENT = EventEngineClient(cfg.CONF.event_engine)

    return _EVENT_ENGINE_CLIENT


def get_notifier_client():
    global _NOTIFIER_CLIENT
    global _NOTIFIER_CLIENT_LOCK

    with _NOTIFIER_CLIENT_LOCK:
        if not _NOTIFIER_CLIENT:
            _NOTIFIER_CLIENT = NotifierClient(cfg.CONF.notifier)

    return _NOTIFIER_CLIENT


class EngineClient(eng.Engine):
    """RPC Engine client."""

    def __init__(self, rpc_conf_dict):
        """Constructs an RPC client for engine.

        :param rpc_conf_dict: Dict containing RPC configuration.
        """
        self._client = base.get_rpc_client_driver()(rpc_conf_dict)

    @base.wrap_messaging_exception
    def start_workflow(self, wf_identifier, wf_namespace='', wf_ex_id=None,
                       wf_input=None, description='', async_=False, **params):
        """Starts workflow sending a request to engine over RPC.

        :param wf_identifier: Workflow identifier.
        :param wf_namespace: Workflow namespace.
        :param wf_input: Workflow input data as a dictionary.
        :param wf_ex_id: Workflow execution id. If passed, it will be set
            in the new execution object.
        :param description: Execution description.
        :param async_: If True, start workflow in asynchronous mode
            (w/o waiting for completion).
        :param params: Additional workflow type specific parameters.
        :return: Workflow execution.
        """

        call = self._client.async_call if async_ else self._client.sync_call

        LOG.info(
            "Send RPC request 'start_workflow'[workflow_identifier=%s, "
            "workflow_input=%s, description=%s, params=%s]",
            wf_identifier,
            wf_input,
            description,
            params
        )

        return call(
            auth_ctx.ctx(),
            'start_workflow',
            wf_identifier=wf_identifier,
            wf_namespace=wf_namespace,
            wf_ex_id=wf_ex_id,
            wf_input=wf_input or {},
            description=description,
            params=params
        )

    @base.wrap_messaging_exception
    def start_task(self, task_ex_id, first_run, waiting,
                   triggered_by, rerun, reset, **params):
        """Starts task sending a request to engine over RPC.

        """

        return self._client.async_call(
            auth_ctx.ctx(),
            'start_task',
            task_ex_id=task_ex_id,
            first_run=first_run,
            waiting=waiting,
            triggered_by=triggered_by,
            rerun=rerun,
            reset=reset,
            params=params
        )

    @base.wrap_messaging_exception
    def start_action(self, action_name, action_input,
                     description=None, namespace='', **params):
        """Starts action sending a request to engine over RPC.

        :param action_name: Action name.
        :param action_input: Action input data as a dictionary.
        :param description: Execution description.
        :param namespace: The namespace of the action.
        :param params: Additional options for action running.
        :return: Action execution.
        """
        return self._client.sync_call(
            auth_ctx.ctx(),
            'start_action',
            action_name=action_name,
            action_input=action_input or {},
            description=description,
            namespace=namespace,
            params=params
        )

    @base.wrap_messaging_exception
    @profiler.trace('engine-client-on-action-complete', hide_args=True)
    def on_action_complete(self, action_ex_id, result, wf_action=False,
                           async_=False):
        """Conveys action result to Mistral Engine.

        This method should be used by clients of Mistral Engine to update
        the state of an action execution once action has executed. One of
        the clients of this method is Mistral REST API server that receives
        action result from the outside action handlers.

        Note: calling this method serves an event notifying Mistral that
        it possibly needs to move the workflow on, i.e. run other workflow
        tasks for which all dependencies are satisfied.

        :param action_ex_id: Action execution id.
        :param result: Action execution result.
        :param wf_action: If True it means that the given id points to
            a workflow execution rather than action execution. It happens
            when a nested workflow execution sends its result to a parent
            workflow.
        :param async_: If True, run action in asynchronous mode (w/o waiting
            for completion).
        :return: Action(or workflow if wf_action=True) execution object.
        """

        call = self._client.async_call if async_ else self._client.sync_call

        LOG.info(
            "Send RPC request 'on_action_complete'[action_ex_id=%s, "
            "result=%s]",
            action_ex_id,
            result.cut_repr() if result else None
        )

        return call(
            auth_ctx.ctx(),
            'on_action_complete',
            action_ex_id=action_ex_id,
            result=result,
            wf_action=wf_action
        )

    @base.wrap_messaging_exception
    @profiler.trace('engine-client-on-action-update', hide_args=True)
    def on_action_update(self, action_ex_id, state, wf_action=False,
                         async_=False):
        """Conveys update of action state to Mistral Engine.

        This method should be used by clients of Mistral Engine to update
        the state of an action execution once action has executed.

        Note: calling this method serves an event notifying Mistral that it
        may need to change the state of the parent task and workflow. Use
        on_action_complete if the action execution reached completion state.

        :param action_ex_id: Action execution id.
        :param state: Updated state.
        :param wf_action: If True it means that the given id points to
            a workflow execution rather than action execution. It happens
            when a nested workflow execution sends its result to a parent
            workflow.
        :param async_: If True, run action in asynchronous mode (w/o waiting
            for completion).
        :return: Action(or workflow if wf_action=True) execution object.
        """

        call = self._client.async_call if async_ else self._client.sync_call

        LOG.info(
            "Send RPC request 'on_action_update'"
            "[action_ex_id=%s, state=%s]",
            action_ex_id,
            state
        )

        return call(
            auth_ctx.ctx(),
            'on_action_update',
            action_ex_id=action_ex_id,
            state=state,
            wf_action=wf_action
        )

    @base.wrap_messaging_exception
    def pause_workflow(self, wf_ex_id):
        """Stops the workflow with the given execution id.

        :param wf_ex_id: Workflow execution id.
        :return: Workflow execution.
        """

        LOG.info(
            "Send RPC request 'pause_workflow'[execution_id=%s]",
            wf_ex_id
        )

        return self._client.sync_call(
            auth_ctx.ctx(),
            'pause_workflow',
            wf_ex_id=wf_ex_id
        )

    @base.wrap_messaging_exception
    def rerun_workflow(self, task_ex_id, reset=True, skip=False, env=None):
        """Rerun the workflow.

        This method reruns workflow with the given execution id
        at the specific task execution id.

        :param task_ex_id: Task execution id.
        :param reset: If true, then reset task execution state and purge
            action execution for the task.
        :param skip: If True, then skip failed task and continue workflow
            execution.
        :param env: Environment variables to update.
        :return: Workflow execution.
        """

        LOG.info(
            "Send RPC request 'rerun_workflow'[task_ex_id=%s]",
            task_ex_id
        )

        return self._client.sync_call(
            auth_ctx.ctx(),
            'rerun_workflow',
            task_ex_id=task_ex_id,
            reset=reset,
            skip=skip,
            env=env
        )

    @base.wrap_messaging_exception
    def resume_workflow(self, wf_ex_id, env=None):
        """Resumes the workflow with the given execution id.

        :param wf_ex_id: Workflow execution id.
        :param env: Environment variables to update.
        :return: Workflow execution.
        """

        LOG.info(
            "Send RPC request 'resume_workflow'[wf_ex_id=%s]",
            wf_ex_id
        )

        return self._client.sync_call(
            auth_ctx.ctx(),
            'resume_workflow',
            wf_ex_id=wf_ex_id,
            env=env
        )

    @base.wrap_messaging_exception
    def stop_workflow(self, wf_ex_id, state, message=None):
        """Stops workflow execution with given status.

        Once stopped, the workflow is complete with SUCCESS or ERROR,
        and can not be resumed.

        :param wf_ex_id: Workflow execution id
        :param state: State assigned to the workflow: SUCCESS or ERROR
        :param message: Optional information string

        :return: Workflow execution, model.Execution
        """

        LOG.info(
            "Send RPC request 'stop_workflow'[execution_id=%s,"
            " state=%s, message=%s]",
            wf_ex_id,
            state,
            message
        )

        return self._client.sync_call(
            auth_ctx.ctx(),
            'stop_workflow',
            wf_ex_id=wf_ex_id,
            state=state,
            message=message
        )

    @base.wrap_messaging_exception
    def rollback_workflow(self, wf_ex_id):
        """Rolls back the workflow with the given execution id.

        :param wf_ex_id: Workflow execution id.

        :return: Workflow execution.
        """

        LOG.info(
            "Send RPC request 'rollback_workflow'[execution_id=%s]",
            wf_ex_id
        )

        return self._client.sync_call(
            auth_ctx.ctx(),
            'rollback_workflow',
            wf_ex_id=wf_ex_id
        )

    @base.wrap_messaging_exception
    def process_action_heartbeats(self, action_ex_ids):
        """Receives action execution heartbeats.

        :param action_ex_ids: Action execution ids.
        """

        LOG.info(
            "Send RPC request 'report_running_actions'[action_ex_ids=%s]",
            action_ex_ids
        )

        return self._client.async_call(
            auth_ctx.ctx(),
            'report_running_actions',
            action_ex_ids=action_ex_ids
        )


class ExecutorClient(exe.Executor):
    """RPC Executor client."""

    def __init__(self, rpc_conf_dict):
        """Constructs an RPC client for the Executor."""

        self.topic = cfg.CONF.executor.topic
        self._client = base.get_rpc_client_driver()(rpc_conf_dict)

    @profiler.trace('executor-client-run-action')
    def run_action(self, action, action_ex_id, safe_rerun, exec_ctx,
                   redelivered=False, target=None, async_=True, timeout=None):
        """Sends a request to run action to executor.

        :param action: Action to run.
        :param action_ex_id: Action execution id.
        :param safe_rerun: If true, action would be re-run if executor dies
            during execution.
        :param exec_ctx: A dict of values providing information about
            the current execution.
        :param redelivered: Tells if given action was run before on another
            executor.
        :param target: Target (group of action executors).
        :param async_: If True, run action in asynchronous mode (w/o waiting
            for completion).
        :param timeout: a period of time in seconds after which execution of
            action will be interrupted
        :return: Action result.
        """
        rpc_kwargs = {
            'action': action,
            'action_ex_id': action_ex_id,
            'safe_rerun': safe_rerun,
            'exec_ctx': exec_ctx,
            'timeout': timeout
        }

        rpc_client_method = (
            self._client.async_call if async_
            else self._client.sync_call
        )

        LOG.info(
            "Send RPC request 'run_action' [action=%s, action_ex_id=%s]",
            action,
            action_ex_id
        )

        return rpc_client_method(auth_ctx.ctx(), 'run_action', **rpc_kwargs)


class EventEngineClient(evt_eng.EventEngine):
    """RPC EventEngine client."""

    def __init__(self, rpc_conf_dict):
        """Constructs an RPC client for the EventEngine service."""
        self._client = base.get_rpc_client_driver()(rpc_conf_dict)

    def create_event_trigger(self, trigger, events):
        LOG.info(
            "Send RPC request 'create_event_trigger'[trigger=%s, "
            "events=%s", trigger, events
        )
        return self._client.async_call(
            auth_ctx.ctx(),
            'create_event_trigger',
            trigger=trigger,
            events=events,
            fanout=True,
        )

    def delete_event_trigger(self, trigger, events):
        LOG.info(
            "Send RPC request 'delete_event_trigger'[trigger=%s, "
            "events=%s", trigger, events
        )
        return self._client.async_call(
            auth_ctx.ctx(),
            'delete_event_trigger',
            trigger=trigger,
            events=events,
            fanout=True,
        )

    def update_event_trigger(self, trigger):
        LOG.info(
            "Send RPC request 'update_event_trigger'[rpc_ctx=%s,"
            " trigger=%s", trigger
        )
        return self._client.async_call(
            auth_ctx.ctx(),
            'update_event_trigger',
            trigger=trigger,
            fanout=True,
        )


class NotifierClient(notif.Notifier):
    """RPC Notifier client."""

    def __init__(self, rpc_conf_dict):
        """Constructs an RPC client for the Notifier service."""
        self._client = base.get_rpc_client_driver()(rpc_conf_dict)

    def notify(self, ex_id, data, event, timestamp, publishers):
        try:
            return self._client.async_call(
                auth_ctx.ctx(),
                'notify',
                ex_id=ex_id,
                data=data,
                event=event,
                timestamp=timestamp,
                publishers=publishers
            )
        except Exception:
            LOG.exception('Unable to send notification.')
