# Copyright 2016 - Nokia Networks.
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
import operator
from oslo_log import log as logging
import six

from mistral.db.v2 import api as db_api
from mistral.engine import actions
from mistral.engine import dispatcher
from mistral.engine import policies
from mistral import exceptions as exc
from mistral import expressions as expr
from mistral import utils
from mistral.utils import wf_trace
from mistral.workbook import parser as spec_parser
from mistral.workflow import base as wf_base
from mistral.workflow import data_flow
from mistral.workflow import states
from mistral.workflow import utils as wf_utils
from mistral.workflow import with_items


LOG = logging.getLogger(__name__)


@six.add_metaclass(abc.ABCMeta)
class Task(object):
    """Task.

    Represents a workflow task and defines interface that can be used by
    Mistral engine or its components in order to manipulate with tasks.
    """

    def __init__(self, wf_ex, task_spec, ctx, task_ex=None):
        self.wf_ex = wf_ex
        self.task_spec = task_spec
        self.ctx = ctx
        self.task_ex = task_ex
        self.wf_spec = spec_parser.get_workflow_spec(wf_ex.spec)
        self.waiting = False
        self.reset_flag = False

    @abc.abstractmethod
    def on_action_complete(self, action_ex):
        """Handle action completion.

        :param action_ex: Action execution.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def run(self):
        """Runs task."""
        raise NotImplementedError

    def defer(self):
        """Defers task.

        This methods finds task execution or creates new and puts task
        to a waiting state.
        """

        if not self.task_ex:
            self.task_ex = wf_utils.find_task_executions_by_spec(
                self.wf_ex,
                self.task_spec
            )

        if not self.task_ex:
            self._create_task_execution()

        self.set_state(states.WAITING, 'Task execution is deferred.')

        self.waiting = True

    def reset(self):
        self.reset_flag = True

    def set_state(self, state, state_info, processed=None):
        """Sets task state without executing post completion logic.

        :param state: New task state.
        :param state_info: New state information (i.e. error message).
        :param processed: New "processed" flag value.
        """

        wf_trace.info(
            self.task_ex.workflow_execution,
            "Task execution '%s' [%s -> %s]: %s" %
            (self.task_ex.id, self.task_ex.state, state, state_info)
        )

        self.task_ex.state = state
        self.task_ex.state_info = state_info

        if processed is not None:
            self.task_ex.processed = processed

    def complete(self, state, state_info=None):
        """Complete task and set specified state.

        Method sets specified task state and runs all necessary post
        completion logic such as publishing workflow variables and
        scheduling new workflow commands.

        :param state: New task state.
        :param state_info: New state information (i.e. error message).
        """

        # Ignore if task already completed.
        if states.is_completed(self.task_ex.state):
            return

        self.set_state(state, state_info)

        data_flow.publish_variables(self.task_ex, self.task_spec)

        if not self.task_spec.get_keep_result():
            # Destroy task result.
            for ex in self.task_ex.executions:
                if hasattr(ex, 'output'):
                    ex.output = {}

        self._after_task_complete()

        # Ignore DELAYED state.
        if self.task_ex.state == states.RUNNING_DELAYED:
            return

        # If workflow is paused we shouldn't schedule new commands
        # and mark task as processed.
        if states.is_paused(self.wf_ex.state):
            return

        wf_ctrl = wf_base.get_controller(self.wf_ex, self.wf_spec)

        # Calculate commands to process next.
        cmds = wf_ctrl.continue_workflow()

        # Mark task as processed after all decisions have been made
        # upon its completion.
        self.task_ex.processed = True

        dispatcher.dispatch_workflow_commands(self.wf_ex, cmds)

    def _before_task_start(self):
        policies_spec = self.task_spec.get_policies()

        for p in policies.build_policies(policies_spec, self.wf_spec):
            p.before_task_start(self.task_ex, self.task_spec)

    def _after_task_complete(self):
        policies_spec = self.task_spec.get_policies()

        for p in policies.build_policies(policies_spec, self.wf_spec):
            p.after_task_complete(self.task_ex, self.task_spec)

    def _create_task_execution(self, state=states.RUNNING):
        self.task_ex = db_api.create_task_execution({
            'name': self.task_spec.get_name(),
            'workflow_execution_id': self.wf_ex.id,
            'workflow_name': self.wf_ex.workflow_name,
            'workflow_id': self.wf_ex.workflow_id,
            'state': state,
            'spec': self.task_spec.to_dict(),
            'in_context': self.ctx,
            'published': {},
            'runtime_context': {},
            'project_id': self.wf_ex.project_id
        })

        # Add to collection explicitly so that it's in a proper
        # state within the current session.
        self.wf_ex.task_executions.append(self.task_ex)

    def _get_action_defaults(self):
        action_name = self.task_spec.get_action_name()

        if not action_name:
            return {}

        env = self.task_ex.in_context.get('__env', {})

        return env.get('__actions', {}).get(action_name, {})


class RegularTask(Task):
    """Regular task.

    Takes care of processing regular tasks with one action.
    """

    def on_action_complete(self, action_ex):
        state = action_ex.state
        # TODO(rakhmerov): Here we can define more informative messages
        # cases when action is successful and when it's not. For example,
        # in state_info we can specify the cause action.
        state_info = (None if state == states.SUCCESS
                      else action_ex.output.get('result'))

        self.complete(state, state_info)

    def is_completed(self):
        return self.task_ex and states.is_completed(self.task_ex.state)

    def run(self):
        if not self.task_ex:
            self._run_new()
        else:
            self._run_existing()

    def _run_new(self):
        # NOTE(xylan): Need to think how to get rid of this weird judgment
        # to keep it more consistent with the function name.
        self.task_ex = wf_utils.find_task_execution_with_state(
            self.wf_ex,
            self.task_spec,
            states.WAITING
        )

        if self.task_ex:
            self.set_state(states.RUNNING, None)

            self.task_ex.in_context = self.ctx
        else:
            self._create_task_execution()

        LOG.debug(
            'Starting task [workflow=%s, task_spec=%s, init_state=%s]' %
            (self.wf_ex.name, self.task_spec, self.task_ex.state)
        )

        self._before_task_start()

        # Policies could possibly change task state.
        if self.task_ex.state != states.RUNNING:
            return

        self._schedule_actions()

    def _run_existing(self):
        if self.waiting:
            return

        # Explicitly change task state to RUNNING.
        # Throw exception if the existing task already succeeded.
        if self.task_ex.state == states.SUCCESS:
            raise exc.MistralError(
                'Rerunning succeeded tasks is not supported.'
            )

        self.set_state(states.RUNNING, None, processed=False)

        self._reset_actions()

        self._schedule_actions()

    def _reset_actions(self):
        """Resets task state.

        Depending on task type this method may reset task state. For example,
        delete all task actions etc.
        """

        # Reset state of processed task and related action executions.
        if self.reset_flag:
            action_exs = self.task_ex.executions
        else:
            action_exs = db_api.get_action_executions(
                task_execution_id=self.task_ex.id,
                state=states.ERROR,
                accepted=True
            )

        for action_ex in action_exs:
            action_ex.accepted = False

    def _schedule_actions(self):
        # Regular task schedules just one action.
        input_dict = self._get_action_input()
        target = self._get_target(input_dict)

        action = self._build_action()

        action.validate_input(input_dict)

        action.schedule(input_dict, target)

    def _get_target(self, input_dict):
        return expr.evaluate_recursively(
            self.task_spec.get_target(),
            utils.merge_dicts(
                copy.deepcopy(input_dict),
                copy.deepcopy(self.ctx)
            )
        )

    def _get_action_input(self, ctx=None):
        ctx = ctx or self.ctx

        input_dict = expr.evaluate_recursively(self.task_spec.get_input(), ctx)

        return utils.merge_dicts(
            input_dict,
            self._get_action_defaults(),
            overwrite=False
        )

    def _build_action(self):
        action_name = self.task_spec.get_action_name()
        wf_name = self.task_spec.get_workflow_name()

        if wf_name:
            return actions.WorkflowAction(wf_name, task_ex=self.task_ex)

        if not action_name:
            action_name = 'std.noop'

        action_def = actions.resolve_action_definition(
            action_name,
            self.wf_ex.name,
            self.wf_spec.get_name()
        )

        if action_def.spec:
            return actions.AdHocAction(action_def, task_ex=self.task_ex)

        return actions.PythonAction(action_def, task_ex=self.task_ex)


class WithItemsTask(RegularTask):
    """With-items task.

    Takes care of processing "with-items" tasks.
    """

    def on_action_complete(self, action_ex):
        state = action_ex.state
        # TODO(rakhmerov): Here we can define more informative messages
        # cases when action is successful and when it's not. For example,
        # in state_info we can specify the cause action.
        state_info = (None if state == states.SUCCESS
                      else action_ex.output.get('result'))

        with_items.increase_capacity(self.task_ex)

        if with_items.is_completed(self.task_ex):
            self.complete(
                with_items.get_final_state(self.task_ex),
                state_info
            )

            return

        if (with_items.has_more_iterations(self.task_ex)
                and with_items.get_concurrency(self.task_ex)):
            self._schedule_actions()

    def _schedule_actions(self):
        input_dicts = self._get_with_items_input()

        if not input_dicts:
            self.complete(states.SUCCESS)

            return

        for idx, input_dict in input_dicts:
            target = self._get_target(input_dict)

            action = self._build_action()

            action.schedule(input_dict, target, index=idx)

    def _get_with_items_input(self):
        """Calculate input array for separating each action input.

        Example:
          DSL:
            with_items:
              - itemX in <% $.arrayI %>
              - itemY in <% $.arrayJ %>

          Assume arrayI = [1, 2], arrayJ = ['a', 'b'].
          with_items_input = {
            "itemX": [1, 2],
            "itemY": ['a', 'b']
          }

          Then we get separated input:
          inputs_per_item = [
            {'itemX': 1, 'itemY': 'a'},
            {'itemX': 2, 'itemY': 'b'}
          ]

        :return: the list of tuples containing indexes
        and the corresponding input dict.
        """
        with_items_inputs = expr.evaluate_recursively(
            self.task_spec.get_with_items(),
            self.ctx
        )

        with_items.validate_input(with_items_inputs)

        inputs_per_item = []

        for key, value in with_items_inputs.items():
            for index, item in enumerate(value):
                iter_context = {key: item}

                if index >= len(inputs_per_item):
                    inputs_per_item.append(iter_context)
                else:
                    inputs_per_item[index].update(iter_context)

        action_inputs = []

        for item_input in inputs_per_item:
            new_ctx = utils.merge_dicts(item_input, self.ctx)

            action_inputs.append(self._get_action_input(new_ctx))

        with_items.prepare_runtime_context(
            self.task_ex,
            self.task_spec,
            action_inputs
        )

        indices = with_items.get_indices_for_loop(self.task_ex)

        with_items.decrease_capacity(self.task_ex, len(indices))

        if indices:
            current_inputs = operator.itemgetter(*indices)(action_inputs)

            return zip(
                indices,
                current_inputs if isinstance(current_inputs, tuple)
                else [current_inputs]
            )

        return []
