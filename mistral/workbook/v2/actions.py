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

# TODO(rakhmerov): In progress.


class ActionSpec(base.BaseSpec):
    # See http://json-schema.org
    _schema = {
        "type": "object",
        "properties": {
            "Version": {"type": "string"},
            "name": {"type": "string"},
            "class": {"type": "string"},
            "namespace": {"type": "string"},
            "base-parameters": {"type": "object"},
            "parameters": {"type": "array"},
            "output": {"type": ["string", "object", "array", "null"]},
        },
        "required": ["Version", "name", "class", "namespace"],
        "additionalProperties": False
    }

    _version = '2.0'

    def __init__(self, data):
        super(ActionSpec, self).__init__(data)

        self._name = data['name']
        self._class = data['class']
        self._namespace = data['namespace']
        self._base_parameters = data.get('base-parameters', {})
        self._parameters = data.get('parameters', {})
        self._output = data.get('output')

    def get_name(self):
        return self._name

    def get_class(self):
        return self._class

    def get_namespace(self):
        return self._namespace

    def get_base_parameters(self):
        return self._base_parameters

    def get_parameters(self):
        return self._parameters

    def get_output(self):
        return self._output


class ActionSpecList(base.BaseSpecList):
    item_class = ActionSpec
    _version = '2.0'
