# Copyright 2014 - Mirantis, Inc.
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

from mistral import utils
from mistral.workbook import base
from mistral.workbook.v2 import retry_policy


class TaskPoliciesSpec(base.BaseSpec):
    # See http://json-schema.org
    _policies_schema = {
        "type": "object",
        "properties": {
            "retry": {"type": ["object", "null"]},
            "wait-before": {
                "oneOf": [
                    {"$ref": "#/definitions/yaql"},
                    {"$ref": "#/definitions/positiveInteger"}
                ]
            },
            "wait-after": {
                "oneOf": [
                    {"$ref": "#/definitions/yaql"},
                    {"$ref": "#/definitions/positiveInteger"}
                ]
            },
            "timeout": {
                "oneOf": [
                    {"$ref": "#/definitions/yaql"},
                    {"$ref": "#/definitions/positiveInteger"}
                ]
            },
            "pause-before": {
                "oneOf": [
                    {"$ref": "#/definitions/yaql"},
                    {"type": "boolean"}
                ]
            },
            "concurrency": {
                "oneOf": [
                    {"$ref": "#/definitions/yaql"},
                    {"$ref": "#/definitions/positiveInteger"}
                ]
            },
        },
        "additionalProperties": False,
        "definitions": {
            "positiveInteger": {
                "type": "integer",
                "minimum": 0
            }
        },
    }

    _schema = utils.merge_dicts(_policies_schema, base.BaseSpec._yaql_schema)

    def __init__(self, data):
        super(TaskPoliciesSpec, self).__init__(data)

        self._retry = self._spec_property('retry', retry_policy.RetrySpec)
        self._wait_before = data.get("wait-before", 0)
        self._wait_after = data.get("wait-after", 0)
        self._timeout = data.get("timeout", 0)
        self._pause_before = data.get("pause-before", False)
        self._concurrency = data.get("concurrency", 0)

    def get_retry(self):
        return self._retry

    def get_wait_before(self):
        return self._wait_before

    def get_wait_after(self):
        return self._wait_after

    def get_timeout(self):
        return self._timeout

    def get_pause_before(self):
        return self._pause_before

    def get_concurrency(self):
        return self._concurrency
