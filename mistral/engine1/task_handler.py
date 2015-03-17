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
from mistral.engine1 import policies
from mistral.engine1 import rpc
from mistral.engine1 import utils as e_utils
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


def run_existent_task(task_ex_id):
    """This function runs existent task execution.

    It is needed mostly by scheduler.
    """
    task_ex = db_api.get_task_execution(task_ex_id)
    task_spec = spec_parser.get_task_spec(task_ex.spec)
    wf_spec = spec_parser.get_workflow_spec(
        db_api.get_workflow_definition(task_ex.workflow_name).spec
    )

    # Explicitly change task state to RUNNING.
    task_ex.state = states.RUNNING

    _run_existent_task(task_ex, task_spec, wf_spec)


def _run_existent_task(task_ex, task_spec, wf_spec):
    input_dicts = _get_input_dictionaries(
        wf_spec, task_ex, task_spec, task_ex.in_context
    )
    for input_d in input_dicts:
        _run_action_or_workflow(task_ex, task_spec, input_d)


def run_task(wf_cmd):
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

    _run_existent_task(task_ex, task_spec, wf_spec)


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
            # TODO(rakhmerov): Implement 'with-items' logic.
            pass
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

    # TODO(rakhmerov): May be it shouldn't be here. Need to think.
    if task_spec.get_with_items():
        with_items.prepare_runtime_context(task_ex, task_spec)

    return task_ex


def _create_action_execution(task_ex, action_def, action_input):
    action_ex = db_api.create_action_execution({
        'name': action_def.name,
        'task_execution_id': task_ex.id,
        'workflow_name': task_ex.workflow_name,
        'spec': action_def.spec,
        'project_id': task_ex.project_id,
        'state': states.RUNNING,
        'input': action_input}
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

    if not task_spec.get_with_items():
        if task_spec.get_action_name():
            input_dict = get_action_input(
                wf_spec,
                task_ex,
                task_spec,
                ctx
            )
        elif task_spec.get_workflow_name():
            input_dict = get_workflow_input(task_spec, ctx)
        else:
            raise RuntimeError('Must never happen.')

        return [input_dict]
    else:
        # TODO(rakhmerov): Implement 'with-items'.
        return []


def get_action_input(wf_spec, task_ex, task_spec, ctx):
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

        base_input = action_spec.get_base_input()

        if base_input:
            input_dict = expr.evaluate_recursively(
                base_input,
                input_dict
            )
        else:
            input_dict = {}

    if a_m.has_action_context(
            action_def.action_class, action_def.attributes or {}):
        input_dict.update(a_m.get_action_context(task_ex))

    return input_dict


def get_workflow_input(task_spec, ctx):
    return expr.evaluate_recursively(task_spec.get_input(), ctx)


def _run_action_or_workflow(task_ex, task_spec, input_dict):
    t_name = task_ex.name

    if task_spec.get_action_name():
        wf_trace.info(
            task_ex,
            "Task '%s' is RUNNING [action_name = %s]" %
            (t_name, task_spec.get_action_name())
        )

        _schedule_run_action(task_ex, task_spec, input_dict)
    elif task_spec.get_workflow_name():
        wf_trace.info(
            task_ex,
            "Task '%s' is RUNNING [workflow_name = %s]" %
            (t_name, task_spec.get_workflow_name()))

        _schedule_run_workflow(task_ex, task_spec, input_dict)


def _get_action_defaults(task_ex, task_spec):
    actions = task_ex.in_context.get('__env', {}).get('__actions', {})

    return actions.get(task_spec.get_action_name(), {})


def _schedule_run_action(task_ex, task_spec, action_input):
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

    action_ex = _create_action_execution(task_ex, action_def, action_input)

    target = expr.evaluate_recursively(
        task_spec.get_target(),
        utils.merge_dicts(
            copy.deepcopy(action_input),
            copy.copy(task_ex.in_context)
        )
    )

    scheduler.schedule_call(
        None,
        'mistral.engine1.task_handler.run_action',
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


def _schedule_run_workflow(task_ex, task_spec, wf_input):
    parent_wf_ex = task_ex.workflow_execution
    parent_wf_spec = spec_parser.get_workflow_spec(parent_wf_ex.spec)

    wf_spec_name = task_spec.get_workflow_name()

    wf_def = e_utils.resolve_workflow_definition(
        parent_wf_ex.workflow_name,
        parent_wf_spec.get_name(),
        wf_spec_name
    )

    wf_spec = spec_parser.get_workflow_spec(wf_def.spec)

    wf_params = {'task_execution_id': task_ex.id}

    if 'env' in parent_wf_ex.params:
        wf_params['env'] = parent_wf_ex.params['env']

    for k, v in wf_input.items():
        if k not in wf_spec.get_input():
            wf_params[k] = v
            del wf_input[k]

    scheduler.schedule_call(
        None,
        'mistral.engine1.task_handler.run_workflow',
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
