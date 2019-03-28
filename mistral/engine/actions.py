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
from mistral.engine import post_tx_queue
from mistral.engine import utils as engine_utils
from mistral.engine import workflow_handler as wf_handler
from mistral import exceptions as exc
from mistral.executors import base as exe
from mistral import expressions as expr
from mistral.lang import parser as spec_parser
from mistral.services import action_manager as a_m
from mistral.services import security
from mistral import utils
from mistral.utils import wf_trace
from mistral.workflow import data_flow
from mistral.workflow import lookup_utils
from mistral.workflow import states
from mistral_lib import actions as ml_actions


LOG = logging.getLogger(__name__)


@six.add_metaclass(abc.ABCMeta)
class Action(object):
    """Action.

    Represents a workflow action and defines interface that can be used by
    Mistral engine or its components in order to manipulate with actions.
    """

    def __init__(self, action_def, action_ex=None, task_ex=None):
        self.action_def = action_def
        self.action_ex = action_ex
        self.task_ex = action_ex.task_execution if action_ex else task_ex

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

        if state == states.PAUSED and self.is_sync(self.action_ex.input):
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

    def validate_input(self, input_dict):
        """Validates action input parameters.

        :param input_dict: Dictionary with input parameters.
        """
        raise NotImplementedError

    def is_sync(self, input_dict):
        """Determines if action is synchronous.

        :param input_dict: Dictionary with input parameters.
        """
        return True

    def _create_action_execution(self, input_dict, runtime_ctx, is_sync,
                                 desc='', action_ex_id=None):
        action_ex_id = action_ex_id or utils.generate_unicode_uuid()

        values = {
            'id': action_ex_id,
            'name': self.action_def.name,
            'spec': self.action_def.spec,
            'state': states.RUNNING,
            'input': input_dict,
            'runtime_context': runtime_ctx,
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

        self.action_ex = db_api.create_action_execution(values)

        if self.task_ex:
            # Add to collection explicitly so that it's in a proper
            # state within the current session.
            self.task_ex.action_executions.append(self.action_ex)

    @profiler.trace('action-log-result', hide_args=True)
    def _log_result(self, prev_state, result):
        state = self.action_ex.state

        def _result_msg():
            if state == states.ERROR:
                return "error = %s" % utils.cut(result.error)

            return "result = %s" % utils.cut(result.data)

        if prev_state != state:
            wf_trace.info(
                None,
                "Action '%s' (%s)(task=%s) [%s -> %s, %s]" %
                (self.action_ex.name,
                 self.action_ex.id,
                 self.task_ex.name if self.task_ex else None,
                 prev_state,
                 state,
                 _result_msg())
            )


class PythonAction(Action):
    """Regular Python action."""

    def __init__(self, action_def, action_ex=None, task_ex=None):
        super(PythonAction, self).__init__(action_def, action_ex, task_ex)

        self._prepared_input = None

    @profiler.trace('action-complete', hide_args=True)
    def complete(self, result):
        assert self.action_ex

        if states.is_completed(self.action_ex.state):
            raise ValueError(
                "Action {} is already completed".format(self.action_ex.id))

        prev_state = self.action_ex.state

        if result.is_success():
            self.action_ex.state = states.SUCCESS
        elif result.is_cancel():
            self.action_ex.state = states.CANCELLED
        else:
            self.action_ex.state = states.ERROR

        self.action_ex.output = self._prepare_output(result).to_dict()
        self.action_ex.accepted = True

        self._log_result(prev_state, result)

    @profiler.trace('action-schedule', hide_args=True)
    def schedule(self, input_dict, target, index=0, desc='', safe_rerun=False,
                 timeout=None):
        assert not self.action_ex

        self.validate_input(input_dict)

        # Assign the action execution ID here to minimize database calls.
        # Otherwise, the input property of the action execution DB object needs
        # to be updated with the action execution ID after the action execution
        # DB object is created.
        action_ex_id = utils.generate_unicode_uuid()

        self._create_action_execution(
            self._prepare_input(input_dict),
            self._prepare_runtime_context(index, safe_rerun),
            self.is_sync(input_dict),
            desc=desc,
            action_ex_id=action_ex_id
        )

        execution_context = self._prepare_execution_context()

        # Register an asynchronous command to send the action to
        # run on an executor outside of the main DB transaction.
        def _run_action():
            executor = exe.get_executor(cfg.CONF.executor.type)

            executor.run_action(
                self.action_ex.id,
                self.action_def.action_class,
                self.action_def.attributes or {},
                self.action_ex.input,
                self.action_ex.runtime_context.get('safe_rerun', False),
                execution_context,
                target=target,
                timeout=timeout
            )

        post_tx_queue.register_operation(_run_action)

    @profiler.trace('action-run', hide_args=True)
    def run(self, input_dict, target, index=0, desc='', save=True,
            safe_rerun=False, timeout=None):
        assert not self.action_ex

        self.validate_input(input_dict)

        prepared_input_dict = self._prepare_input(input_dict)

        # Assign the action execution ID here to minimize database calls.
        # Otherwise, the input property of the action execution DB object needs
        # to be updated with the action execution ID after the action execution
        # DB object is created.
        action_ex_id = utils.generate_unicode_uuid()

        if save:
            self._create_action_execution(
                prepared_input_dict,
                self._prepare_runtime_context(index, safe_rerun),
                self.is_sync(input_dict),
                desc=desc,
                action_ex_id=action_ex_id
            )

        executor = exe.get_executor(cfg.CONF.executor.type)

        execution_context = self._prepare_execution_context()

        result = executor.run_action(
            self.action_ex.id if self.action_ex else None,
            self.action_def.action_class,
            self.action_def.attributes or {},
            prepared_input_dict,
            safe_rerun,
            execution_context,
            target=target,
            async_=False,
            timeout=timeout
        )

        return self._prepare_output(result)

    def is_sync(self, input_dict):
        prepared_input_dict = self._prepare_input(input_dict)

        a = a_m.get_action_class(self.action_def.name)(**prepared_input_dict)

        return a.is_sync()

    def validate_input(self, input_dict):
        # NOTE(kong): Don't validate action input if action initialization
        # method contains ** argument.
        if '**' in self.action_def.input:
            return

        expected_input = utils.get_dict_from_string(self.action_def.input)

        engine_utils.validate_input(
            expected_input,
            input_dict,
            self.action_def.name,
            self.action_def.action_class
        )

    def _prepare_execution_context(self):
        exc_ctx = {}

        if self.task_ex:
            wf_ex = self.task_ex.workflow_execution

            exc_ctx['workflow_execution_id'] = wf_ex.id
            exc_ctx['task_execution_id'] = self.task_ex.id
            exc_ctx['workflow_name'] = wf_ex.name

        if self.action_ex:
            exc_ctx['action_execution_id'] = self.action_ex.id
            exc_ctx['callback_url'] = (
                '/v2/action_executions/%s' % self.action_ex.id
            )

        return exc_ctx

    def _prepare_input(self, input_dict):
        """Template method to do manipulations with input parameters.

        Python action doesn't do anything specific with initial input.
        """
        return input_dict

    def _prepare_output(self, result):
        """Template method to do manipulations with action result.

        Python action doesn't do anything specific with result.
        """
        return result

    def _prepare_runtime_context(self, index, safe_rerun):
        """Template method to prepare action runtime context.

        Python action inserts index into runtime context and information if
        given action is safe_rerun.
        """
        return {'index': index, 'safe_rerun': safe_rerun}


class AdHocAction(PythonAction):
    """Ad-hoc action."""

    @profiler.trace('ad-hoc-action-init', hide_args=True)
    def __init__(self, action_def, action_ex=None, task_ex=None, task_ctx=None,
                 wf_ctx=None):
        self.action_spec = spec_parser.get_action_spec(action_def.spec)

        base_action_def = lookup_utils.find_action_definition_by_name(
            self.action_spec.get_base()
        )

        if not base_action_def:
            raise exc.InvalidActionException(
                "Failed to find action [action_name=%s]" %
                self.action_spec.get_base()
            )

        base_action_def = self._gather_base_actions(
            action_def,
            base_action_def
        )

        super(AdHocAction, self).__init__(
            base_action_def,
            action_ex,
            task_ex
        )

        self.adhoc_action_def = action_def
        self.task_ctx = task_ctx or {}
        self.wf_ctx = wf_ctx or {}

    @profiler.trace('ad-hoc-action-validate-input', hide_args=True)
    def validate_input(self, input_dict):
        expected_input = self.action_spec.get_input()

        engine_utils.validate_input(
            expected_input,
            input_dict,
            self.adhoc_action_def.name,
            self.action_spec.__class__.__name__
        )

        super(AdHocAction, self).validate_input(
            self._prepare_input(input_dict)
        )

    @profiler.trace('ad-hoc-action-prepare-input', hide_args=True)
    def _prepare_input(self, input_dict):
        if self._prepared_input is not None:
            return self._prepared_input

        base_input_dict = input_dict

        for action_def in self.adhoc_action_defs:
            action_spec = spec_parser.get_action_spec(action_def.spec)

            for k, v in action_spec.get_input().items():
                if (k not in base_input_dict or
                        base_input_dict[k] is utils.NotDefined):
                    base_input_dict[k] = v

            base_input_expr = action_spec.get_base_input()

            if base_input_expr:
                wf_ex = (
                    self.task_ex.workflow_execution if self.task_ex else None
                )

                ctx_view = data_flow.ContextView(
                    base_input_dict,
                    self.task_ctx,
                    data_flow.get_workflow_environment_dict(wf_ex),
                    self.wf_ctx
                )

                base_input_dict = expr.evaluate_recursively(
                    base_input_expr,
                    ctx_view
                )
            else:
                base_input_dict = {}

        self._prepared_input = super(AdHocAction, self)._prepare_input(
            base_input_dict
        )

        return self._prepared_input

    @profiler.trace('ad-hoc-action-prepare-output', hide_args=True)
    def _prepare_output(self, result):
        # In case of error, we don't transform a result.
        if not result.is_error():
            for action_def in reversed(self.adhoc_action_defs):
                adhoc_action_spec = spec_parser.get_action_spec(
                    action_def.spec
                )

                transformer = adhoc_action_spec.get_output()

                if transformer is not None:
                    result = ml_actions.Result(
                        data=expr.evaluate_recursively(
                            transformer,
                            result.data
                        ),
                        error=result.error
                    )

        return result

    @profiler.trace('ad-hoc-action-prepare-runtime-context', hide_args=True)
    def _prepare_runtime_context(self, index, safe_rerun):
        ctx = super(AdHocAction, self)._prepare_runtime_context(
            index,
            safe_rerun
        )

        # Insert special field into runtime context so that we track
        # a relationship between python action and adhoc action.
        return utils.merge_dicts(
            ctx,
            {'adhoc_action_name': self.adhoc_action_def.name}
        )

    @profiler.trace('ad-hoc-action-gather-base-actions', hide_args=True)
    def _gather_base_actions(self, action_def, base_action_def):
        """Find all base ad-hoc actions and store them

        An ad-hoc action may be based on another ad-hoc action (and this
        recursively). Using twice the same base action is not allowed to
        avoid infinite loops. It stores the list of ad-hoc actions.

        :param action_def: Action definition
        :type action_def: ActionDefinition
        :param base_action_def: Original base action definition
        :type base_action_def: ActionDefinition
        :return: The definition of the base system action
        :rtype: ActionDefinition
        """

        self.adhoc_action_defs = [action_def]
        original_base_name = self.action_spec.get_name()
        action_names = set([original_base_name])

        base = base_action_def

        while not base.is_system and base.name not in action_names:
            action_names.add(base.name)
            self.adhoc_action_defs.append(base)

            base_name = base.spec['base']
            try:
                base = db_api.get_action_definition(base_name)
            except exc.DBEntityNotFoundError:
                raise exc.InvalidActionException(
                    "Failed to find action [action_name=%s]" % base_name
                )

        # if the action is repeated
        if base.name in action_names:
            raise ValueError(
                'An ad-hoc action cannot use twice the same action, %s is '
                'used at least twice' % base.name
            )

        return base


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

    def is_sync(self, input_dict):
        # Workflow action is always asynchronous.
        return False

    def validate_input(self, input_dict):
        # TODO(rakhmerov): Implement.
        pass


def resolve_action_definition(action_spec_name, wf_name=None,
                              wf_spec_name=None):
    """Resolve action definition accounting for ad-hoc action namespacing.

    :param action_spec_name: Action name according to a spec.
    :param wf_name: Workflow name.
    :param wf_spec_name: Workflow name according to a spec.
    :return: Action definition (python or ad-hoc).
    """

    action_db = None

    if wf_name and wf_name != wf_spec_name:
        # If workflow belongs to a workbook then check
        # action within the same workbook (to be able to
        # use short names within workbooks).
        # If it doesn't exist then use a name from spec
        # to find an action in DB.
        wb_name = wf_name.rstrip(wf_spec_name)[:-1]

        action_full_name = "%s.%s" % (wb_name, action_spec_name)

        action_db = lookup_utils.find_action_definition_by_name(
            action_full_name
        )

    if not action_db:
        action_db = lookup_utils.find_action_definition_by_name(
            action_spec_name
        )

    if not action_db:
        raise exc.InvalidActionException(
            "Failed to find action [action_name=%s]" % action_spec_name
        )

    return action_db
