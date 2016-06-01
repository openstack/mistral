# Copyright 2016 - StackStorm, Inc.
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

from oslo_log import log as logging

from mistral.db.v2 import api as db_api
from mistral.engine import utils as eng_utils
from mistral.utils import wf_trace
from mistral.workbook import parser as spec_parser
from mistral.workflow import data_flow
from mistral.workflow import states


LOG = logging.getLogger(__name__)


def canonize_workflow_params(params):
    # Resolve environment parameter.
    env = params.get('env', {})

    if not isinstance(env, dict) and not isinstance(env, six.string_types):
        raise ValueError(
            'Unexpected type for environment [environment=%s]' % str(env)
        )

    if isinstance(env, six.string_types):
        env_db = db_api.get_environment(env)
        env = env_db.variables
        params['env'] = env

    return params


def _create_workflow_execution(wf_def, wf_spec, wf_input, desc, params):
    wf_ex = db_api.create_workflow_execution({
        'name': wf_def.name,
        'description': desc,
        'workflow_name': wf_def.name,
        'workflow_id': wf_def.id,
        'spec': wf_spec.to_dict(),
        'params': params or {},
        'state': states.IDLE,
        'input': wf_input or {},
        'output': {},
        'context': copy.deepcopy(wf_input) or {},
        'task_execution_id': params.get('task_execution_id'),
        'runtime_context': {
            'index': params.get('index', 0)
        },
    })

    data_flow.add_openstack_data_to_context(wf_ex)
    data_flow.add_execution_to_context(wf_ex)
    data_flow.add_environment_to_context(wf_ex)
    data_flow.add_workflow_variables_to_context(wf_ex, wf_spec)

    return wf_ex


def create_workflow_execution(wf_identifier, wf_input, description, params,
                              wf_spec=None):
    params = canonize_workflow_params(params)

    wf_def = db_api.get_workflow_definition(wf_identifier)

    if wf_spec is None:
        wf_spec = spec_parser.get_workflow_spec(wf_def.spec)

    eng_utils.validate_input(wf_def, wf_input, wf_spec)

    wf_ex = _create_workflow_execution(
        wf_def,
        wf_spec,
        wf_input,
        description,
        params
    )

    wf_trace.info(wf_ex, "Starting workflow: '%s'" % wf_identifier)

    return wf_ex, wf_spec
