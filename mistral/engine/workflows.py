# Copyright 2016 - Nokia Networks.
# Copyright 2016 - Brocade Communications Systems, Inc.
# Copyright 2018 - Extreme Networks, Inc.
# Copyright 2019 - NetCracker Technology Corp.
# Modified in 2025 by NetCracker Technology Corp.
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
import json
from oslo_config import cfg
from oslo_log import log as logging
from osprofiler import profiler

from mistral import context as auth_ctx
from mistral.db.v2 import api as db_api
from mistral.db.v2.sqlalchemy import models as db_models
from mistral.engine import dispatcher
from mistral.engine import post_tx_queue
from mistral.engine import utils as engine_utils
from mistral import exceptions as exc
from mistral import expressions as expr
from mistral.lang import parser as spec_parser
from mistral.notifiers import base as notif
from mistral.notifiers import notification_events as events
from mistral.rpc import clients as rpc
from mistral.services.kafka_notifications import send_notification
from mistral.services import triggers
from mistral.services import workflows as wf_service
from mistral.utils import wf_trace
from mistral.workflow import base as wf_base
from mistral.workflow import commands
from mistral.workflow import data_flow
from mistral.workflow import states
from mistral_lib import actions as ml_actions
from mistral_lib import utils

LOG = logging.getLogger(__name__)

_START_WORKFLOW_PATH = (
    'mistral.engine.workflows._start_workflow'
)


