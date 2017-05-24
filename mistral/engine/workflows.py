# Copyright 2016 - Nokia Networks.
# Copyright 2016 - Brocade Communications Systems, Inc.
# Copyright 2018 - Extreme Networks, Inc.
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
from oslo_config import cfg
from oslo_log import log as logging
from osprofiler import profiler
import six

from mistral.db.v2 import api as db_api
from mistral.db.v2.sqlalchemy import models as db_models
from mistral.engine import action_queue
from mistral.engine import dispatcher
from mistral.engine import utils as engine_utils
from mistral import exceptions as exc
from mistral.lang import parser as spec_parser
from mistral.notifiers import base as notif
from mistral.notifiers import notification_events as events
from mistral.services import triggers
from mistral.services import workflows as wf_service
from mistral import utils
from mistral.utils import merge_dicts
from mistral.utils import wf_trace
from mistral.workflow import base as wf_base
from mistral.workflow import commands
from mistral.workflow import data_flow
from mistral.workflow import lookup_utils
from mistral.workflow import states
from mistral_lib import actions as ml_actions


LOG = logging.getLogger(__name__)


@six.add_metaclass(abc.ABCMeta)
class Workflow(object):
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

    def notify(self, event):
        publishers = self.wf_ex.params.get('notify')

        if not publishers and not isinstance(publishers, list):
            return

        notifier = notif.get_notifier(cfg.CONF.notifier.type)

        notifier.notify(
            self.wf_ex.id,
            self.wf_ex.to_dict(),
            event,
            self.wf_ex.updated_at,
            publishers
        )

    @profiler.trace('workflow-start')
    def start(self, wf_def, wf_ex_id, input_dict, desc='', params=None):
        """Start workflow.

        :param wf_def: Workflow definition.
        :param wf_ex_id: Workflow execution id.
        :param input_dict: Workflow input.
        :param desc: Workflow execution description.
        :param params: Workflow type specific parameters.

        :raises
        """

        assert not self.wf_ex

        # New workflow execution.
        self.wf_spec = spec_parser.get_workflow_spec_by_definition_id(
            wf_def.id,
            wf_def.updated_at
        )

        wf_trace.info(
            self.wf_ex,
            'Starting workflow [name=%s, input=%s]' %
            (wf_def.name, utils.cut(input_dict))
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

        # Publish event as soon as state is set to running.
        self.notify(events.WORKFLOW_LAUNCHED)

        wf_ctrl = wf_base.get_controller(self.wf_ex, self.wf_spec)

        dispatcher.dispatch_workflow_commands(
            self.wf_ex,
            wf_ctrl.continue_workflow()
        )

    def stop(self, state, msg=None):
        """Stop workflow.

        :param state: New workflow state.
        :param msg: Additional explaining message.
        """
        assert self.wf_ex

        if state == states.SUCCESS:
            self._succeed_workflow(self._get_final_context(), msg)
        elif state == states.ERROR:
            self._fail_workflow(self._get_final_context(), msg)
        elif state == states.CANCELLED:
            self._cancel_workflow(msg)

    def pause(self, msg=None):
        """Pause workflow.

        :param msg: Additional explaining message.
        """

        assert self.wf_ex

        if states.is_paused(self.wf_ex.state):
            return

        # Set the state of this workflow to paused.
        self.set_state(states.PAUSED, state_info=msg)

        # Publish event.
        self.notify(events.WORKFLOW_PAUSED)

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

        # Publish event.
        self.notify(events.WORKFLOW_RESUMED)

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

    def rerun(self, task_ex, reset=True, env=None):
        """Rerun workflow from the given task.

        :param task_ex: Task execution that the workflow needs to rerun from.
        :param reset: If True, reset task state including deleting its action
            executions.
        :param env: Environment.
        """

        assert self.wf_ex

        # Since some lookup utils functions may use cache for completed tasks
        # we need to clean caches to make sure that stale objects can't be
        # retrieved.
        lookup_utils.clear_caches()

        wf_service.update_workflow_execution_env(self.wf_ex, env)

        self.set_state(states.RUNNING, recursive=True)

        wf_ctrl = wf_base.get_controller(self.wf_ex)

        # Calculate commands to process next.
        cmds = wf_ctrl.rerun_tasks([task_ex], reset=reset)

        self._continue_workflow(cmds)

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

        if cmds:
            dispatcher.dispatch_workflow_commands(self.wf_ex, cmds)
        else:
            self.check_and_complete()

    @profiler.trace('workflow-lock')
    def lock(self):
        assert self.wf_ex

        return db_api.acquire_lock(db_models.WorkflowExecution, self.wf_ex.id)

    def _get_final_context(self):
        wf_ctrl = wf_base.get_controller(self.wf_ex)
        final_context = {}
        try:
            final_context = wf_ctrl.evaluate_workflow_final_context()
        except Exception as e:
            LOG.warning(
                'Failed to get final context for workflow execution. '
                '[wf_ex_id: %s, wf_name: %s, error: %s]',
                self.wf_ex.id,
                self.wf_ex.name,
                str(e)
            )

        return final_context

    def _create_execution(self, wf_def, wf_ex_id, input_dict, desc, params):
        self.wf_ex = db_api.create_workflow_execution({
            'id': wf_ex_id,
            'name': wf_def.name,
            'description': desc,
            'workflow_name': wf_def.name,
            'workflow_namespace': wf_def.namespace,
            'workflow_id': wf_def.id,
            'spec': self.wf_spec.to_dict(),
            'state': states.IDLE,
            'output': {},
            'task_execution_id': params.get('task_execution_id'),
            'root_execution_id': params.get('root_execution_id'),
            'runtime_context': {
                'index': params.get('index', 0)
            },
        })

        self.wf_ex.input = input_dict or {}

        env = _get_environment(params)

        if env:
            params['env'] = env

        self.wf_ex.params = params

        data_flow.add_openstack_data_to_context(self.wf_ex)
        data_flow.add_execution_to_context(self.wf_ex)
        data_flow.add_environment_to_context(self.wf_ex)
        data_flow.add_workflow_variables_to_context(self.wf_ex, self.wf_spec)

        spec_parser.cache_workflow_spec_by_execution_id(
            self.wf_ex.id,
            self.wf_spec
        )

    @profiler.trace('workflow-set-state')
    def set_state(self, state, state_info=None, recursive=False):
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
                return

            self.wf_ex = wf_ex
            self.wf_ex.state_info = state_info

            wf_trace.info(
                self.wf_ex,
                "Workflow '%s' [%s -> %s, msg=%s]"
                % (self.wf_ex.workflow_name, cur_state, state, state_info)
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
            # No need to keep task executions of this workflow in the
            # lookup cache anymore.
            lookup_utils.invalidate_cached_task_executions(self.wf_ex.id)

            triggers.on_workflow_complete(self.wf_ex)

        if recursive and self.wf_ex.task_execution_id:
            parent_task_ex = db_api.get_task_execution(
                self.wf_ex.task_execution_id
            )

            parent_wf = Workflow(wf_ex=parent_task_ex.workflow_execution)

            parent_wf.lock()

            parent_wf.set_state(state, recursive=recursive)

            # TODO(rakhmerov): It'd be better to use instance of Task here.
            parent_task_ex.state = state
            parent_task_ex.state_info = None
            parent_task_ex.processed = False

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

        # Workflow is not completed if there are any incomplete task
        # executions.
        incomplete_tasks_count = db_api.get_incomplete_task_executions_count(
            workflow_execution_id=self.wf_ex.id,
        )

        if incomplete_tasks_count > 0:
            return incomplete_tasks_count

        wf_ctrl = wf_base.get_controller(self.wf_ex, self.wf_spec)

        if wf_ctrl.any_cancels():
            msg = _build_cancel_info_message(wf_ctrl, self.wf_ex)

            self._cancel_workflow(msg)
        elif wf_ctrl.all_errors_handled():
            ctx = wf_ctrl.evaluate_workflow_final_context()

            self._succeed_workflow(ctx)
        else:
            msg = _build_fail_info_message(wf_ctrl, self.wf_ex)
            final_context = wf_ctrl.evaluate_workflow_final_context()

            self._fail_workflow(final_context, msg)

        return 0

    def _succeed_workflow(self, final_context, msg=None):
        self.wf_ex.output = data_flow.evaluate_workflow_output(
            self.wf_ex,
            self.wf_spec.get_output(),
            final_context
        )

        # Set workflow execution to success until after output is evaluated.
        self.set_state(states.SUCCESS, msg)

        # Publish event.
        self.notify(events.WORKFLOW_SUCCEEDED)

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

        self.set_state(states.ERROR, state_info=msg)

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

        self.wf_ex.output = merge_dicts({'result': msg}, output_on_error)

        # Publish event.
        self.notify(events.WORKFLOW_FAILED)

        if self.wf_ex.task_execution_id:
            self._send_result_to_parent_workflow()

    def _cancel_workflow(self, msg):
        if states.is_completed(self.wf_ex.state):
            return

        self.set_state(states.CANCELLED, state_info=msg)

        # When we set an ERROR state we should safely set output value getting
        # w/o exceptions due to field size limitations.
        msg = utils.cut_by_kb(
            msg,
            cfg.CONF.engine.execution_field_size_limit_kb
        )

        self.wf_ex.output = {'result': msg}

        # Publish event.
        self.notify(events.WORKFLOW_CANCELLED)

        if self.wf_ex.task_execution_id:
            self._send_result_to_parent_workflow()

    def _send_result_to_parent_workflow(self):
        if self.wf_ex.state == states.SUCCESS:
            result = ml_actions.Result(data=self.wf_ex.output)
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

        action_queue.schedule_on_action_complete(
            self.wf_ex.id,
            result,
            wf_action=True
        )


def _get_environment(params):
    env = params.get('env', {})

    if isinstance(env, dict):
        return env

    if isinstance(env, six.string_types):
        env_db = db_api.load_environment(env)

        if not env_db:
            raise exc.InputException(
                'Environment is not found: %s' % env
            )

        return env_db.variables

    raise exc.InputException(
        'Unexpected value type for environment [env=%s, type=%s]'
        % (env, type(env))
    )


def _build_fail_info_message(wf_ctrl, wf_ex):
    # Try to find where error is exactly.
    failed_tasks = sorted(
        filter(
            lambda t: not wf_ctrl.is_error_handled_for(t),
            lookup_utils.find_error_task_executions(wf_ex.id)
        ),
        key=lambda t: t.name
    )

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
    cancelled_tasks = sorted(
        lookup_utils.find_cancelled_task_executions(wf_ex.id),
        key=lambda t: t.name
    )

    return (
        'Cancelled tasks: %s' % ', '.join([t.name for t in cancelled_tasks])
    )
