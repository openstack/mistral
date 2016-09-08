# Copyright 2014 - Mirantis, Inc.
# Copyright 2015 - StackStorm, Inc.
# Copyright 2016 - Brocade Communications Systems, Inc.
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

from mistral.db.v2 import api as db_api
from mistral.utils import serializers
from mistral.workflow import states


class Result(object):
    """Explicit data structure containing a result of task execution."""

    def __init__(self, data=None, error=None, cancel=False):
        self.data = data
        self.error = error
        self.cancel = cancel

    def __repr__(self):
        return 'Result [data=%s, error=%s, cancel=%s]' % (
            repr(self.data), repr(self.error), str(self.cancel)
        )

    def is_cancel(self):
        return self.cancel

    def is_error(self):
        return self.error is not None and not self.is_cancel()

    def is_success(self):
        return not self.is_error() and not self.is_cancel()

    def __eq__(self, other):
        return (
            self.data == other.data and
            self.error == other.error and
            self.cancel == other.cancel
        )

    def __ne__(self, other):
        return not self.__eq__(other)

    def to_dict(self):
        return ({'result': self.data}
                if self.is_success() else {'result': self.error})


class ResultSerializer(serializers.Serializer):
    @staticmethod
    def serialize(entity):
        return {
            'data': entity.data,
            'error': entity.error,
            'cancel': entity.cancel
        }

    @staticmethod
    def deserialize(entity):
        return Result(
            entity['data'],
            entity['error'],
            entity.get('cancel', False)
        )


def find_task_executions_by_name(wf_ex, task_name):
    return db_api.get_task_executions(
        workflow_execution_id=wf_ex.id,
        name=task_name
    )


def find_task_executions_by_spec(wf_ex, task_spec):
    return find_task_executions_by_name(wf_ex, task_spec.get_name())


def find_task_executions_by_specs(wf_ex, task_specs):
    res = []

    for t_s in task_specs:
        res = res + find_task_executions_by_spec(wf_ex, t_s)

    return res


def find_task_executions_with_state(wf_ex, state):
    return db_api.get_task_executions(
        workflow_execution_id=wf_ex.id,
        state=state
    )


def find_running_task_executions(wf_ex):
    return find_task_executions_with_state(wf_ex, states.RUNNING)


def find_successful_task_executions(wf_ex):
    return find_task_executions_with_state(wf_ex, states.SUCCESS)


def find_error_task_executions(wf_ex):
    return find_task_executions_with_state(wf_ex, states.ERROR)


def find_cancelled_task_executions(wf_ex):
    return find_task_executions_with_state(wf_ex, states.CANCELLED)
