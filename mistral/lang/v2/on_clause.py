# Copyright 2014 - Mirantis, Inc.
# Copyright 2015 - StackStorm, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
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

from mistral.lang import types
from mistral.lang.v2 import base
from mistral.lang.v2 import publish

NEXT_TASK = {
    "oneOf": [
        {
            "type": "string",
            "pattern": "^\S+$",
            "description": "Task name (e.g.: `task1`)"
        },
        {
            "type": "string",
            "pattern": "^\w+ \w+=(.*)$",
            "description": "Task name with dict parameter "
                           "(e.g.: `fail msg=\"test\"`, "
                           "`fail msg=<% task() %>`)"
        },
        {
            "type": "string",
            "pattern": "^\w+\\(\w+=(.*)\\)$",
            "description": "Task name with func parameter "
                           "(e.g.: `fail(msg=\"test\")`, "
                           "`fail(msg=<% task() %>)`)"
        }
    ]
}

TASK_WITH_EXPRESSION = {
    "type": "object",
    "minProperties": 1,
    "maxProperties": 1,
    "patternProperties": {
        x['pattern']: types.EXPRESSION for x in NEXT_TASK['oneOf']
    },
    "description": "All next task variants plus expression (e.g.: "
                   "`task1: <% $.vm_id != null %>`, "
                   "`fail(msg=\"test\"): <% $.vm_id != null %>`)."
}

LIST_OF_TASKS = {
    "type": "array",
    "items": {
        "oneOf": [
            NEXT_TASK,
            TASK_WITH_EXPRESSION
        ]
    },
    "uniqueItems": True,
    "minItems": 1
}

ADVANCED_PUBLISHING_DICT = {
    "type": "object",
    "minProperties": 1,
    "properties": {
        "publish": publish.PublishSpec.get_schema(),
        "next": {
            "oneOf": [
                NEXT_TASK,
                TASK_WITH_EXPRESSION,
                LIST_OF_TASKS
            ]
        }
    },
    "additionalProperties": False
}


class OnClauseSpec(base.BaseSpec):
    _schema = {
        "oneOf": [
            NEXT_TASK,
            TASK_WITH_EXPRESSION,
            LIST_OF_TASKS,
            ADVANCED_PUBLISHING_DICT
        ]
    }

    def __init__(self, data, validate):
        super(OnClauseSpec, self).__init__(data, validate)

        if not isinstance(data, dict):
            # Old simple schema.
            self._publish = None
            self._next = prepare_next_clause(data)
        else:
            # New advanced schema.
            self._publish = self._spec_property('publish', publish.PublishSpec)
            self._next = prepare_next_clause(data.get('next'))

    @classmethod
    def get_schema(cls, includes=['definitions']):
        return super(OnClauseSpec, cls).get_schema(includes)

    def get_publish(self):
        return self._publish

    def get_next(self):
        return self._next


def _as_list_of_tuples(data):
    if not data:
        return []

    if isinstance(data, six.string_types):
        return [_as_tuple(data)]

    return [_as_tuple(item) for item in data]


def _as_tuple(val):
    return list(val.items())[0] if isinstance(val, dict) else (val, '')


def prepare_next_clause(next_clause):
    list_of_tuples = _as_list_of_tuples(next_clause)

    for i, task in enumerate(list_of_tuples):
        task_name, params = OnClauseSpec._parse_cmd_and_input(task[0])

        list_of_tuples[i] = (task_name, task[1], params)

    return list_of_tuples
