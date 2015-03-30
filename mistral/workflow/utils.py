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

from mistral.utils import serializers
from mistral.workflow import states


class Result(object):
    """Explicit data structure containing a result of task execution."""

    def __init__(self, data=None, error=None):
        self.data = data
        self.error = error

    def __repr__(self):
        return 'Result [data=%s, error=%s]' % (
            repr(self.data), repr(self.error))

    def is_error(self):
        return self.error is not None

    def is_success(self):
        return not self.is_error()

    def __eq__(self, other):
        return self.data == other.data and self.error == other.error


class ResultSerializer(serializers.Serializer):
    def serialize(self, entity):
        return {'data': entity.data, 'error': entity.error}

    def deserialize(self, entity):
        return Result(entity['data'], entity['error'])


def find_task_execution(wf_ex, task_spec):
    task_execs = [
        t for t in wf_ex.task_executions
        if t.name == task_spec.get_name()
    ]

    return task_execs[0] if len(task_execs) > 0 else None


def find_task_executions(wf_ex, task_specs):
    return filter(
        None,
        [find_task_execution(wf_ex, t_s) for t_s in task_specs]
    )


def find_tasks_with_state(wf_ex, state):
    return [t for t in wf_ex.task_executions if t.state == state]


def find_running_tasks(wf_ex):
    return find_tasks_with_state(wf_ex, states.RUNNING)


def find_completed_tasks(wf_ex):
    return [
        t for t in wf_ex.task_executions if states.is_completed(t.state)
    ]


def find_successful_tasks(wf_ex):
    return find_tasks_with_state(wf_ex, states.SUCCESS)


def find_incomplete_tasks(wf_ex):
    return [t for t in wf_ex.task_executions
            if not states.is_completed(t.state)]


def find_error_tasks(wf_ex):
    return find_tasks_with_state(wf_ex, states.ERROR)
