# Copyright 2014 - Mirantis, Inc.
# Copyright 2015 - StackStorm, Inc.
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

from mistral.workbook.v2 import actions as act
from mistral.workbook.v2 import base
from mistral.workbook.v2 import workflows as wf


class WorkbookSpec(base.BaseSpec):
    # See http://json-schema.org

    _action_schema = act.ActionSpec.get_schema(includes=None)

    _workflow_schema = wf.WorkflowSpec.get_schema(includes=None)

    _schema = {
        "type": "object",
        "properties": {
            "version": {"enum": ["2.0", 2.0]},
            "actions": {
                "type": "object",
                "minProperties": 1,
                "patternProperties": {
                    "version": {"enum": ["2.0", 2.0]},
                    "^(?!version)\w+$": _action_schema
                }
            },
            "workflows": {
                "type": "object",
                "minProperties": 1,
                "patternProperties": {
                    "version": {"enum": ["2.0", 2.0]},
                    "^(?!version)\w+$": _workflow_schema
                }
            }
        },
        "additionalProperties": False
    }

    def __init__(self, data):
        super(WorkbookSpec, self).__init__(data)

        self._inject_version(['actions', 'workflows', 'triggers'])

        self._name = data['name']
        self._description = data.get('description')
        self._tags = data.get('tags', [])
        self._actions = self._spec_property('actions', act.ActionSpecList)
        self._workflows = self._spec_property('workflows', wf.WorkflowSpecList)

    def get_name(self):
        return self._name

    def get_description(self):
        return self._description

    def get_tags(self):
        return self._tags

    def get_actions(self):
        return self._actions

    def get_workflows(self):
        return self._workflows
