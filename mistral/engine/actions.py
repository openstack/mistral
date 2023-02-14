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

from mistral.db.v2 import api as db_api
from mistral.engine import post_tx_queue
from mistral.engine import utils as engine_utils
from mistral.engine import workflow_handler as wf_handler
from mistral import exceptions as exc
from mistral.executors import base as exe
from mistral.lang import parser as spec_parser
from mistral.rpc import clients as rpc
from mistral.services import security
from mistral.utils import wf_trace
from mistral.workflow import data_flow
from mistral.workflow import states
from mistral_lib import utils


LOG = logging.getLogger(__name__)
CONF = cfg.CONF


class Action(object, metaclass=abc.ABCMeta):
    """Action.

    Represents a workflow action and defines interface that can be used by
    Mistral engine or its components in order to manipulate with actions.
    """

    def __init__(self, action_desc, action_ex=None, task_ex=None,
                 task_ctx=None):
        self.action_desc = action_desc
        self.action_ex = action_ex
        self.namespace = action_desc.namespace if action_desc else None
        self.task_ex = action_ex.task_execution if action_ex else task_ex
        self.task_ctx = task_ctx

    @abc.abstractmethod
    def complete(self, result):
        """Complete action and process its result.

        :param result: Action result.
        """
        raise NotImplementedError

    def fail(self, msg):
        assert self.action_ex

        # When we set an ERROR state we should safely set output value getting
        # w/o exceptions due to field size limitations.
        msg = utils.cut_by_kb(
            msg,
            cfg.CONF.engine.execution_field_size_limit_kb
        )

        self.action_ex.state = states.ERROR
        self.action_ex.output = {'result': msg}

    def update(self, state):
        assert self.action_ex

        # TODO(rakhmerov): Not sure we can do it for all actions.
        action = self.action_desc.instantiate(self.action_ex.input, {})

        if state == states.PAUSED and action.is_sync():
            raise exc.InvalidStateTransitionException(
                'Transition to the PAUSED state is only supported '
                'for asynchronous action execution.'
            )

        if not states.is_valid_transition(self.action_ex.state, state):
            raise exc.InvalidStateTransitionException(
                'Invalid state transition from %s to %s.' %
                (self.action_ex.state, state)
            )

        self.action_ex.state = state

    @abc.abstractmethod
    def schedule(self, input_dict, target, index=0, desc='', safe_rerun=False,
                 timeout=None):
        """Schedule action run.

        This method is needed to schedule action run so its result can
        be received later by engine. In this sense it will be running in
        asynchronous mode from engine perspective (don't confuse with
        executor asynchrony when executor doesn't immediately send a
        result).

        :param timeout: a period of time in seconds after which execution of
            action will be interrupted
        :param input_dict: Action input.
        :param target: Target (group of action executors).
        :param index: Action execution index. Makes sense for some types.
        :param desc: Action execution description.
        :param safe_rerun: If true, action would be re-run if executor dies
            during execution.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def run(self, input_dict, target, index=0, desc='', save=True,
            safe_rerun=False, timeout=None):
        """Immediately run action.

        This method runs method w/o scheduling its run for a later time.
        From engine perspective action will be processed in synchronous
        mode.

        :param timeout: a period of time in seconds after which execution of
            action will be interrupted
        :param input_dict: Action input.
        :param target: Target (group of action executors).
        :param index: Action execution index. Makes sense for some types.
        :param desc: Action execution description.
        :param save: True if action execution object needs to be saved.
        :param safe_rerun: If true, action would be re-run if executor dies
            during execution.
        :return: Action output.
        """
        raise NotImplementedError

    def _prepare_execution_context(self):
        res = {}

        if self.task_ex:
            wf_ex = self.task_ex.workflow_execution

            res['workflow_execution_id'] = wf_ex.id
            res['task_execution_id'] = self.task_ex.id
            res['workflow_name'] = wf_ex.name

        if self.action_ex:
            res['action_execution_id'] = self.action_ex.id
            res['callback_url'] = (
                '/v2/action_executions/%s' % self.action_ex.id
            )

        return res

    def _create_action_execution(self, input_dict, runtime_ctx,
                                 desc='', action_ex_id=None, is_sync=True):
        action_ex_id = action_ex_id or utils.generate_unicode_uuid()

        values = {
            'id': action_ex_id,
            'name': self.action_desc.name,
            'state': states.RUNNING,
            'input': input_dict,
            'runtime_context': runtime_ctx,
            'workflow_namespace': self.namespace,
            'description': desc,
            'is_sync': is_sync
        }

        if self.task_ex:
            values.update({
                'task_execution_id': self.task_ex.id,
                'workflow_name': self.task_ex.workflow_name,
                'workflow_namespace': self.task_ex.workflow_namespace,
                'workflow_id': self.task_ex.workflow_id,
                'project_id': self.task_ex.project_id,
            })
        else:
            values.update({
                'project_id': security.get_project_id(),
            })

        LOG.info("Create action execution [action_name=%s, action_ex_id=%s]",
                 self.action_desc.name, action_ex_id)

        self.action_ex = db_api.create_action_execution(values)

        if self.task_ex:
            # Add to collection explicitly so that it's in a proper
            # state within the current session.
            self.task_ex.action_executions.append(self.action_ex)

    @profiler.trace('action-log-result', hide_args=True)
    def _log_result(self, prev_state, result):
        state = self.action_ex.state

        if prev_state != state:
            wf_trace.info(
                None,
                "Action '%s' (%s)(task_name=%s, "
                "task_ex_id=%s) [%s -> %s, %s]" %
                (self.action_ex.name,
                 self.action_ex.id,
                 self.task_ex.name if self.task_ex else None,
                 self.task_ex.id if self.task_ex else None,
                 prev_state,
                 state,
                 result.cut_repr())
            )


class RegularAction(Action):
    """Regular Python action."""

    @profiler.trace('regular-action-complete', hide_args=True)
    def complete(self, result):
        assert self.action_ex

        if states.is_completed(self.action_ex.state):
            raise ValueError(
                "Action {} is already completed".format(self.action_ex.id)
            )

        prev_state = self.action_ex.state

        if result.is_success():
            self.action_ex.state = states.SUCCESS
        elif result.is_cancel():
            self.action_ex.state = states.CANCELLED
        else:
            self.action_ex.state = states.ERROR

        # Convert the result, if needed.
        converted_result = self.action_desc.post_process_result(result)

        self.action_ex.output = converted_result.to_dict()
        self.action_ex.accepted = True

        self._log_result(prev_state, result)

    @profiler.trace('action-schedule', hide_args=True)
    def schedule(self, input_dict, target, index=0, desc='', safe_rerun=False,
                 timeout=None):
        assert not self.action_ex

        self.action_desc.check_parameters(input_dict)

        wf_ex = self.task_ex.workflow_execution if self.task_ex else None

        wf_ctx = data_flow.ContextView(
            self.task_ctx,
            data_flow.get_workflow_environment_dict(wf_ex),
            wf_ex.context if wf_ex else {}
        )

        try:
            action = self.action_desc.instantiate(input_dict, wf_ctx)
        except Exception:
            raise exc.InvalidActionException(
                'Failed to instantiate an action'
                ' [action_desc=%s, input_dict=%s]'
                % (self.action_desc, input_dict)
            )

        # Assign the action execution ID here to minimize database calls.
        # Otherwise, the input property of the action execution DB object needs
        # to be updated with the action execution ID after the action execution
        # DB object is created.
        action_ex_id = utils.generate_unicode_uuid()

        self._create_action_execution(
            input_dict,
            self._prepare_runtime_context(index, safe_rerun),
            desc=desc,
            action_ex_id=action_ex_id,
            is_sync=action.is_sync()
        )

        def _run_action():
            executor = exe.get_executor(cfg.CONF.executor.type)

            return executor.run_action(
                action,
                self.action_ex.id if self.action_ex is not None else None,
                safe_rerun,
                self._prepare_execution_context(),
                target=target,
                timeout=timeout
            )

        # Register an asynchronous command to run the action
        # on an executor outside of the main DB transaction.
        post_tx_queue.register_operation(_run_action)

    @profiler.trace('action-run', hide_args=True)
    def run(self, input_dict, target, index=0, desc='', save=True,
            safe_rerun=False, timeout=None):
        assert not self.action_ex

        self.action_desc.check_parameters(input_dict)

        try:
            action = self.action_desc.instantiate(input_dict, {})
        except Exception:
            raise exc.InvalidActionException(
                'Failed to instantiate an action'
                ' [action_desc=%s, input_dict=%s]'
                % (self.action_desc, input_dict)
            )

        # Assign the action execution ID here to minimize database calls.
        # Otherwise, the input property of the action execution DB object needs
        # to be updated with the action execution ID after the action execution
        # DB object is created.
        action_ex_id = utils.generate_unicode_uuid()

        if save:
            self._create_action_execution(
                input_dict,
                self._prepare_runtime_context(index, safe_rerun),
                desc=desc,
                action_ex_id=action_ex_id,
                is_sync=action.is_sync()
            )

        executor = exe.get_executor(cfg.CONF.executor.type)

        return executor.run_action(
            action,
            self.action_ex.id if self.action_ex is not None else None,
            safe_rerun,
            self._prepare_execution_context(),
            target=target,
            async_=False,
            timeout=timeout
        )

    def _prepare_runtime_context(self, index, safe_rerun):
        """Template method to prepare action runtime context.

        Regular action inserts an index into its runtime context and
        the flag showing if the action is safe to rerun (i.e. it's
        idempotent).
        """
        return {'index': index, 'safe_rerun': safe_rerun}


class WorkflowAction(Action):
    """Workflow action."""

    def __init__(self, wf_name, **kwargs):
        super(WorkflowAction, self).__init__(None, **kwargs)

        self.wf_name = wf_name

    @profiler.trace('workflow-action-complete', hide_args=True)
    def complete(self, result):
        # No-op because in case of workflow result is already processed.
        pass

    @profiler.trace('workflow-action-schedule', hide_args=True)
    def schedule(self, input_dict, target, index=0, desc='', safe_rerun=False,
                 timeout=None):
        assert not self.action_ex

        self.validate_input(input_dict)

        parent_wf_ex = self.task_ex.workflow_execution
        parent_wf_spec = spec_parser.get_workflow_spec_by_execution_id(
            parent_wf_ex.id
        )

        wf_def = engine_utils.resolve_workflow_definition(
            parent_wf_ex.workflow_name,
            parent_wf_spec.get_name(),
            namespace=parent_wf_ex.params['namespace'],
            wf_spec_name=self.wf_name
        )

        wf_spec = spec_parser.get_workflow_spec_by_definition_id(
            wf_def.id,
            wf_def.updated_at
        )

        # If the parent has a root_execution_id, it must be a sub-workflow. So
        # we should propagate that ID down. Otherwise the parent must be the
        # root execution and we should use the parents ID.
        root_execution_id = parent_wf_ex.root_execution_id or parent_wf_ex.id

        wf_params = {
            'root_execution_id': root_execution_id,
            'task_execution_id': self.task_ex.id,
            'index': index,
            'namespace': parent_wf_ex.params['namespace']
        }

        if 'notify' in parent_wf_ex.params:
            wf_params['notify'] = parent_wf_ex.params['notify']

        for k, v in list(input_dict.items()):
            if k not in wf_spec.get_input():
                wf_params[k] = v
                del input_dict[k]

        if cfg.CONF.engine.start_subworkflows_via_rpc:
            def _start_subworkflow():
                rpc.get_engine_client().start_workflow(
                    wf_def.id,
                    wf_def.namespace,
                    None,
                    input_dict,
                    "sub-workflow execution",
                    async_=True,
                    **wf_params
                )

            post_tx_queue.register_operation(_start_subworkflow)
        else:
            wf_handler.start_workflow(
                wf_def.id,
                wf_def.namespace,
                None,
                input_dict,
                "sub-workflow execution",
                wf_params
            )

    @profiler.trace('workflow-action-run', hide_args=True)
    def run(self, input_dict, target, index=0, desc='', save=True,
            safe_rerun=True, timeout=None):
        raise NotImplementedError('Does not apply to this WorkflowAction.')

    def validate_input(self, input_dict):
        # TODO(rakhmerov): Implement.
        pass
