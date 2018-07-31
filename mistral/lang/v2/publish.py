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

from mistral import exceptions as exc
from mistral.lang import types
from mistral.lang.v2 import base


class PublishSpec(base.BaseSpec):
    _schema = {
        "type": "object",
        "properties": {
            "branch": types.NONEMPTY_DICT,
            "global": types.NONEMPTY_DICT,
            "atomic": types.NONEMPTY_DICT
        },
        "additionalProperties": False
    }

    def __init__(self, data, validate):
        super(PublishSpec, self).__init__(data, validate)

        self._branch = self._data.get('branch')
        self._global = self._data.get('global')
        self._atomic = self._data.get('atomic')

    @classmethod
    def get_schema(cls, includes=['definitions']):
        return super(PublishSpec, cls).get_schema(includes)

    def validate_semantics(self):
        if not self._branch and not self._global and not self._atomic:
            raise exc.InvalidModelException(
                "Either 'branch', 'global' or 'atomic' must be specified: "
                % self._data
            )

        self.validate_expr(self._branch)
        self.validate_expr(self._global)
        self.validate_expr(self._atomic)

    def get_branch(self):
        return self._branch

    def get_global(self):
        return self._global

    def get_atomic(self):
        return self._atomic
