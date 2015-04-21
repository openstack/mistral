# Copyright 2015 - Mirantis, Inc.
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

import copy

from mistral.db.v2 import api as db_api
from mistral.db.v2.sqlalchemy import models
from mistral.engine import policies
from mistral.engine import rpc
from mistral.engine import utils as e_utils
from mistral import expressions as expr
from mistral.openstack.common import log as logging
from mistral.services import action_manager as a_m
from mistral.services import scheduler
from mistral import utils
from mistral.utils import wf_trace
from mistral.workbook import parser as spec_parser
from mistral.workflow import data_flow
from mistral.workflow import states
from mistral.workflow import with_items


"""Responsible for running tasks and handling results."""

LOG = logging.getLogger(__name__)


def run_existing_task(task_ex_id):
    """This function runs existing task execution.

    It is needed mostly by scheduler.
    """
    task_ex = db_api.get_task_execution(task_ex_id)
    task_spec = spec_parser.get_task_spec(task_ex.spec)
    wf_def = db_api.get_workflow_definition(task_ex.workflow_name)
    wf_spec = spec_parser.get_workflow_spec(wf_def.spec)

    # Explicitly change task state to RUNNING.
    task_ex.state = states.RUNNING

    _run_existing_task(task_ex, task_spec, wf_spec)


def _run_existing_task(task_ex, task_spec, wf_spec):
    input_dicts = _get_input_dictionaries(
        wf_spec,
        task_ex,
        task_spec,
        task_ex.in_context
    )

    # TODO(rakhmerov): May be it shouldn't be here. Need to think.
    if task_spec.get_with_items():
        with_items.prepare_runtime_context(task_ex, task_spec, input_dicts)

    # In some cases we can have no input, e.g. in case of 'with-items'.
    if input_dicts:
        for index, input_d in enumerate(input_dicts):
            _run_action_or_workflow(task_ex, task_spec, input_d, index)
    else:
        _schedule_noop_action(task_ex, task_spec)


def run_new_task(wf_cmd):
    """Runs a task."""
    ctx = wf_cmd.ctx
    wf_ex = wf_cmd.wf_ex
    wf_spec = spec_parser.get_workflow_spec(wf_ex.spec)
    task_spec = wf_cmd.task_spec

    LOG.debug(
        'Starting workflow task [workflow=%s, task_spec=%s]' %
        (wf_ex.name, task_spec)
    )

    task_ex = _create_task_execution(wf_ex, task_spec, ctx)

    # TODO(rakhmerov): 'concurrency' policy should keep a number of running
    # actions/workflows under control so it can't be implemented if it runs
    # before any action executions are created.
    before_task_start(task_ex, task_spec, wf_spec)

    # Policies could possibly change task state.
    if task_ex.state != states.RUNNING:
        return

    _run_existing_task(task_ex, task_spec, wf_spec)


def on_action_complete(action_ex, result):
    """Handles event of action result arrival.

    Given action result this method performs analysis of the workflow
    execution and identifies commands (including tasks) that can be
    scheduled for execution.

    :param action_ex: Action execution objects the result belongs to.
    :param result: Task action/workflow output wrapped into
        mistral.workflow.utils.Result instance.
    :return List of engine commands that need to be performed.
    """

    task_ex = action_ex.task_execution

    # Ignore if action already completed.
    if (states.is_completed(action_ex.state) and not
            isinstance(action_ex, models.WorkflowExecution)):
        return task_ex

    result = e_utils.transform_result(task_ex, result)

    wf_ex = task_ex.workflow_execution

    # Ignore workflow executions because they're handled during
    # workflow completion
    if not isinstance(action_ex, models.WorkflowExecution):
        _store_action_result(wf_ex, action_ex, result)

    wf_spec = spec_parser.get_workflow_spec(wf_ex.spec)
    task_spec = wf_spec.get_tasks()[task_ex.name]

    if result.is_success():
        if not task_spec.get_with_items():
            _complete_task(task_ex, task_spec, states.SUCCESS)
        else:
            if with_items.iterations_completed(task_ex):
                _complete_task(task_ex, task_spec, states.SUCCESS)

    else:
        _complete_task(task_ex, task_spec, states.ERROR)

    return task_ex


def _create_task_execution(wf_ex, task_spec, ctx):
    task_ex = db_api.create_task_execution({
        'name': task_spec.get_name(),
        'workflow_execution_id': wf_ex.id,
        'workflow_name': wf_ex.workflow_name,
        'state': states.RUNNING,
        'spec': task_spec.to_dict(),
        'in_context': ctx,
        'published': {},
        'runtime_context': {},
        'project_id': wf_ex.project_id
    })

    # Add to collection explicitly so that it's in a proper
    # state within the current session.
    wf_ex.task_executions.append(task_ex)

    return task_ex


