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

from mistral import exceptions as exc
from mistral import utils
from mistral.workbook import base


class ActionSpec(base.BaseSpec):
    # See http://json-schema.org
    _schema = {
        "type": "object",
        "properties": {
            "version": {"type": "string"},
            "name": {"type": "string"},
            "description": {"type": "string"},
            "tags": {"type": "array"},
            "base": {"type": "string"},
            "base-input": {"type": "object"},
            "input": {"type": "array"},
            "output": {"type": ["string", "object", "array", "null"]},
        },
        "required": ["version", "name", "base"],
        "additionalProperties": False
    }

    _version = '2.0'

    def __init__(self, data):
        super(ActionSpec, self).__init__(data)

        self._name = data['name']
        self._description = data.get('description')
        self._tags = data.get('tags', [])
        self._base = data['base']
        self._base_input = data.get('base-input', {})
        self._input = data.get('input', [])
        self._output = data.get('output')

        self._base, _input = self._parse_cmd_and_input(self._base)

        utils.merge_dicts(self._base_input, _input)

    def get_name(self):
        return self._name

    def get_description(self):
        return self._description

    def get_tags(self):
        return self._tags

    def get_base(self):
        return self._base

    def get_base_input(self):
        return self._base_input

    def get_input(self):
        return self._input

    def get_output(self):
        return self._output


class ActionSpecList(base.BaseSpecList):
    item_class = ActionSpec
    _version = '2.0'


class ActionListSpec(base.BaseSpec):
    # See http://json-schema.org
    _schema = {
        "type": "object",
        "properties": {
            "version": {"type": "string"},
        },
        "required": ["version"],
        "additionalProperties": True
    }

    _version = '2.0'

    def __init__(self, data):
        super(ActionListSpec, self).__init__(data)

        self._actions = []

        for k, v in data.iteritems():
            if k == 'version':
                continue

            v['name'] = k
            self._inject_version([k])

            self._actions.append(ActionSpec(v))

    def validate(self):
        if len(self._data.keys()) < 2:
            raise exc.InvalidModelException(
                'At least one action must be in action list [data=%s]' %
                self._data
            )

    def get_actions(self):
        return self._actions
