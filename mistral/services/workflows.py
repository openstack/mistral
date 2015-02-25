# Copyright 2013 - Mirantis, Inc.
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
from mistral import utils
from mistral.workbook import parser as spec_parser


STD_WF_PATH = '../resources/workflows'


def register_standard_workflows():
    workflow_paths = utils.get_file_list(STD_WF_PATH)

    for wf_path in workflow_paths:
        workflow_definition = open(wf_path).read()
        update_workflows(workflow_definition, scope='public')


def sync_db():
    register_standard_workflows()


def create_workflows(definition, scope='private'):
    wf_list_spec = spec_parser.get_workflow_list_spec_from_yaml(definition)

    db_wfs = []

    with db_api.transaction():
        for wf_spec in wf_list_spec.get_workflows():
            db_wfs.append(_create_workflow(wf_spec, definition, scope))

    return db_wfs


def update_workflows(definition, scope='private'):
    wf_list_spec = spec_parser.get_workflow_list_spec_from_yaml(definition)

    db_wfs = []

    with db_api.transaction():
        for wf_spec in wf_list_spec.get_workflows():
            db_wfs.append(_create_or_update_workflow(
                wf_spec,
                definition,
                scope
            ))

    return db_wfs


def _get_workflow_values(wf_spec, definition, scope):
    values = {
        'name': wf_spec.get_name(),
        'tags': wf_spec.get_tags(),
        'definition': definition,
        'spec': wf_spec.to_dict(),
        'scope': scope
    }

    return values


def _create_workflow(wf_spec, definition, scope):
    return db_api.create_workflow_definition(
        _get_workflow_values(wf_spec, definition, scope)
    )


def _create_or_update_workflow(wf_spec, definition, scope):
    values = _get_workflow_values(wf_spec, definition, scope)

    return db_api.create_or_update_workflow_definition(values['name'], values)
