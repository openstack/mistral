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
from mistral.workbook.v1 import namespaces
from mistral.workbook.v1 import workflow


class WorkbookSpec(base.BaseSpec):
    # See http://json-schema.org
    _schema = {
        "type": "object",
        "properties": {
            "Namespaces": {"type": "object"},
            "Workflow": {"type": "object"},
            "Triggers": {"type": "object"}
        },
        "required": ["Workflow"],
        "additionalProperties": False
    }

    def __init__(self, doc):
        super(WorkbookSpec, self).__init__(doc)

        self.namespaces = self._spec_property('Namespaces',
                                              namespaces.NamespaceSpecList)
        self.workflow = self._spec_property('Workflow', workflow.WorkflowSpec)
        self.tasks = self.workflow.tasks

    def get_triggers(self):
        triggers_from_data = self._data.get("Triggers", None)

        if not triggers_from_data:
            return []

        triggers = []
        for name in triggers_from_data:
            trigger_dict = {'name': name}
            trigger_dict.update(triggers_from_data[name])
            triggers.append(trigger_dict)

        return triggers

    def get_action(self, full_action_name):
        if not self.namespaces:
            return None

        if full_action_name.find(".") == -1:
            return {}

        ns_name = full_action_name.split('.')[0]
        action_name = full_action_name.split('.')[1]

        if ns_name in self.namespaces.item_keys():
            return self.namespaces[ns_name].actions.get(action_name)

    def get_actions(self, namespace_name):
        return self.namespaces.get(namespace_name).actions

    def get_trigger_task_name(self, trigger_name):
        trigger = self._data["Triggers"].get(trigger_name)
        return trigger.get('tasks') if trigger else ""
