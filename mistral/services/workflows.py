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
from mistral.workbook import parser as spec_parser


def create_workflow(values):
    _update_specification(values)

    with db_api.transaction():
        wf_db = db_api.create_workflow(values)

    return wf_db


def update_workflow(workflow_name, values):
    _update_specification(values)

    with db_api.transaction():
        wf_db = db_api.update_workflow(workflow_name, values)

    return wf_db


def _update_specification(values):
    # No need to do anything if specification gets pushed explicitly.
    if 'spec' in values:
        return

    if 'definition' in values:
        spec = spec_parser.get_workflow_spec_from_yaml(values['definition'])
        values['spec'] = spec.to_dict()
