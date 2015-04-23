# Copyright 2014 - Mirantis, Inc.
# Copyright 2015 - Huawei Technologies Co. Ltd
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
import six

from mistral.db.v2 import api as db_api
from mistral import exceptions as exc
from mistral import expressions as expr
from mistral.openstack.common import log as logging
from mistral import utils
from mistral.workbook import parser as spec_parser
from mistral.workflow import utils as wf_utils

LOG = logging.getLogger(__name__)


def validate_input(definition, spec, input):
    input_param_names = copy.copy((input or {}).keys())
    missing_param_names = []

    for p_name, p_value in six.iteritems(spec.get_input()):
        if p_value is utils.NotDefined and p_name not in input_param_names:
            missing_param_names.append(p_name)
        if p_name in input_param_names:
            input_param_names.remove(p_name)

    if missing_param_names or input_param_names:
        msg = 'Invalid input [name=%s, class=%s'
        msg_props = [definition.name, spec.__class__.__name__]

        if missing_param_names:
            msg += ', missing=%s'
            msg_props.append(missing_param_names)

        if input_param_names:
            msg += ', unexpected=%s'
            msg_props.append(input_param_names)

        msg += ']'

        raise exc.InputException(
            msg % tuple(msg_props)
        )
    else:
        utils.merge_dicts(input, spec.get_input(), overwrite=False)


def resolve_action_definition(wf_name, wf_spec_name, action_spec_name):
    action_db = None

    if wf_name != wf_spec_name:
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


def resolve_workflow_definition(parent_wf_name, parent_wf_spec_name,
                                wf_spec_name):
    wf_def = None

    if parent_wf_name != parent_wf_spec_name:
        # If parent workflow belongs to a workbook then
        # check child workflow within the same workbook
        # (to be able to use short names within workbooks).
        # If it doesn't exist then use a name from spec
        # to find a workflow in DB.
        wb_name = parent_wf_name.rstrip(parent_wf_spec_name)[:-1]

        wf_full_name = "%s.%s" % (wb_name, wf_spec_name)

        wf_def = db_api.load_workflow_definition(wf_full_name)

    if not wf_def:
        wf_def = db_api.load_workflow_definition(wf_spec_name)

    if not wf_def:
        raise exc.WorkflowException(
            "Failed to find workflow [name=%s]" % wf_spec_name
        )

    return wf_def


# TODO(rakhmerov): Think of a better home for this method.
# Looks like we need a special module for ad-hoc actions.
def transform_result(task_ex, result):
    """Transforms task result accounting for ad-hoc actions.

    In case if the given result is an action result and action is
    an ad-hoc action the method transforms the result according to
    ad-hoc action configuration.

    :param task_ex: Task DB model.
    :param result: Result of task action/workflow.
    """
    if result.is_error():
        return result

    action_spec_name = spec_parser.get_task_spec(
        task_ex.spec).get_action_name()

    if action_spec_name:
        wf_ex = task_ex.workflow_execution
        wf_spec_name = spec_parser.get_workflow_spec(wf_ex.spec).get_name()

        return transform_action_result(
            wf_ex.workflow_name,
            wf_spec_name,
            action_spec_name,
            result
        )

    return result


# TODO(rakhmerov): Should probably go into task handler.
def transform_action_result(wf_name, wf_spec_name, action_spec_name, result):
    action_def = resolve_action_definition(
        wf_name,
        wf_spec_name,
        action_spec_name
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
