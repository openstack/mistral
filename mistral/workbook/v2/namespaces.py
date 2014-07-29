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
from mistral.workbook.v2 import actions


# TODO(rakhmerov): It currently duplicates the method in ../v1/namespaces.py
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
            "name": {"type": "string"},
            "class": {"type": ["string", "null"]},
            "base-parameters": {"type": ["object", "null"]},
            "actions": {"type": "object"}
        },
        "required": ["name", "actions"],
        "additionalProperties": False
    }

    _version = '2.0'

    def __init__(self, data):
        super(NamespaceSpec, self).__init__(data)

        self._name = data['name']
        self._clazz = data.get('class')
        self._base_parameters = data.get('base-parameters')
        self._parameters = data.get('parameters')

        for _, action in data['actions'].iteritems():
            action['namespace'] = self._name

            if 'class' not in action:
                action['class'] = self._clazz

            merge_base_parameters(action, self._base_parameters)

        self._actions = self._spec_property('actions', actions.ActionSpecList)

    def get_name(self):
        return self._name

    def get_class(self):
        return self._clazz

    def get_base_parameters(self):
        return self._base_parameters

    def get_parameters(self):
        return self._parameters

    def get_actions(self):
        return self._actions


class NamespaceSpecList(base.BaseSpecList):
    item_class = NamespaceSpec
