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


from mistral.db.v2 import api as db_api
from mistral.engine import rpc
from mistral.engine import utils as e_utils
from mistral import exceptions as exc
from mistral import expressions as expr
from mistral.services import action_manager as a_m
from mistral.services import security
from mistral import utils
from mistral.utils import wf_trace
from mistral.workbook import parser as spec_parser
from mistral.workflow import states
from mistral.workflow import utils as wf_utils


def create_action_execution(action_def, action_input, task_ex=None,
                            index=0, description=''):
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
            action_def.action_class, action_def.attributes or {}) and task_ex:
        action_input.update(a_m.get_action_context(task_ex, action_ex_id))

    values = {
        'id': action_ex_id,
        'name': action_def.name,
        'spec': action_def.spec,
        'state': states.RUNNING,
        'input': action_input,
        'runtime_context': {'with_items_index': index},
        'description': description
    }

    if task_ex:
        values.update({
            'task_execution_id': task_ex.id,
            'workflow_name': task_ex.workflow_name,
            'workflow_id': task_ex.workflow_id,
            'project_id': task_ex.project_id,
        })
    else:
        values.update({
            'project_id': security.get_project_id(),
        })

    action_ex = db_api.create_action_execution(values)

    if task_ex:
        # Add to collection explicitly so that it's in a proper
        # state within the current session.
        task_ex.executions.append(action_ex)

    return action_ex


def _inject_action_ctx_for_validating(action_def, input_dict):
    if a_m.has_action_context(action_def.action_class, action_def.attributes):
        input_dict.update(a_m.get_empty_action_context())


def get_action_input(action_name, input_dict, wf_name=None, wf_spec=None):
    action_def = resolve_action_definition(
        action_name,
        wf_name,
        wf_spec.get_name() if wf_spec else None
    )

    if action_def.action_class:
        _inject_action_ctx_for_validating(action_def, input_dict)

    # NOTE(xylan): Don't validate action input if action initialization method
    # contains ** argument.
    if '**' not in action_def.input:
        e_utils.validate_input(action_def, input_dict)

    if action_def.spec:
        # Ad-hoc action.
        return _get_adhoc_action_input(
            action_def,
            input_dict,
            wf_name,
            wf_spec
        )

    return input_dict


def _get_adhoc_action_input(action_def, input_dict,
                            wf_name=None, wf_spec=None):
    action_spec = spec_parser.get_action_spec(action_def.spec)

    base_name = action_spec.get_base()

    action_def = resolve_action_definition(
        base_name,
        wf_name if wf_name else None,
        wf_spec.get_name() if wf_spec else None
    )

    _inject_action_ctx_for_validating(action_def, input_dict)
    e_utils.validate_input(action_def, input_dict, action_spec)

    base_input = action_spec.get_base_input()

    if base_input:
        input_dict = expr.evaluate_recursively(
            base_input,
            input_dict
        )
    else:
        input_dict = {}

    return input_dict


def run_action(action_def, action_input,
               action_ex_id=None, target=None, async=True):
    action_result = rpc.get_executor_client().run_action(
        action_ex_id,
        action_def.action_class,
        action_def.attributes or {},
        action_input,
        target,
        async
    )

    if action_result:
        return _get_action_output(action_result)


def _get_action_output(result):
    """Returns action output.

    :param result: ActionResult instance or ActionResult dict
    :return: dict containing result.
    """
    if isinstance(result, dict):
        result = wf_utils.Result(result.get('data'), result.get('error'))

    return ({'result': result.data}
            if result.is_success() else {'result': result.error})


def store_action_result(action_ex, result):
    prev_state = action_ex.state

    action_ex.state = states.SUCCESS if result.is_success() else states.ERROR
    action_ex.output = _get_action_output(result)

    action_ex.accepted = True

    _log_action_result(action_ex, prev_state, action_ex.state, result)

    return action_ex


def _log_action_result(action_ex, from_state, to_state, result):
    def _result_msg():
        if action_ex.state == states.ERROR:
            return "error = %s" % utils.cut(result.error)

        return "result = %s" % utils.cut(result.data)

    wf_trace.info(
        None,
        "Action execution '%s' [%s -> %s, %s]" %
        (action_ex.name, from_state, to_state, _result_msg())
    )


def run_existing_action(action_ex_id, target):
    action_ex = db_api.get_action_execution(action_ex_id)
    action_def = db_api.get_action_definition(action_ex.name)

    return run_action(
        action_def,
        action_ex.input,
        action_ex_id,
        target
    )


def resolve_definition(action_name, task_ex=None, wf_spec=None):
    if task_ex and wf_spec:
        wf_ex = task_ex.workflow_execution

        action_def = resolve_action_definition(
            action_name,
            wf_ex.workflow_name,
            wf_spec.get_name()
        )
    else:
        action_def = resolve_action_definition(action_name)

    if action_def.spec:
        # Ad-hoc action.
        action_spec = spec_parser.get_action_spec(action_def.spec)

        base_name = action_spec.get_base()

        action_def = resolve_action_definition(
            base_name,
            task_ex.workflow_name if task_ex else None,
            wf_spec.get_name() if wf_spec else None
        )

    return action_def


def resolve_action_definition(action_spec_name, wf_name=None,
                              wf_spec_name=None):
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


def transform_result(result, task_ex=None, action_ex=None):
    """Transforms task result accounting for ad-hoc actions.

    In case if the given result is an action result and action is
    an ad-hoc action the method transforms the result according to
    ad-hoc action configuration.

    :param task_ex: Task DB model.
    :param result: Result of task action/workflow.
    """
    if result.is_error():
        return result

    action_spec_name = None

    if task_ex:
        action_spec_name = spec_parser.get_task_spec(
            task_ex.spec).get_action_name()
    elif action_ex:
        if action_ex.spec:
            action_spec_name = spec_parser.get_action_spec(action_ex.spec)
        else:
            action_spec_name = action_ex.name

    if action_spec_name:
        wf_ex = task_ex.workflow_execution if task_ex else None
        wf_spec_name = wf_ex.spec['name'] if task_ex else None

        return transform_action_result(
            action_spec_name,
            result,
            wf_ex.workflow_name if wf_ex else None,
            wf_spec_name if wf_ex else None,
        )

    return result


def transform_action_result(action_spec_name, result,
                            wf_name=None, wf_spec_name=None):
    action_def = resolve_action_definition(
        action_spec_name,
        wf_name,
        wf_spec_name
    )

    if not action_def.spec:
        return result

    transformer = spec_parser.get_action_spec(action_def.spec).get_output()

    if transformer is None:
        return result

    return wf_utils.Result(
        data=expr.evaluate_recursively(transformer, result.data),
        error=result.error
    )