class Workflow(object, metaclass=abc.ABCMeta):
    """Workflow.

    Represents a workflow and defines interface that can be used by
    Mistral engine or its components in order to manipulate with workflows.
    """

    def __init__(self, wf_ex=None):
        self.wf_ex = wf_ex
        if wf_ex:
            # We're processing a workflow that's already in progress.
            self.wf_spec = spec_parser.get_workflow_spec_by_execution_id(
                wf_ex.id
            )
        else:
            self.wf_spec = None

    def _notify(self, from_state, to_state):
        publishers = self.wf_ex.params.get('notify')

        if not publishers and not isinstance(publishers, list):
            return

        notifier = notif.get_notifier(cfg.CONF.notifier.type)

        event = events.identify_workflow_event(from_state, to_state)

        filtered_publishers = []

        for publisher in publishers:
            if not isinstance(publisher, dict):
                continue

            target_events = publisher.get('event_types', [])

            if not target_events or event in target_events:
                filtered_publishers.append(publisher)

        if not filtered_publishers:
            return

        root_execution_id = self.wf_ex.root_execution_id or self.wf_ex.id

        notification_data = {
            "id": self.wf_ex.id,
            "name": self.wf_ex.name,
            "workflow_name": self.wf_ex.workflow_name,
            "workflow_namespace": self.wf_ex.workflow_namespace,
            "workflow_id": self.wf_ex.workflow_id,
            "root_execution_id": root_execution_id,
            "state": self.wf_ex.state,
            "state_info": self.wf_ex.state_info,
            "project_id": self.wf_ex.project_id,
            "task_execution_id": self.wf_ex.task_execution_id,
            "params": self.wf_ex.params,
            "created_at": utils.datetime_to_str(self.wf_ex.created_at),
            "updated_at": utils.datetime_to_str(self.wf_ex.updated_at)
        }

        if 'params' in self.wf_ex and 'headers' in self.wf_ex['params']:
            notification_data['headers'] = self.wf_ex['params']['headers']

        kafka_data = {
            'rpc_ctx': auth_ctx.ctx().to_dict(),
            'ex_id': self.wf_ex.id,
            'data': notification_data,
            'event': event,
            'timestamp': self.wf_ex.updated_at,
            'publishers': filtered_publishers
        }

        def _send_notification():
            if cfg.CONF.kafka_notifications.enabled:
                delivered = send_notification(kafka_data)
                if delivered:
                    return

            notifier.notify(
                notification_data["id"],
                notification_data,
                event,
                notification_data["updated_at"],
                filtered_publishers
            )
        post_tx_queue.register_operation(_send_notification)

    @profiler.trace('workflow-start')
    def start(self, wf_def, wf_ex_id, input_dict, desc='', params=None,
              is_planned=False):
        """Start workflow.

        :param wf_def: Workflow definition.
        :param wf_ex_id: Workflow execution id.
        :param input_dict: Workflow input.
        :param desc: Workflow execution description.
        :param params: Workflow type specific parameters.

        :raises
        """

        if ((self.wf_ex is not None and not is_planned) or
           (is_planned and self.wf_ex is None)):
            raise AssertionError("Impossible state")

        wf_trace.info(
            self.wf_ex,
            'Starting workflow [name=%s, input=%s]' %
            (wf_def.name, utils.cut(input_dict))
        )

        if not is_planned:
            # New workflow execution.
            self.wf_spec = spec_parser.get_workflow_spec_by_definition_id(
                wf_def.id,
                wf_def.updated_at
            )

            self.validate_input(input_dict)
            self._create_execution(
                wf_def,
                wf_ex_id,
                self.prepare_input(input_dict),
                desc,
                params
            )

        self.set_state(states.RUNNING)

        wf_ctrl = wf_base.get_controller(self.wf_ex, self.wf_spec)

        dispatcher.dispatch_workflow_commands(
            self.wf_ex,
            wf_ctrl.continue_workflow()
        )

    def stop(self, state, msg=None, sync=True, force=False):
        """Stop workflow.

        :param state: New workflow state.
        :param msg: Additional explaining message.
        :param sync: Mode to update wf state.
        """
        assert self.wf_ex

        if state == states.SUCCESS:
            self._succeed_workflow(self._get_final_context(), msg)
        elif state == states.ERROR:
            self._fail_workflow(self._get_final_context(), msg)
        elif state == states.CANCELLED:
            if sync:
                self._cancel_workflow(self._get_final_context(), msg, force)
            else:
                self._mark_workflow_cancelled(msg)

    def pause(self, msg=None):
        """Pause workflow.

        :param msg: Additional explaining message.
        """

        assert self.wf_ex

        if states.is_paused(self.wf_ex.state):
            return

        # Set the state of this workflow to paused.
        self.set_state(states.PAUSED, state_info=msg)

        # If workflow execution is a subworkflow,
        # schedule update to the task execution.
        if self.wf_ex.task_execution_id:
            # Import the task_handler module here to avoid circular reference.
            from mistral.engine import task_handler
            task_handler.schedule_on_action_update(self.wf_ex)

    def resume(self, env=None):
        """Resume workflow.

        :param env: Environment.
        """

        assert self.wf_ex

        wf_service.update_workflow_execution_env(self.wf_ex, env)

        self.set_state(states.RUNNING)

        wf_ctrl = wf_base.get_controller(self.wf_ex)

        # Calculate commands to process next.
        cmds = wf_ctrl.continue_workflow()

        self._continue_workflow(cmds)

        # If workflow execution is a subworkflow,
        # schedule update to the task execution.
        if self.wf_ex.task_execution_id:
            # Import the task_handler module here to avoid circular reference.
            from mistral.engine import task_handler

            task_handler.schedule_on_action_update(self.wf_ex)

    def prepare_input(self, input_dict):
        for k, v in self.wf_spec.get_input().items():
            if k not in input_dict or input_dict[k] is utils.NotDefined:
                input_dict[k] = v

        return input_dict

    def validate_input(self, input_dict):
        engine_utils.validate_input(
            self.wf_spec.get_input(),
            input_dict,
            self.wf_spec.get_name(),
            self.wf_spec.__class__.__name__
        )

    def rerun(self, task, reset=True, skip=False, env=None):
        """Rerun workflow from the given task.

        :param task: An engine task associated with the task the workflow
            needs to rerun from.
        :param reset: If True, reset task state including deleting its action
            executions.
        :param skip: If True, then skip failed task and continue workflow
            execution.
        :param env: Environment.
        """

        assert self.wf_ex

        wf_service.update_workflow_execution_env(self.wf_ex, env)

        self._recursive_rerun()

        wf_ctrl = wf_base.get_controller(self.wf_ex)

        # Calculate commands to process next.
        if skip:
            cmds = wf_ctrl.skip_tasks([task.task_ex])
        else:
            cmds = wf_ctrl.rerun_tasks([task.task_ex], reset=reset)

        if cmds:
            task.cleanup_runtime_context()

        self._continue_workflow(cmds)

    def _recursive_rerun(self):
        """Rerun all parent workflow executions recursively.

        If there is a parent execution then it reruns as well.
        """

        from mistral.engine import workflow_handler

        self.set_state(states.RUNNING)

        # TODO(rakhmerov): We call an internal method of a module here.
        # The simplest way is to make it public, however, I believe
        # it's another "bad smell" that tells that some refactoring
        # of the architecture is needed.
        workflow_handler._schedule_check_and_fix_integrity(self.wf_ex)

        if self.wf_ex.task_execution_id:
            parent_task_ex = db_api.get_task_execution(
                self.wf_ex.task_execution_id
            )

            parent_wf = Workflow(wf_ex=parent_task_ex.workflow_execution)

            parent_wf.lock()

            parent_wf._recursive_rerun()

            # TODO(rakhmerov): this is a design issue again as in many places.
            # Ideally, we should just build (or get) an instance of Task and
            # call set_state() on it.
            from mistral.engine import task_handler
            task_handler.mark_task_running(parent_task_ex, parent_wf.wf_spec)

    def _get_backlog(self):
        return self.wf_ex.runtime_context.get(dispatcher.BACKLOG_KEY)

    def _continue_workflow(self, cmds):
        # When resuming a workflow we need to ignore all 'pause'
        # commands because workflow controller takes tasks that
        # completed within the period when the workflow was paused.
        cmds = list(
            [c for c in cmds if not isinstance(c, commands.PauseWorkflow)]
        )

        # Since there's no explicit task causing the operation
        # we need to mark all not processed tasks as processed
        # because workflow controller takes only completed tasks
        # with flag 'processed' equal to False.
        for t_ex in self.wf_ex.task_executions:
            if states.is_completed(t_ex.state) and not t_ex.processed:
                t_ex.processed = True

        if cmds or self._get_backlog():
            dispatcher.dispatch_workflow_commands(self.wf_ex, cmds)
        else:
            self.check_and_complete()

    @profiler.trace('workflow-lock')
    def lock(self):
        assert self.wf_ex

        return db_api.acquire_lock(db_models.WorkflowExecution, self.wf_ex.id)

    def _get_final_context(self):
        final_ctx = {}

        wf_ctrl = wf_base.get_controller(self.wf_ex)

        try:
            final_ctx = wf_ctrl.evaluate_workflow_final_context()
        except Exception as e:
            LOG.warning(
                'Failed to get final context for workflow execution. '
                '[wf_ex_id: %s, wf_name: %s, error: %s]',
                self.wf_ex.id,
                self.wf_ex.name,
                str(e)
            )

        return final_ctx

    def _create_execution(self, wf_def, wf_ex_id, input_dict, desc,
                          params, state=states.IDLE):
        wf_body = {
            'id': wf_ex_id,
            'name': wf_def.name,
            'description': desc,
            'tags': wf_def.tags,
            'workflow_name': wf_def.name,
            'workflow_namespace': wf_def.namespace,
            'workflow_id': wf_def.id,
            'spec': self.wf_spec.to_dict(),
            'state': state,
            'output': {},
            'task_execution_id': params.get('task_execution_id'),
            'root_execution_id': params.get('root_execution_id'),
            'runtime_context': {'index': params.get('index', 0)}
        }
        retry_no = None
        task_ex_id = params.get('task_execution_id')
        if task_ex_id:
            task_ex = db_api.get_task_execution(task_ex_id)
            retry_policy = task_ex['runtime_context'].get('retry_task_policy')
            if retry_policy:
                retry_no = retry_policy['retry_no']
        if retry_no:
            wf_body['runtime_context']['retry_no'] = retry_no
        else:
            wf_body['runtime_context']['retry_no'] = 0

        if wf_def.workbook_name:
            wf_body['runtime_context']['wb_name'] = wf_def.workbook_name

        self.wf_ex = db_api.create_workflow_execution(wf_body)

        LOG.info("Created workflow execution [workflow_name=%s, wf_ex_id=%s, "
                 "task_execution_id=%s, root_execution_id=%s]", wf_def.name,
                 self.wf_ex.id, params.get('task_execution_id'),
                 params.get('root_execution_id'))

        self.wf_ex.input = input_dict or {}

        params['env'] = _get_environment(params)
        params['read_only'] = False

        self.wf_ex.params = params

        data_flow.add_openstack_data_to_context(self.wf_ex)
        data_flow.add_execution_to_context(self.wf_ex)
        data_flow.add_workflow_variables_to_context(self.wf_ex, self.wf_spec)

        spec_parser.cache_workflow_spec_by_execution_id(
            self.wf_ex.id,
            self.wf_spec
        )

    @profiler.trace('workflow-set-state')
    def set_state(self, state, state_info=None):
        assert self.wf_ex

        cur_state = self.wf_ex.state

        if states.is_valid_transition(cur_state, state):
            wf_ex = db_api.update_workflow_execution_state(
                id=self.wf_ex.id,
                cur_state=cur_state,
                state=state
            )

            if wf_ex is None:
                # Do nothing because the state was updated previously.
                return False

            self.wf_ex = wf_ex
            self.wf_ex.state_info = json.dumps(state_info) \
                if isinstance(state_info, dict) else state_info

            self._notify(cur_state, state)

            wf_trace.info(
                self.wf_ex,
                "Workflow '%s' [%s -> %s, msg=%s]" %
                (self.wf_ex.workflow_name,
                 cur_state,
                 state,
                 self.wf_ex.state_info)
            )
        else:
            msg = ("Can't change workflow execution state from %s to %s. "
                   "[workflow=%s, execution_id=%s]" %
                   (cur_state, state, self.wf_ex.name, self.wf_ex.id))

            raise exc.WorkflowException(msg)

        # Workflow result should be accepted by parent workflows (if any)
        # only if it completed successfully or failed.
        self.wf_ex.accepted = states.is_completed(state)

        if states.is_completed(state):
            triggers.on_workflow_complete(self.wf_ex)

        return True

    @profiler.trace('workflow-check-and-complete')
    def check_and_complete(self):
        """Completes the workflow if it needs to be completed.

        The method simply checks if there are any tasks that are not
        in a terminal state. If there aren't any then it performs all
        necessary logic to finalize the workflow (calculate output etc.).
        :return: Number of incomplete tasks.
        """

        if states.is_paused_or_completed(self.wf_ex.state):
            return 0
        wf_ctrl = wf_base.get_controller(self.wf_ex, self.wf_spec)
        if (states.is_planned(self.wf_ex.state) and
                not wf_ctrl._is_marked_cancelled()):
            return 0

        # Workflow is not completed if there are any incomplete task
        # executions.
        incomplete_tasks_count = db_api.get_incomplete_task_executions_count(
            workflow_execution_id=self.wf_ex.id,
        )

        if incomplete_tasks_count > 0:
            return incomplete_tasks_count

        LOG.debug("Workflow completed [id=%s]", self.wf_ex.id)

        # NOTE(rakhmerov): Once we know that the workflow has completed,
        # we need to expire all the objects in the DB session to make sure
        # to read the most relevant data from the DB (that's already been
        # committed in parallel transactions). Otherwise, some data like
        # workflow context may be stale and decisions made upon it will be
        # wrong.
        db_api.expire_all()

        if wf_ctrl.any_cancels():
            final_context = wf_ctrl.evaluate_workflow_final_context()

            self._cancel_workflow(
                final_context,
                msg=_build_cancel_info_message(wf_ctrl, self.wf_ex)
            )
        elif wf_ctrl._is_marked_cancelled():
            final_context = wf_ctrl.evaluate_workflow_final_context()

            self._cancel_workflow(final_context)
        elif wf_ctrl.all_errors_handled():
            ctx = wf_ctrl.evaluate_workflow_final_context()

            self._succeed_workflow(ctx)
        else:
            if self.wf_ex.params.get('terminate_to_error'):
                msg = "Workflow was terminated to error."
            else:
                msg = _build_fail_info_message(wf_ctrl, self.wf_ex)
            final_context = wf_ctrl.evaluate_workflow_final_context()

            self._fail_workflow(final_context, msg)

        return 0

    def plan(self, wf_def, wf_ex_id, input_dict,
             desc, params):
        """Create workflow execution in planned state.

        The method set wf_spec to Workflow obj and creates
        workflow execution with planned state in database.
        """
        # New workflow execution.
        self.wf_spec = spec_parser.get_workflow_spec_by_definition_id(
            wf_def.id,
            wf_def.updated_at
        )
        self.validate_input(input_dict)
        self._create_execution(
            wf_def,
            wf_ex_id,
            self.prepare_input(input_dict),
            desc,
            params
        )
        self.set_state(states.PLANNED)

    def _succeed_workflow(self, final_context, msg=None):
        output = data_flow.evaluate_workflow_output(
            self.wf_ex,
            self.wf_spec.get_output(),
            final_context
        )

        # Set workflow execution to success after output is evaluated.
        if not self.set_state(states.SUCCESS, msg):
            return
        self.wf_ex.params['read_only'] = True

        self.wf_ex.output = output

        if self.wf_ex.task_execution_id:
            self._send_result_to_parent_workflow()

    def _fail_workflow(self, final_context, msg):
        if states.is_paused_or_completed(self.wf_ex.state):
            return

        output_on_error = {}

        try:
            output_on_error = data_flow.evaluate_workflow_output(
                self.wf_ex,
                self.wf_spec.get_output_on_error(),
                final_context
            )
        except exc.MistralException as e:
            msg = (
                "Failed to evaluate expression in output-on-error! "
                "(output-on-error: '%s', exception: '%s' Cause: '%s'"
                % (self.wf_spec.get_output_on_error(), e, msg)
            )
            LOG.error(msg)

        if not self.set_state(states.ERROR, state_info=msg):
            return

        # When we set an ERROR state we should safely set output value getting
        # w/o exceptions due to field size limitations.

        length_output_on_error = len(str(output_on_error).encode("utf-8"))
        total_output_length = utils.get_number_of_chars_from_kilobytes(
            cfg.CONF.engine.execution_field_size_limit_kb)

        if length_output_on_error < total_output_length:
            msg = utils.cut_by_char(
                msg,
                total_output_length - length_output_on_error
            )
        else:
            msg = utils.cut_by_kb(
                msg,
                cfg.CONF.engine.execution_field_size_limit_kb
            )

        self.wf_ex.output = utils.merge_dicts({'result': msg}, output_on_error)

        if self.wf_ex.task_execution_id:
            self._send_result_to_parent_workflow()

    def _mark_workflow_cancelled(self, msg=None):
        if states.is_completed(self.wf_ex.state):
            return

        self.wf_ex.params['cancelled'] = True

        if states.is_paused(self.wf_ex.state):
            wf_ctrl = wf_base.get_controller(self.wf_ex, self.wf_spec)
            final_context = wf_ctrl.evaluate_workflow_final_context()
            self._cancel_workflow(final_context, msg)

    def _cancel_workflow(self, final_context, msg=None, force=False):
        if states.is_completed(self.wf_ex.state) and not force:
            return

        msg = "Workflow was cancelled." if not msg else msg

        if not self.set_state(states.CANCELLED, state_info=msg):
            return
        self.wf_ex.params['read_only'] = True

        self.wf_ex.output = data_flow.evaluate_workflow_output(
            self.wf_ex,
            {},
            final_context
        )

        if force:
            if self.wf_ex.params.get('force_cancelled', False):
                return
            self.wf_ex.params['force_cancelled'] = True
            tasks_ex = db_api.get_incomplete_task_executions(
                workflow_execution_id=self.wf_ex.id
            )

            from mistral.engine import action_handler as a_h
            from mistral.engine import task_handler as t_h

            for task_ex in tasks_ex:
                task = t_h.build_task_from_execution(self.wf_spec, task_ex)
                task.set_state(states.ERROR, 'Task was failed due '
                               'to workflow force cancel.')
                a_h.cancel_incomplete_actions(task_ex.id)

        if self.wf_ex.task_execution_id:
            self._send_result_to_parent_workflow()

    def _send_result_to_parent_workflow(self):
        if self.wf_ex.state == states.SUCCESS:
            # The result of the sub workflow is already saved
            # so there's no need to send it over RPC.
            result = None
        elif self.wf_ex.state == states.ERROR:
            err_msg = (
                self.wf_ex.state_info or
                'Failed subworkflow [execution_id=%s]' % self.wf_ex.id
            )

            result = ml_actions.Result(error=err_msg)
        elif self.wf_ex.state == states.CANCELLED:
            err_msg = (
                self.wf_ex.state_info or
                'Cancelled subworkflow [execution_id=%s]' % self.wf_ex.id
            )

            result = ml_actions.Result(error=err_msg, cancel=True)
        else:
            raise RuntimeError(
                "Method _send_result_to_parent_workflow() must never be called"
                " if a workflow is not in SUCCESS, ERROR or CANCELLED state."
            )

        # Register a command executed in a separate thread to send the result
        # to the parent workflow outside of the main DB transaction.
        def _send_result():
            rpc.get_engine_client().on_action_complete(
                self.wf_ex.id,
                result,
                wf_action=True
            )

        post_tx_queue.register_operation(_send_result)


