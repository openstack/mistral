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

from mistral.db.v2 import api as db_api
from mistral import exceptions as exc
from mistral import utils


def _compare_parameters(expected_input, actual_input):
    """Compares the expected parameters with the actual parameters.

    :param expected_input: Expected dict of parameters.
    :param actual_input: Actual dict of parameters.
    :return: Tuple {missing parameter names, unexpected parameter names}
    """

    missing_params = []
    unexpected_params = copy.deepcopy(list((actual_input or {}).keys()))

    for p_name, p_value in expected_input.items():
        if p_value is utils.NotDefined and p_name not in unexpected_params:
            missing_params.append(str(p_name))

        if p_name in unexpected_params:
            unexpected_params.remove(p_name)

    return missing_params, unexpected_params


def validate_input(expected_input, actual_input, obj_name, obj_class):
    actual_input = actual_input or {}

    missing, unexpected = _compare_parameters(
        expected_input,
        actual_input
    )

    if missing or unexpected:
        msg = 'Invalid input [name=%s, class=%s'
        msg_props = [obj_name, obj_class]

        if missing:
            msg += ', missing=%s'
            msg_props.append(missing)

        if unexpected:
            msg += ', unexpected=%s'
            msg_props.append(unexpected)

        msg += ']'

        raise exc.InputException(msg % tuple(msg_props))


def resolve_workflow_definition(parent_wf_name, parent_wf_spec_name,
                                namespace, wf_spec_name):
    wf_def = None

    if parent_wf_name != parent_wf_spec_name:
        # If parent workflow belongs to a workbook then
        # check child workflow within the same workbook
        # (to be able to use short names within workbooks).
        # If it doesn't exist then use a name from spec
        # to find a workflow in DB.
        wb_name = parent_wf_name.rstrip(parent_wf_spec_name)[:-1]

        wf_full_name = "%s.%s" % (wb_name, wf_spec_name)

        wf_def = db_api.load_workflow_definition(wf_full_name, namespace)

    if not wf_def:
        wf_def = db_api.load_workflow_definition(wf_spec_name, namespace)

    if not wf_def:
        raise exc.WorkflowException(
            "Failed to find workflow [name=%s] [namespace=%s]" %
            (wf_spec_name, namespace)
        )

    return wf_def
