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


class TaskSpec(base.BaseSpec):
    # See http://json-schema.org
    _schema = {
        "type": "object",
        "properties": {
            "version": {"type": "string"},
            "name": {"type": "string"},
            "action": {"type": ["string", "null"]},
            "parameters": {"type": ["object", "null"]},
            "publish": {"type": ["object", "null"]},
            "retry": {"type": ["object", "null"]},
            "requires": {"type": ["object", "string", "array", "null"]},
            "on-finish": {"type": ["string", "array", "null"]},
            "on-success": {"type": ["string", "array", "null"]},
            "on-error": {"type": ["string", "array", "null"]}
        },
        "required": ["name", "action"],
        "additionalProperties": False
    }

    def __init__(self, data):
        super(TaskSpec, self).__init__(data)

        self._prepare(data)

        self.requires = data.get('requires')
        self.action = data['action']
        self.name = data['name']
        self.parameters = data.get('parameters', {})

    def _prepare(self, task):
        if task:
            req = task.get("requires", {})

            if req and isinstance(req, list):
                task["requires"] = dict(zip(req, [''] * len(req)))
            elif isinstance(req, dict):
                task['requires'] = req

    def get_property(self, property_name, default=None):
        return self._data.get(property_name, default)

    def get_requires(self):
        return self._as_dict('requires').keys()

    def get_on_error(self):
        return self._as_dict("on-error")

    def get_on_success(self):
        return self._as_dict("on-success")

    def get_on_finish(self):
        return self._as_dict("on-finish")

    def get_action_namespace(self):
        return self.action.split('.')[0]

    def get_action_name(self):
        return self.action.split('.')[1]

    def get_full_action_name(self):
        return self.action

    def is_retry_task(self):
        return self.get_property("retry") is not None

    def get_retry_parameters(self):
        iterations = 0
        break_on = None
        delay = 0
        retry = self.get_property("retry")

        if retry:
            if "count" in retry:
                iterations = retry["count"]
            if "break-on" in retry:
                break_on = retry["break-on"]
            if "delay" in retry:
                delay = retry["delay"]

        return iterations, break_on, delay


class TaskSpecList(base.BaseSpecList):
    item_class = TaskSpec
