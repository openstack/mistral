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

from mistral.workbook import types
from mistral.workbook.v2 import base
from mistral.workbook.v2 import policies
from mistral.workbook.v2 import tasks


direct_wf_ts = tasks.DirectWorkflowTaskSpec


class TaskDefaultsSpec(base.BaseSpec):
    # See http://json-schema.org
    _task_policies_schema = policies.PoliciesSpec.get_schema(
        includes=None)

    _on_clause_type = {
        "oneOf": [
            types.NONEMPTY_STRING,
            types.UNIQUE_STRING_OR_YAQL_CONDITION_LIST
        ]
    }

    _schema = {
        "type": "object",
        "properties": {
            "retry": policies.RETRY_SCHEMA,
            "wait-before": policies.WAIT_BEFORE_SCHEMA,
            "wait-after": policies.WAIT_AFTER_SCHEMA,
            "timeout": policies.TIMEOUT_SCHEMA,
            "pause-before": policies.PAUSE_BEFORE_SCHEMA,
            "concurrency": policies.CONCURRENCY_SCHEMA,
            "on-complete": _on_clause_type,
            "on-success": _on_clause_type,
            "on-error": _on_clause_type,
            "requires": {
                "oneOf": [types.NONEMPTY_STRING, types.UNIQUE_STRING_LIST]
            }
        },
        "additionalProperties": False
    }

    @classmethod
    def get_schema(cls, includes=['definitions']):
        return super(TaskDefaultsSpec, cls).get_schema(includes)

    def __init__(self, data):
        super(TaskDefaultsSpec, self).__init__(data)

        self._policies = self._group_spec(
            policies.PoliciesSpec,
            'retry',
            'wait-before',
            'wait-after',
            'timeout',
            'pause-before',
            'concurrency'
        )
        self._on_complete = direct_wf_ts.prepare_on_clause(
            self._as_list_of_tuples('on-complete')
        )
        self._on_success = direct_wf_ts.prepare_on_clause(
            self._as_list_of_tuples('on-success')
        )
        self._on_error = direct_wf_ts.prepare_on_clause(
            self._as_list_of_tuples('on-error')
        )
        self._requires = data.get('requires', [])

    def validate_schema(self):
        super(TaskDefaultsSpec, self).validate_schema()

        # Validate YAQL expressions.
        self._validate_transitions('on-complete')
        self._validate_transitions('on-success')
        self._validate_transitions('on-error')

    def _validate_transitions(self, on_clause):
        val = self._data.get(on_clause, [])

        [self.validate_yaql_expr(t)
         for t in ([val] if isinstance(val, six.string_types) else val)]

    def get_policies(self):
        return self._policies

    def get_on_complete(self):
        return self._on_complete

    def get_on_success(self):
        return self._on_success

    def get_on_error(self):
        return self._on_error

    def get_requires(self):
        if isinstance(self._requires, six.string_types):
            return [self._requires]

        return self._requires
