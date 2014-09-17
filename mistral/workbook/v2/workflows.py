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
from mistral.workbook.v2 import tasks


class WorkflowSpec(base.BaseSpec):
    # See http://json-schema.org
    _schema = {
        "type": "object",
        "properties": {
            "version": {"type": "string"},
            "name": {"type": "string"},
            "description": {"type": "string"},
            "type": {"enum": ["reverse", "direct"]},
            "policies": {"type": ["object", "null"]},
            "on-task-complete": {"type": ["array", "null"]},
            "on-task-success": {"type": ["array", "null"]},
            "on-task-error": {"type": ["array", "null"]},
            "parameters": {"type": ["array", "null"]},
            "output": {"type": ["string", "object", "array", "null"]},
            "tasks": {"type": "object"},
        },
        "required": ["version", "name", "type", "tasks"],
        "additionalProperties": False
    }

    _version = '2.0'

    def __init__(self, data):
        super(WorkflowSpec, self).__init__(data)

        self._name = data['name']
        self._description = data.get('description')
        self._type = data['type']
        self._parameters = data.get('parameters', {})
        self._output = data.get('output', {})
        # TODO(rakhmerov): Build workflow policies specification.
        self._policies = None
        self._on_task_complete = self._as_list_of_tuples("on-task-complete")
        self._on_task_success = self._as_list_of_tuples("on-task-success")
        self._on_task_error = self._as_list_of_tuples("on-task-error")

        self._tasks = self._spec_property('tasks', tasks.TaskSpecList)

    def get_name(self):
        return self._name

    def get_description(self):
        return self._description

    def get_type(self):
        return self._type

    def get_parameters(self):
        return self._parameters

    def get_output(self):
        return self._output

    def get_policies(self):
        return self._policies

    def get_on_task_complete(self):
        return self._on_task_complete

    def get_on_task_success(self):
        return self._on_task_success

    def get_on_task_error(self):
        return self._on_task_error

    def get_tasks(self):
        return self._tasks


class WorkflowSpecList(base.BaseSpecList):
    item_class = WorkflowSpec
    _version = '2.0'
