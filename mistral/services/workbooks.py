# -*- coding: utf-8 -*-
#
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
from mistral.db.v1 import api as db_api_v1
from mistral.db.v2 import api as db_api_v2
from mistral.services import triggers
from mistral.services import trusts
from mistral.workbook import parser as spec_parser


def create_workbook_v1(values):
    _add_security_info(values)

    return db_api_v1.workbook_create(values)


def update_workbook_v1(workbook_name, values):
    wb_db = db_api_v1.workbook_update(workbook_name, values)

    if 'definition' in values:
        triggers.create_associated_triggers(wb_db)

    return wb_db


def create_workbook_v2(values):
    _add_security_info(values)
    _update_specification(values)
    _infer_data_from_specification(values)

    with db_api_v2.transaction():
        wb_db = db_api_v2.create_workbook(values)

        _on_workbook_update(wb_db, values)

    return wb_db


def update_workbook_v2(values):
    _update_specification(values)
    _infer_data_from_specification(values)

    with db_api_v2.transaction():
        wb_db = db_api_v2.update_workbook(values['name'], values)

        _on_workbook_update(wb_db, values)

    return wb_db


def _on_workbook_update(wb_db, values):
    wb_spec = spec_parser.get_workbook_spec(values['spec'])

    _create_or_update_actions(wb_db, wb_spec.get_actions())
    _create_or_update_workflows(wb_db, wb_spec.get_workflows())


def _create_or_update_actions(wb_db, actions_spec):
    if actions_spec:
        for action_spec in actions_spec:
            action_name = '%s.%s' % (wb_db.name, action_spec.get_name())

            values = {
                'name': action_name,
                'spec': action_spec.to_dict(),
                'is_system': False,
                'scope': wb_db.scope,
                'trust_id': wb_db.trust_id,
                'project_id': wb_db.project_id
            }

            db_api_v2.create_or_update_action(action_name, values)


def _create_or_update_workflows(wb_db, workflows_spec):
    if workflows_spec:
        for wf_spec in workflows_spec:
            wf_name = '%s.%s' % (wb_db.name, wf_spec.get_name())

            values = {
                'name': wf_name,
                'spec': wf_spec.to_dict(),
                'scope': wb_db.scope,
                'trust_id': wb_db.trust_id,
                'project_id': wb_db.project_id
            }

            db_api_v2.create_or_update_workflow(wf_name, values)


def _add_security_info(values):
    if cfg.CONF.pecan.auth_enable:
        values.update({
            'trust_id': trusts.create_trust().id,
            'project_id': context.ctx().project_id
        })


def _update_specification(values):
    # No need to do anything if specification gets pushed explicitly.
    if 'spec' in values:
        return

    if 'definition' in values:
        spec = spec_parser.get_workbook_spec_from_yaml(values['definition'])
        values['spec'] = spec.to_dict()


def _infer_data_from_specification(values):
    values['name'] = values['spec']['name']
    values['tags'] = values['spec'].get('tags', [])
