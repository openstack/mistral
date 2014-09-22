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

from mistral.workbook import base
from mistral.workbook.v2 import actions as act
from mistral.workbook.v2 import triggers as tr
from mistral.workbook.v2 import workflows as wf


class WorkbookSpec(base.BaseSpec):
    # See http://json-schema.org
    _schema = {
        "type": "object",
        "properties": {
            "version": {"value": "2.0"},
            "name": {"type": "string"},
            "description": {"type": "string"},
            "tags": {"type": "array"},
            "actions": {"type": "object"},
            "workflows": {"type": "object"},
            "triggers": {"type": "object"}
        },
        "required": ["name"],
        "additionalProperties": False
    }

    _version = '2.0'

    def __init__(self, data):
        super(WorkbookSpec, self).__init__(data)

        self._inject_version(['actions', 'workflows', 'triggers'])

        self._name = data['name']
        self._description = data.get('description')
        self._tags = data.get('tags', [])
        self._actions = self._spec_property('actions', act.ActionSpecList)
        self._workflows = \
            self._spec_property('workflows', wf.WorkflowSpecList)
        self._triggers = self._spec_property('triggers', tr.TriggerSpecList)

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

    def get_triggers(self):
        return self._triggers
