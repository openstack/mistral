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

import six

from mistral import utils
from mistral.workbook import types
from mistral.workbook.v2 import base


class ActionSpec(base.BaseSpec):
    # See http://json-schema.org
    _schema = {
        "type": "object",
        "properties": {
            "base": types.NONEMPTY_STRING,
            "base-input": types.NONEMPTY_DICT,
            "input": types.UNIQUE_STRING_OR_ONE_KEY_DICT_LIST,
            "output": types.ANY_NULLABLE,
        },
        "required": ["base"],
        "additionalProperties": False
    }

    def __init__(self, data):
        super(ActionSpec, self).__init__(data)

        self._name = data['name']
        self._description = data.get('description')
        self._tags = data.get('tags', [])
        self._base = data['base']
        self._base_input = data.get('base-input', {})
        self._input = utils.get_input_dict(data.get('input', []))
        self._output = data.get('output')

        self._base, _input = self._parse_cmd_and_input(self._base)

        utils.merge_dicts(self._base_input, _input)

    def validate_schema(self):
        super(ActionSpec, self).validate_schema()

        # Validate YAQL expressions.
        inline_params = self._parse_cmd_and_input(self._data.get('base'))[1]
        self.validate_yaql_expr(inline_params)

        self.validate_yaql_expr(self._data.get('base-input', {}))

        if isinstance(self._data.get('output'), six.string_types):
            self.validate_yaql_expr(self._data.get('output'))

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


class ActionListSpec(base.BaseListSpec):
    item_class = ActionSpec

    def get_actions(self):
        return self.get_items()
