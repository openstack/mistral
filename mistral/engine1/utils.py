# Copyright 2014 - Mirantis, Inc.
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
from mistral import exceptions as exc
from mistral import expressions as expr
from mistral.openstack.common import log as logging
from mistral.workbook import parser as spec_parser
from mistral.workflow import utils as wf_utils

LOG = logging.getLogger(__name__)


def validate_workflow_input(wf_db, wf_spec, wf_input):
    input_param_names = copy.copy((wf_input or {}).keys())
    missing_param_names = []

    for p_name in wf_spec.get_input():
        if p_name not in input_param_names:
            missing_param_names.append(p_name)
        else:
            input_param_names.remove(p_name)

    if missing_param_names or input_param_names:
        msg = 'Invalid workflow input [workflow=%s'
        msg_props = [wf_db.name]

        if missing_param_names:
            msg += ', missing=%s'
            msg_props.append(missing_param_names)

        if input_param_names:
            msg += ', unexpected=%s'
            msg_props.append(input_param_names)

        msg += ']'

        raise exc.WorkflowInputException(
            msg % tuple(msg_props)
        )


def resolve_action(wf_name, wf_spec_name, action_spec_name):
    action_db = None

    if wf_name != wf_spec_name:
        # If workflow belongs to a workbook then check
        # action within the same workbook (to be able to
        # use short names within workbooks).
        # If it doesn't exist then use a name from spec
        # to find an action in DB.
        wb_name = wf_name.rstrip(wf_spec_name)[:-1]

        action_full_name = "%s.%s" % (wb_name, action_spec_name)

        action_db = db_api.load_action(action_full_name)

    if not action_db:
        action_db = db_api.load_action(action_spec_name)

    if not action_db:
        raise exc.InvalidActionException(
            "Failed to find action [action_name=%s]" % action_spec_name
        )

    return action_db


def resolve_workflow(parent_wf_name, parent_wf_spec_name, wf_spec_name):
    wf_db = None

    if parent_wf_name != parent_wf_spec_name:
        # If parent workflow belongs to a workbook then
        # check child workflow within the same workbook
        # (to be able to use short names within workbooks).
        # If it doesn't exist then use a name from spec
        # to find a workflow in DB.
        wb_name = parent_wf_name.rstrip(parent_wf_spec_name)[:-1]

        wf_full_name = "%s.%s" % (wb_name, wf_spec_name)

        wf_db = db_api.load_workflow(wf_full_name)

    if not wf_db:
        wf_db = db_api.load_workflow(wf_spec_name)

    if not wf_db:
        raise exc.WorkflowException(
            "Failed to find workflow [name=%s]" % wf_spec_name
        )

    return wf_db


def transform_result(exec_db, task_db, raw_result):
    if raw_result.is_error():
        return raw_result

    action_spec_name =\
        spec_parser.get_task_spec(task_db.spec).get_action_name()

    wf_spec_name = \
        spec_parser.get_workflow_spec(exec_db.wf_spec).get_name()

    if action_spec_name:
        return transform_action_result(
            exec_db.wf_name,
            wf_spec_name,
            action_spec_name,
            raw_result
        )

    return raw_result


def transform_action_result(wf_name, wf_spec_name, action_spec_name,
                            raw_result):
    action_db = resolve_action(
        wf_name,
        wf_spec_name,
        action_spec_name
    )

    if not action_db.spec:
        return raw_result

    transformer = spec_parser.get_action_spec(action_db.spec).get_output()

    if transformer is None:
        return raw_result

    return wf_utils.TaskResult(
        data=expr.evaluate_recursively(transformer, raw_result.data),
        error=raw_result.error
    )
