# Copyright 2014 - Mirantis, Inc.
# Copyright 2015 - StackStorm, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

import six

from mistral.workbook import types
from mistral.workbook.v2 import base


class RetrySpec(base.BaseSpec):
    # See http://json-schema.org
    _retry_dict_schema = {
        "type": "object",
        "properties": {
            "count": {
                "oneOf": [
                    types.YAQL,
                    types.POSITIVE_INTEGER
                ]
            },
            "break-on": types.YAQL,
            "continue-on": types.YAQL,
            "delay": {
                "oneOf": [
                    types.YAQL,
                    types.POSITIVE_INTEGER
                ]
            },
        },
        "required": ["delay", "count"],
        "additionalProperties": False
    }

    _schema = {
        "oneOf": [
            _retry_dict_schema,
            types.NONEMPTY_STRING
        ]
    }

    @classmethod
    def get_schema(cls, includes=['definitions']):
        return super(RetrySpec, cls).get_schema(includes)

    def __init__(self, data):
        data = self._transform_retry_one_line(data)
        super(RetrySpec, self).__init__(data)

        self._break_on = data.get('break-on')
        self._count = data.get('count')
        self._continue_on = data.get('continue-on')
        self._delay = data['delay']

    def _transform_retry_one_line(self, retry):
        if isinstance(retry, six.string_types):
            _, params = self._parse_cmd_and_input(retry)
            return params

        return retry

    def validate_schema(self):
        super(RetrySpec, self).validate_schema()

        # Validate YAQL expressions.
        self.validate_yaql_expr(self._data.get('count'))
        self.validate_yaql_expr(self._data.get('delay'))
        self.validate_yaql_expr(self._data.get('break-on'))
        self.validate_yaql_expr(self._data.get('continue-on'))

    def get_count(self):
        return self._count

    def get_break_on(self):
        return self._break_on

    def get_continue_on(self):
        return self._continue_on

    def get_delay(self):
        return self._delay
