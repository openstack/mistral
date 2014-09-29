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

from oslo.config import cfg

from mistral import context
from mistral.db.v2 import api as db_api
from mistral.services import trusts
from mistral.workbook import parser as spec_parser


def create_workflows(definition):
    wf_list_spec = spec_parser.get_workflow_list_spec_from_yaml(definition)

    db_wfs = []

    with db_api.transaction():
        for wf_spec in wf_list_spec.get_workflows():
            db_wfs.append(create_workflow(wf_spec, definition))

    return db_wfs


def update_workflows(definition):
    wf_list_spec = spec_parser.get_workflow_list_spec_from_yaml(definition)

    db_wfs = []

    with db_api.transaction():
        for wf_spec in wf_list_spec.get_workflows():
            db_wfs.append(create_or_update_workflow(wf_spec, definition))

    return db_wfs


def create_workflow(wf_spec, definition):
    values = {
        'name': wf_spec.get_name(),
        'tags': wf_spec.get_tags(),
        'definition': definition,
        'spec': wf_spec.to_dict()
    }

    _add_security_info(values)

    return db_api.create_workflow(values)


def create_or_update_workflow(wf_spec, definition):
    values = {
        'name': wf_spec.get_name(),
        'tags': wf_spec.get_tags(),
        'definition': definition,
        'spec': wf_spec.to_dict()
    }

    _add_security_info(values)

    return db_api.create_or_update_workflow(values['name'], values)


def _add_security_info(values):
    if cfg.CONF.pecan.auth_enable:
        values.update({
            'trust_id': trusts.create_trust().id,
            'project_id': context.ctx().project_id
        })
