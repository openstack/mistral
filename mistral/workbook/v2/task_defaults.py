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
from mistral.workbook.v2 import task_policies


class TaskDefaultsSpec(base.BaseSpec):
    # See http://json-schema.org
    _schema = {
        "type": "object",
        "properties": {
            "version": {"type": "string"},
            "policies": {"type": ["object", "null"]},
            "on-complete": {"type": ["array", "null"]},
            "on-success": {"type": ["array", "null"]},
            "on-error": {"type": ["array", "null"]},
        },
        "required": ["version"],
        "additionalProperties": False
    }

    _version = '2.0'

    def __init__(self, data):
        super(TaskDefaultsSpec, self).__init__(data)

        self._policies = self._spec_property(
            'policies',
            task_policies.TaskPoliciesSpec
        )
        self._on_complete = self._as_list_of_tuples("on-complete")
        self._on_success = self._as_list_of_tuples("on-success")
        self._on_error = self._as_list_of_tuples("on-error")

    def get_policies(self):
        return self._policies

    def get_on_complete(self):
        return self._on_complete

    def get_on_success(self):
        return self._on_success

    def get_on_error(self):
        return self._on_error
