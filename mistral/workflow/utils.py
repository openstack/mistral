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

from mistral.utils import serializer


class TaskResult(object):
    """Explicit data structure containing a result of task execution."""

    def __init__(self, data=None, error=None):
        self.data = data
        self.error = error

    def __repr__(self):
        return 'TaskResult [data=%s, error=%s]' % \
               (repr(self.data), repr(self.error))

    def is_error(self):
        return self.error is not None

    def is_success(self):
        return not self.is_error()

    def __eq__(self, other):
        return self.data == other.data and self.error == other.error


class TaskResultSerializer(serializer.Serializer):
    def serialize(self, entity):
        return {'data': entity.data, 'error': entity.error}

    def deserialize(self, entity):
        return TaskResult(entity['data'], entity['error'])