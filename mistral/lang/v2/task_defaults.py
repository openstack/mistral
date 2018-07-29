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

from mistral.lang import types
from mistral.lang.v2 import base
from mistral.lang.v2 import on_clause
from mistral.lang.v2 import policies
from mistral.lang.v2 import retry_policy


# TODO(rakhmerov): This specification should be broken into two separate
# specs for direct and reverse workflows. It's weird to combine them into
# one because they address different use cases.


class TaskDefaultsSpec(base.BaseSpec):
    # See http://json-schema.org
    _schema = {
        "type": "object",
        "properties": {
            "retry": retry_policy.RetrySpec.get_schema(),
            "wait-before": types.EXPRESSION_OR_POSITIVE_INTEGER,
            "wait-after": types.EXPRESSION_OR_POSITIVE_INTEGER,
            "timeout": types.EXPRESSION_OR_POSITIVE_INTEGER,
            "pause-before": types.EXPRESSION_OR_BOOLEAN,
            "concurrency": types.EXPRESSION_OR_POSITIVE_INTEGER,
            "on-complete": on_clause.OnClauseSpec.get_schema(),
            "on-success": on_clause.OnClauseSpec.get_schema(),
            "on-error": on_clause.OnClauseSpec.get_schema(),
            "safe-rerun": types.EXPRESSION_OR_BOOLEAN,
            "requires": {
                "oneOf": [types.NONEMPTY_STRING, types.UNIQUE_STRING_LIST]
            }
        },
        "additionalProperties": False
    }

    @classmethod
    def get_schema(cls, includes=['definitions']):
        return super(TaskDefaultsSpec, cls).get_schema(includes)

    def __init__(self, data, validate):
        super(TaskDefaultsSpec, self).__init__(data, validate)

        self._policies = self._group_spec(
            policies.PoliciesSpec,
            'retry',
            'wait-before',
            'wait-after',
            'timeout',
            'pause-before',
            'concurrency'
        )

        on_spec_cls = on_clause.OnClauseSpec

        self._on_complete = self._spec_property('on-complete', on_spec_cls)
        self._on_success = self._spec_property('on-success', on_spec_cls)
        self._on_error = self._spec_property('on-error', on_spec_cls)

        self._safe_rerun = data.get('safe-rerun')

        # TODO(rakhmerov): 'requires' should reside in a different spec for
        # reverse workflows.
        self._requires = data.get('requires', [])

    def validate_schema(self):
        super(TaskDefaultsSpec, self).validate_schema()

        self.validate_expr(self._data.get('safe-rerun', {}))

    def validate_semantics(self):
        # Validate YAQL expressions.
        self._validate_transitions(self._on_complete)
        self._validate_transitions(self._on_success)
        self._validate_transitions(self._on_error)

    def _validate_transitions(self, on_clause_spec):
        val = on_clause_spec.get_next() if on_clause_spec else []

        if not val:
            return

        [self.validate_expr(t)
            for t in ([val] if isinstance(val, six.string_types) else val)]

    def get_policies(self):
        return self._policies

    def get_on_complete(self):
        return self._on_complete

    def get_on_success(self):
        return self._on_success

    def get_on_error(self):
        return self._on_error

    def get_safe_rerun(self):
        return self._safe_rerun

    def get_requires(self):
        if isinstance(self._requires, six.string_types):
            return [self._requires]

        return self._requires
