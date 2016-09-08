# Copyright 2016 - Nokia Networks.
# Copyright 2016 - Brocade Communications Systems, Inc.
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
from osprofiler import profiler
import six

from mistral.db.v2 import api as db_api
from mistral.engine.rpc_backend import rpc
from mistral.engine import utils as e_utils
from mistral.engine import workflow_handler as wf_handler
from mistral import exceptions as exc
from mistral import expressions as expr
from mistral.services import action_manager as a_m
from mistral.services import scheduler
from mistral.services import security
from mistral import utils
from mistral.utils import wf_trace
from mistral.workbook import parser as spec_parser
from mistral.workflow import states
from mistral.workflow import utils as wf_utils


_RUN_EXISTING_ACTION_PATH = 'mistral.engine.actions._run_existing_action'


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

    @abc.abstractmethod
    def schedule(self, input_dict, target, index=0, desc='', safe_rerun=False):
        """Schedule action run.

        This method is needed to schedule action run so its result can
        be received later by engine. In this sense it will be running in
        asynchronous mode from engine perspective (don't confuse with
        executor asynchrony when executor doesn't immediately send a
        result).

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
            safe_rerun=False):
        """Immediately run action.

        This method runs method w/o scheduling its run for a later time.
        From engine perspective action will be processed in synchronous
        mode.

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

    def _create_action_execution(self, input_dict, runtime_ctx,
                                 desc='', action_ex_id=None):
        action_ex_id = action_ex_id or utils.generate_unicode_uuid()

        values = {
            'id': action_ex_id,
            'name': self.action_def.name,
            'spec': self.action_def.spec,
            'state': states.RUNNING,
            'input': input_dict,
            'runtime_context': runtime_ctx,
            'description': desc
        }

        if self.task_ex:
            values.update({
                'task_execution_id': self.task_ex.id,
                'workflow_name': self.task_ex.workflow_name,
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

    def _inject_action_ctx_for_validating(self, input_dict):
        if a_m.has_action_context(
                self.action_def.action_class, self.action_def.attributes):
            input_dict.update(a_m.get_empty_action_context())

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

    @profiler.trace('action-complete')
    def complete(self, result):
        assert self.action_ex

        if states.is_completed(self.action_ex.state):
            return

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

    @profiler.trace('action-schedule')
    def schedule(self, input_dict, target, index=0, desc='', safe_rerun=False):
        assert not self.action_ex

        # Assign the action execution ID here to minimize database calls.
        # Otherwise, the input property of the action execution DB object needs
        # to be updated with the action execution ID after the action execution
        # DB object is created.
        action_ex_id = utils.generate_unicode_uuid()

        self._insert_action_context(action_ex_id, input_dict)

        self._create_action_execution(
            self._prepare_input(input_dict),
            self._prepare_runtime_context(index, safe_rerun),
            desc=desc,
            action_ex_id=action_ex_id
        )

        scheduler.schedule_call(
            None,
            _RUN_EXISTING_ACTION_PATH,
            0,
            action_ex_id=self.action_ex.id,
            target=target
        )

    @profiler.trace('action-run')
    def run(self, input_dict, target, index=0, desc='', save=True,
            safe_rerun=False):
        assert not self.action_ex

        input_dict = self._prepare_input(input_dict)
        runtime_ctx = self._prepare_runtime_context(index, safe_rerun)

        # Assign the action execution ID here to minimize database calls.
        # Otherwise, the input property of the action execution DB object needs
        # to be updated with the action execution ID after the action execution
        # DB object is created.
        action_ex_id = utils.generate_unicode_uuid()

        self._insert_action_context(action_ex_id, input_dict, save=save)

        if save:
            self._create_action_execution(
                input_dict,
                runtime_ctx,
                desc=desc,
                action_ex_id=action_ex_id
            )

        result = rpc.get_executor_client().run_action(
            self.action_ex.id if self.action_ex else None,
            self.action_def.action_class,
            self.action_def.attributes or {},
            input_dict,
            target,
            async=False,
            safe_rerun=safe_rerun
        )

        return self._prepare_output(result)

    def is_sync(self, input_dict):
        input_dict = self._prepare_input(input_dict)

        a = a_m.get_action_class(self.action_def.name)(**input_dict)

        return a.is_sync()

    def validate_input(self, input_dict):
        if self.action_def.action_class:
            self._inject_action_ctx_for_validating(input_dict)

        # NOTE(xylan): Don't validate action input if action initialization
        # method contains ** argument.
        if '**' not in self.action_def.input:
            e_utils.validate_input(self.action_def, input_dict)

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

    def _insert_action_context(self, action_ex_id, input_dict, save=True):
        """Template method to prepare action context.

        It inserts the action context in the input if required
        runtime context.
        """
        # we need to push action context to all actions. It's related to
        # https://blueprints.launchpad.net/mistral/+spec/mistral-custom-actions-api
        has_action_context = a_m.has_action_context(
            self.action_def.action_class,
            self.action_def.attributes or {}
        )

        if has_action_context:
            input_dict.update(
                a_m.get_action_context(self.task_ex, action_ex_id, save=save)
            )


class AdHocAction(PythonAction):
    """Ad-hoc action."""

    def __init__(self, action_def, action_ex=None, task_ex=None):
        self.action_spec = spec_parser.get_action_spec(action_def.spec)

        base_action_def = db_api.get_action_definition(
            self.action_spec.get_base()
        )
        base_action_def = self._gather_base_actions(
            action_def, base_action_def
        )

        super(AdHocAction, self).__init__(
            base_action_def,
            action_ex,
            task_ex
        )

        self.adhoc_action_def = action_def

    def validate_input(self, input_dict):
        e_utils.validate_input(
            self.adhoc_action_def,
            input_dict,
            self.action_spec
        )

        super(AdHocAction, self).validate_input(
            self._prepare_input(input_dict)
        )

    def _prepare_input(self, input_dict):
        base_input_dict = input_dict

        for action_def in self.adhoc_action_defs:
            action_spec = spec_parser.get_action_spec(action_def.spec)
            base_input_expr = action_spec.get_base_input()
            if base_input_expr:
                base_input_dict = expr.evaluate_recursively(
                    base_input_expr,
                    base_input_dict
                )
            else:
                base_input_dict = {}

        return super(AdHocAction, self)._prepare_input(base_input_dict)

    def _prepare_output(self, result):
        # In case of error, we don't transform a result.
        if not result.is_error():
            adhoc_action_spec = spec_parser.get_action_spec(
                self.adhoc_action_def.spec
            )

            transformer = adhoc_action_spec.get_output()

            if transformer is not None:
                result = wf_utils.Result(
                    data=expr.evaluate_recursively(transformer, result.data),
                    error=result.error
                )

        return result

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

    def _gather_base_actions(self, action_def, base_action_def):
        """Find all base ad-hoc actions and store them

        An ad-hoc action may be based on another ad-hoc action (and this
        recursively). Using twice the same base action is not allowed to
        avoid infinite loops. It stores the list of ad-hoc actions.
        :param action_def: Action definition
        :type action_def: ActionDefinition
        :param base_action_def: Original base action definition
        :type base_action_def: ActionDefinition
        :return; The definition of the base system action
        :rtype; ActionDefinition
        """
        self.adhoc_action_defs = [action_def]
        original_base_name = self.action_spec.get_name()
        action_names = set([original_base_name])

        base = base_action_def
        while not base.is_system and base.name not in action_names:
            action_names.add(base.name)
            self.adhoc_action_defs.append(base)

            base_name = base.spec['base']
            base = db_api.get_action_definition(base_name)

        # if the action is repeated
        if base.name in action_names:
            raise ValueError(
                'An ad-hoc action cannot use twice the same action, %s is '
                'used at least twice' % base.name
            )

        return base


class WorkflowAction(Action):
    """Workflow action."""

    @profiler.trace('action-complete')
    def complete(self, result):
        # No-op because in case of workflow result is already processed.
        pass

    @profiler.trace('action-schedule')
    def schedule(self, input_dict, target, index=0, desc='', safe_rerun=False):
        assert not self.action_ex

        parent_wf_ex = self.task_ex.workflow_execution
        parent_wf_spec = spec_parser.get_workflow_spec_by_execution_id(
            parent_wf_ex.id
        )

        task_spec = spec_parser.get_task_spec(self.task_ex.spec)

        wf_spec_name = task_spec.get_workflow_name()

        wf_def = e_utils.resolve_workflow_definition(
            parent_wf_ex.workflow_name,
            parent_wf_spec.get_name(),
            wf_spec_name
        )

        wf_spec = spec_parser.get_workflow_spec_by_definition_id(
            wf_def.id,
            wf_def.updated_at
        )

        wf_params = {
            'task_execution_id': self.task_ex.id,
            'index': index
        }

        if 'env' in parent_wf_ex.params:
            wf_params['env'] = parent_wf_ex.params['env']

        for k, v in list(input_dict.items()):
            if k not in wf_spec.get_input():
                wf_params[k] = v
                del input_dict[k]

        wf_handler.start_workflow(
            wf_def.id,
            input_dict,
            "sub-workflow execution",
            wf_params
        )

    @profiler.trace('action-run')
    def run(self, input_dict, target, index=0, desc='', save=True,
            safe_rerun=True):
        raise NotImplementedError('Does not apply to this WorkflowAction.')

    def is_sync(self, input_dict):
        # Workflow action is always asynchronous.
        return False

    def validate_input(self, input_dict):
        # TODO(rakhmerov): Implement.
        pass


def _run_existing_action(action_ex_id, target):
    action_ex = db_api.get_action_execution(action_ex_id)
    action_def = db_api.get_action_definition(action_ex.name)

    result = rpc.get_executor_client().run_action(
        action_ex_id,
        action_def.action_class,
        action_def.attributes or {},
        action_ex.input,
        target,
        safe_rerun=action_ex.runtime_context.get('safe_rerun', False)
    )

    return result.to_dict() if result else None


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

        action_db = db_api.load_action_definition(action_full_name)

    if not action_db:
        action_db = db_api.load_action_definition(action_spec_name)

    if not action_db:
        raise exc.InvalidActionException(
            "Failed to find action [action_name=%s]" % action_spec_name
        )

    return action_db
