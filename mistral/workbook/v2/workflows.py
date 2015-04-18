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

from mistral import exceptions as exc
from mistral import utils
from mistral.workbook import types
from mistral.workbook.v2 import base
from mistral.workbook.v2 import task_defaults
from mistral.workbook.v2 import tasks


class WorkflowSpec(base.BaseSpec):
    # See http://json-schema.org

    _direct_task_schema = tasks.DirectWorkflowTaskSpec.get_schema(
        includes=None)

    _reverse_task_schema = tasks.ReverseWorkflowTaskSpec.get_schema(
        includes=None)

    _task_defaults_schema = task_defaults.TaskDefaultsSpec.get_schema(
        includes=None)

    _schema = {
        "type": "object",
        "properties": {
            "type": types.WORKFLOW_TYPE,
            "task-defaults": _task_defaults_schema,
            "input": types.UNIQUE_STRING_OR_ONE_KEY_DICT_LIST,
            "output": types.NONEMPTY_DICT,
            "tasks": {
                "type": "object",
                "minProperties": 1,
                "patternProperties": {
                    "^\w+$": {
                        "anyOf": [
                            _direct_task_schema,
                            _reverse_task_schema
                        ]
                    }
                }
            },
        },
        "required": ["tasks"],
        "additionalProperties": False
    }

    def __init__(self, data):
        super(WorkflowSpec, self).__init__(data)

        self._name = data['name']
        self._description = data.get('description')
        self._tags = data.get('tags', [])
        self._type = data['type'] if 'type' in data else "direct"
        self._input = utils.get_input_dict(data.get('input', []))
        self._output = data.get('output', {})

        self._task_defaults = self._spec_property(
            'task-defaults',
            task_defaults.TaskDefaultsSpec
        )
        self._tasks = self._spec_property(
            'tasks',
            tasks.TaskSpecList.get_class(self._type)
        )

    def validate(self):
        super(WorkflowSpec, self).validate()

        if not self._data.get('tasks'):
            raise exc.InvalidModelException(
                "Workflow doesn't have any tasks [data=%s]" % self._data
            )

        # Validate YAQL expressions.
        self.validate_yaql_expr(self._data.get('output', {}))

    def get_name(self):
        return self._name

    def get_description(self):
        return self._description

    def get_tags(self):
        return self._tags

    def get_type(self):
        return self._type

    def get_input(self):
        return self._input

    def get_output(self):
        return self._output

    def get_task_defaults(self):
        return self._task_defaults

    def get_tasks(self):
        return self._tasks


class WorkflowSpecList(base.BaseSpecList):
    item_class = WorkflowSpec


class WorkflowListSpec(base.BaseListSpec):
    item_class = WorkflowSpec

    def get_workflows(self):
        return self.get_items()