def _get_environment(params):
    env = params.get('env', {})

    if not env:
        return {}

    if isinstance(env, dict):
        env_dict = env
    elif isinstance(env, str):
        env_db = db_api.load_environment(env)

        if not env_db:
            raise exc.InputException(
                'Environment is not found: %s' % env
            )

        env_dict = env_db.variables
    else:
        raise exc.InputException(
            'Unexpected value type for environment [env=%s, type=%s]'
            % (env, type(env))
        )

    if ('evaluate_env' in params and
            not params['evaluate_env']):
        return env_dict
    else:
        return expr.evaluate_recursively(env_dict, {'__env': env_dict})


def _build_fail_info_message(wf_ctrl, wf_ex):
    # Try to find where error is exactly.
    failed_tasks = [
        t_ex for t_ex in db_api.get_task_executions(
            workflow_execution_id=wf_ex.id,
            state=states.ERROR,
            sort_keys=['name']
        ) if not wf_ctrl.is_error_handled_for(t_ex)
    ]

    msg = ('Failure caused by error in tasks: %s\n' %
           ', '.join([t.name for t in failed_tasks]))

    for t in failed_tasks:
        msg += '\n  %s [task_ex_id=%s] -> %s\n' % (t.name, t.id, t.state_info)

        for i, ex in enumerate(t.action_executions):
            if ex.state == states.ERROR:
                output = (ex.output or dict()).get('result', 'Unknown')
                msg += (
                    '    [action_ex_id=%s, idx=%s]: %s\n' % (
                        ex.id,
                        i,
                        str(output)
                    )
                )

        for i, ex in enumerate(t.workflow_executions):
            if ex.state == states.ERROR:
                output = (ex.output or dict()).get('result', 'Unknown')
                msg += (
                    '    [wf_ex_id=%s, idx=%s]: %s\n' % (
                        ex.id,
                        i,
                        str(output)
                    )
                )

    return msg


def _build_cancel_info_message(wf_ctrl, wf_ex):
    # Try to find where cancel is exactly.
    cancelled_tasks = [
        t_ex for t_ex in db_api.get_task_executions(
            workflow_execution_id=wf_ex.id,
            state=states.CANCELLED,
            sort_keys=['name']
        )
    ]

    return (
        'Cancelled tasks: %s' % ', '.join([t.name for t in cancelled_tasks])
    )
