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

from mistral import utils
from mistral.workbook import base
from mistral.workbook.v1 import actions


def merge_base_parameters(action, ns_base_parameters):
    if not ns_base_parameters:
        return

    if 'base-parameters' not in action:
        action['base-parameters'] = ns_base_parameters
        return

    action_base_parameters = action['base-parameters']

    utils.merge_dicts(action_base_parameters, ns_base_parameters)


class NamespaceSpec(base.BaseSpec):
    # See http://json-schema.org
    _schema = {
        "type": "object",
        "properties": {
            "version": {"type": "string"},
            "name": {"type": "string"},
            "class": {"type": ["string", "null"]},
            "base-parameters": {"type": ["object", "null"]},
            "actions": {"type": "object"}
        },
        "required": ["name", "actions"],
        "additionalProperties": False
    }

    def __init__(self, data):
        super(NamespaceSpec, self).__init__(data)

        self.name = data['name']
        self.clazz = data.get('class')
        self.base_parameters = data.get('base-parameters')
        self.parameters = data.get('parameters')

        for _, action in data['actions'].iteritems():
            action['namespace'] = self.name

            if 'class' not in action:
                action['class'] = self.clazz

            merge_base_parameters(action, self.base_parameters)

        self.actions = actions.ActionSpecList(data['actions'])


class NamespaceSpecList(base.BaseSpecList):
    item_class = NamespaceSpec
