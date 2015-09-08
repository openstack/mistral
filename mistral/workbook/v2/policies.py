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

from mistral.workbook import types
from mistral.workbook.v2 import base
from mistral.workbook.v2 import retry_policy


RETRY_SCHEMA = retry_policy.RetrySpec.get_schema(includes=None)
WAIT_BEFORE_SCHEMA = types.YAQL_OR_POSITIVE_INTEGER
WAIT_AFTER_SCHEMA = types.YAQL_OR_POSITIVE_INTEGER
TIMEOUT_SCHEMA = types.YAQL_OR_POSITIVE_INTEGER
PAUSE_BEFORE_SCHEMA = types.YAQL_OR_BOOLEAN
CONCURRENCY_SCHEMA = types.YAQL_OR_POSITIVE_INTEGER


class PoliciesSpec(base.BaseSpec):
    # See http://json-schema.org
    _schema = {
        "type": "object",
        "properties": {
            "retry": RETRY_SCHEMA,
            "wait-before": WAIT_BEFORE_SCHEMA,
            "wait-after": WAIT_AFTER_SCHEMA,
            "timeout": TIMEOUT_SCHEMA,
            "pause-before": PAUSE_BEFORE_SCHEMA,
            "concurrency": CONCURRENCY_SCHEMA,
        },
        "additionalProperties": False
    }

    @classmethod
    def get_schema(cls, includes=['definitions']):
        return super(PoliciesSpec, cls).get_schema(includes)

    def __init__(self, data):
        super(PoliciesSpec, self).__init__(data)

        self._retry = self._spec_property('retry', retry_policy.RetrySpec)
        self._wait_before = data.get('wait-before', 0)
        self._wait_after = data.get('wait-after', 0)
        self._timeout = data.get('timeout', 0)
        self._pause_before = data.get('pause-before', False)
        self._concurrency = data.get('concurrency', 0)

    def validate_schema(self):
        super(PoliciesSpec, self).validate_schema()

        # Validate YAQL expressions.
        self.validate_yaql_expr(self._data.get('wait-before', 0))
        self.validate_yaql_expr(self._data.get('wait-after', 0))
        self.validate_yaql_expr(self._data.get('timeout', 0))
        self.validate_yaql_expr(self._data.get('pause-before', False))
        self.validate_yaql_expr(self._data.get('concurrency', 0))

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
