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
from mistral import utils


# TODO(rakhmerov): This method is too abstract, validation rules may vary
#  depending on object type (action, wf), it's not clear what it can be
# applied to.
# TODO(rakhmerov): It must not do any manipulations with parameters
#  (input_dict)!
def validate_input(definition, input_dict, spec=None):
    input_param_names = copy.deepcopy(list((input_dict or {}).keys()))
    missing_param_names = []

    spec_input = (spec.get_input() if spec else
                  utils.get_dict_from_string(definition.input))

    for p_name, p_value in six.iteritems(spec_input):
        if p_value is utils.NotDefined and p_name not in input_param_names:
            missing_param_names.append(str(p_name))

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
        utils.merge_dicts(input_dict, spec_input, overwrite=False)


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