def _create_action_execution(task_ex, action_def, action_input, index=0):
    # TODO(rakhmerov): We can avoid hitting DB at all when calling something
    # create_action_execution(), these operations can be just done using
    # SQLAlchemy session (1-level cache) and session flush (on TX commit) would
    # send necessary SQL queries to DB. Currently, session flush happens
    # on every operation which may not be optimal. The problem with using just
    # session level cache is in generating ids. Ids are generated only on
    # session flush. And now we have a lot places where we need to have ids
    # before TX completion.

    # Assign the action execution ID here to minimize database calls.
    # Otherwise, the input property of the action execution DB object needs
    # to be updated with the action execution ID after the action execution
    # DB object is created.
    action_ex_id = utils.generate_unicode_uuid()

    if a_m.has_action_context(
            action_def.action_class, action_def.attributes or {}):
        action_input.update(a_m.get_action_context(task_ex, action_ex_id))

    action_ex = db_api.create_action_execution({
        'id': action_ex_id,
        'name': action_def.name,
        'task_execution_id': task_ex.id,
        'workflow_name': task_ex.workflow_name,
        'spec': action_def.spec,
        'project_id': task_ex.project_id,
        'state': states.RUNNING,
        'input': action_input,
        'runtime_context': {'with_items_index': index}}
    )

    # Add to collection explicitly so that it's in a proper
    # state within the current session.
    task_ex.executions.append(action_ex)

    return action_ex


def before_task_start(task_ex, task_spec, wf_spec):
    for p in policies.build_policies(task_spec.get_policies(), wf_spec):
        p.before_task_start(task_ex, task_spec)


def after_task_complete(task_ex, task_spec, wf_spec):
    for p in policies.build_policies(task_spec.get_policies(), wf_spec):
        p.after_task_complete(task_ex, task_spec)


def _get_input_dictionaries(wf_spec, task_ex, task_spec, ctx):
    """Calculates a collection of inputs for task action/workflow.

    If the given task is not configured as 'with-items' then return list
    will consist of one dictionary containing input that task action/workflow
    should run with.
    In case of 'with-items' the result list will contain input dictionaries
    for all 'with-items' iterations correspondingly.
    """
    # TODO(rakhmerov): Think how to get rid of this.
    ctx = data_flow.extract_task_result_proxies_to_context(ctx)

    if not task_spec.get_with_items():
        input_dict = _get_workflow_or_action_input(
            wf_spec,
            task_ex,
            task_spec,
            ctx
        )

        return [input_dict]
    else:
        return _get_with_items_input(wf_spec, task_ex, task_spec, ctx)


def _get_workflow_or_action_input(wf_spec, task_ex, task_spec, ctx):
    if task_spec.get_action_name():
        return _get_action_input(
            wf_spec,
            task_ex,
            task_spec,
            ctx
        )
    elif task_spec.get_workflow_name():
        return _get_workflow_input(task_spec, ctx)
    else:
        raise RuntimeError('Must never happen.')


