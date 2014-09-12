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


class ActionSpec(base.BaseSpec):
    # See http://json-schema.org
    _schema = {
        "type": "object",
        "properties": {
            "version": {"type": "string"},
            "name": {"type": "string"},
            "class": {"type": "string"},
            "namespace": {"type": "string"},
            "base-parameters": {"type": "object"},
            "parameters": {"type": "array"},
            "output": {"type": ["string", "object", "array", "null"]},
        },
        "required": ["name", "class", "namespace"],
        "additionalProperties": False
    }

    def __init__(self, data):
        super(ActionSpec, self).__init__(data)

        self.name = data['name']
        self.clazz = data['class']
        self.namespace = data['namespace']
        self.base_parameters = data.get('base-parameters', {})
        self.parameters = data.get('parameters', {})
        self.output = data.get('output')


class ActionSpecList(base.BaseSpecList):
    item_class = ActionSpec
