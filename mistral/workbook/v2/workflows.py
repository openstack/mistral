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
from mistral.workbook import base
from mistral.workbook.v2 import tasks


class WorkflowSpec(base.BaseSpec):
    # See http://json-schema.org
    _schema = {
        "type": "object",
        "properties": {
            "Version": {"type": "string"},
            "name": {"type": "string"},
            "type": {"enum": ["reverse", "direct"]},
            "start-task": {"type": "string"},
            "policies": {"type": ["object", "null"]},
            "parameters": {"type": ["array", "null"]},
            "output": {"type": ["string", "object", "array", "null"]},
            "tasks": {"type": "object"},
        },
        "required": ["Version", "name", "type", "tasks"],
        "additionalProperties": False
    }

    _version = '2.0'

    def __init__(self, data):
        super(WorkflowSpec, self).__init__(data)

        self._name = data['name']
        self._type = data['type']
        self._parameters = data.get('parameters')
        self._output = data.get('output')
        self._start_task_name = data.get('start-task')
        # TODO(rakhmerov): Build workflow policies specification.
        self._policies = None
        self._tasks = self._spec_property('tasks', tasks.TaskSpecList)

    def validate(self):
        super(WorkflowSpec, self).validate()

        if self._data['type'] == 'direct':
            if 'start-task' not in self._data:
                msg = "Direct workflow 'start-task' property is not defined."
                raise exc.InvalidModelException(msg)
            elif self._data['start-task'] not in self._data['tasks'].keys():
                msg = "'start-task' property of direct workflow is invalid."
                raise exc.InvalidModelException(msg)

    def get_name(self):
        return self._name

    def get_type(self):
        return self._type

    def get_parameters(self):
        return self._parameters

    def get_output(self):
        return self._output

    def get_start_task_name(self):
        return self._start_task_name

    def get_policies(self):
        return self._policies

    def get_tasks(self):
        return self._tasks


class WorkflowSpecList(base.BaseSpecList):
    item_class = WorkflowSpec
    _version = '2.0'