def _get_with_items_input(wf_spec, task_ex, task_spec, ctx):
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

    :return: list containing dicts of each action input.
    """
    with_items_inputs = expr.evaluate_recursively(
        task_spec.get_with_items(), ctx
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
        new_ctx = utils.merge_dicts(item_input, ctx)

        action_inputs.append(_get_workflow_or_action_input(
            wf_spec, task_ex, task_spec, new_ctx
        ))

    return action_inputs


def _get_action_input(wf_spec, task_ex, task_spec, ctx):
    input_dict = expr.evaluate_recursively(task_spec.get_input(), ctx)

    action_spec_name = task_spec.get_action_name()

    action_def = e_utils.resolve_action_definition(
        task_ex.workflow_name,
        wf_spec.get_name(),
        action_spec_name
    )

    input_dict = utils.merge_dicts(
        input_dict,
        _get_action_defaults(task_ex, task_spec),
        overwrite=False
    )

    if action_def.spec:
        # Ad-hoc action.
        action_spec = spec_parser.get_action_spec(action_def.spec)

        base_name = action_spec.get_base()

        action_def = e_utils.resolve_action_definition(
            task_ex.workflow_name,
            wf_spec.get_name(),
            base_name
        )

        e_utils.validate_input(action_def, action_spec, input_dict)

        base_input = action_spec.get_base_input()

        if base_input:
            input_dict = expr.evaluate_recursively(
                base_input,
                input_dict
            )
        else:
            input_dict = {}

    return input_dict


def _get_workflow_input(task_spec, ctx):
    return expr.evaluate_recursively(task_spec.get_input(), ctx)


def _run_action_or_workflow(task_ex, task_spec, input_dict, index):
    t_name = task_ex.name

    if task_spec.get_action_name():
        wf_trace.info(
            task_ex,
            "Task '%s' is RUNNING [action_name = %s]" %
            (t_name, task_spec.get_action_name())
        )

        _schedule_run_action(task_ex, task_spec, input_dict, index)
    elif task_spec.get_workflow_name():
        wf_trace.info(
            task_ex,
            "Task '%s' is RUNNING [workflow_name = %s]" %
            (t_name, task_spec.get_workflow_name()))

        _schedule_run_workflow(task_ex, task_spec, input_dict, index)


def _get_action_defaults(task_ex, task_spec):
    actions = task_ex.in_context.get('__env', {}).get('__actions', {})

    return actions.get(task_spec.get_action_name(), {})


def _schedule_run_action(task_ex, task_spec, action_input, index):
    wf_ex = task_ex.workflow_execution
    wf_spec = spec_parser.get_workflow_spec(wf_ex.spec)

    action_spec_name = task_spec.get_action_name()

    # TODO(rakhmerov): Refactor ad-hoc actions and isolate them.
    action_def = e_utils.resolve_action_definition(
        wf_ex.workflow_name,
        wf_spec.get_name(),
        action_spec_name
    )

    if action_def.spec:
        # Ad-hoc action.
        action_spec = spec_parser.get_action_spec(action_def.spec)

        base_name = action_spec.get_base()

        action_def = e_utils.resolve_action_definition(
            task_ex.workflow_name,
            wf_spec.get_name(),
            base_name
        )

    action_ex = _create_action_execution(
        task_ex, action_def, action_input, index
    )

    target = expr.evaluate_recursively(
        task_spec.get_target(),
        utils.merge_dicts(
            copy.deepcopy(action_input),
            copy.copy(task_ex.in_context)
        )
    )

    scheduler.schedule_call(
        None,
        'mistral.engine.task_handler.run_action',
        0,
        action_ex_id=action_ex.id,
        target=target
    )


def _schedule_noop_action(task_ex, task_spec):
    wf_ex = task_ex.workflow_execution
    wf_spec = spec_parser.get_workflow_spec(wf_ex.spec)

    action_def = e_utils.resolve_action_definition(
        wf_ex.workflow_name,
        wf_spec.get_name(),
        'std.noop'
    )

    action_ex = _create_action_execution(task_ex, action_def, {})

    target = expr.evaluate_recursively(
        task_spec.get_target(),
        task_ex.in_context
    )

    scheduler.schedule_call(
        None,
        'mistral.engine.task_handler.run_action',
        0,
        action_ex_id=action_ex.id,
        target=target
    )


def run_action(action_ex_id, target):
    action_ex = db_api.get_action_execution(action_ex_id)
    action_def = db_api.get_action_definition(action_ex.name)

    rpc.get_executor_client().run_action(
        action_ex.id,
        action_def.action_class,
        action_def.attributes or {},
        action_ex.input,
        target
    )


def _schedule_run_workflow(task_ex, task_spec, wf_input, index):
    parent_wf_ex = task_ex.workflow_execution
    parent_wf_spec = spec_parser.get_workflow_spec(parent_wf_ex.spec)

    wf_spec_name = task_spec.get_workflow_name()

    wf_def = e_utils.resolve_workflow_definition(
        parent_wf_ex.workflow_name,
        parent_wf_spec.get_name(),
        wf_spec_name
    )

    wf_spec = spec_parser.get_workflow_spec(wf_def.spec)

    wf_params = {
        'task_execution_id': task_ex.id,
        'with_items_index': index
    }

    if 'env' in parent_wf_ex.params:
        wf_params['env'] = parent_wf_ex.params['env']

    for k, v in wf_input.items():
        if k not in wf_spec.get_input():
            wf_params[k] = v
            del wf_input[k]

    scheduler.schedule_call(
        None,
        'mistral.engine.task_handler.run_workflow',
        0,
        wf_name=wf_def.name,
        wf_input=wf_input,
        wf_params=wf_params
    )


def run_workflow(wf_name, wf_input, wf_params):
    rpc.get_engine_client().start_workflow(
        wf_name,
        wf_input,
        **wf_params
    )


def _store_action_result(wf_ex, action_ex, result):
    prev_state = action_ex.state

    if result.is_success():
        action_ex.state = states.SUCCESS
        action_ex.output = {'result': result.data}
        action_ex.accepted = True
    else:
        action_ex.state = states.ERROR
        action_ex.output = {'result': result.error}
        action_ex.accepted = False

    _log_action_result(wf_ex, action_ex, prev_state, action_ex.state, result)

    return action_ex.state


def _complete_task(task_ex, task_spec, state):
    # Ignore if task already completed.
    if states.is_completed(task_ex.state):
        return []

    _set_task_state(task_ex, state)

    if task_ex.state == states.SUCCESS:
        data_flow.publish_variables(
            task_ex,
            task_spec
        )

    if not task_spec.get_keep_result():
        data_flow.destroy_task_result(task_ex)


def _set_task_state(task_ex, state):
    # TODO(rakhmerov): How do we log task result?
    wf_trace.info(
        task_ex.workflow_execution,
        "Task execution '%s' [%s -> %s]" %
        (task_ex.name, task_ex.state, state)
    )

    task_ex.state = state


def _log_action_result(wf_ex, action_ex, from_state, to_state, result):
    def _result_msg():
        if action_ex.state == states.ERROR:
            return "error = %s" % utils.cut(result.error)

        return "result = %s" % utils.cut(result.data)

    wf_trace.info(
        wf_ex,
        "Action execution '%s' [%s -> %s, %s]" %
        (action_ex.name, from_state, to_state, _result_msg())
    )
