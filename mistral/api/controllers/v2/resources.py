# Copyright 2013 - Mirantis, Inc.
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

from wsme import types as wtypes

from mistral.api.controllers import resource
from mistral.api.controllers.v2 import types


class Execution(resource.Resource):
    """Execution resource."""

    id = wtypes.text
    "id is immutable and auto assigned."

    workflow_name = wtypes.text
    "reference to workflow definition"

    workflow_id = wtypes.text
    "reference to workflow ID"

    description = wtypes.text
    "description of workflow execution."

    params = types.jsontype
    "params define workflow type specific parameters. For example, reverse \
    workflow takes one parameter 'task_name' that defines a target task."

    task_execution_id = wtypes.text
    "reference to the parent task execution"

    state = wtypes.text
    "state can be one of: IDLE, RUNNING, SUCCESS, ERROR, PAUSED"

    state_info = wtypes.text
    "an optional state information string"

    input = types.jsontype
    "input is a JSON structure containing workflow input values."

    output = types.jsontype
    "output is a workflow output."

    created_at = wtypes.text
    updated_at = wtypes.text

    @classmethod
    def sample(cls):
        return cls(id='123e4567-e89b-12d3-a456-426655440000',
                   workflow_name='flow',
                   workflow_id='123e4567-e89b-12d3-a456-426655441111',
                   description='this is the first execution.',
                   state='SUCCESS',
                   input={},
                   output={},
                   params={'env': {'k1': 'abc', 'k2': 123}},
                   created_at='1970-01-01T00:00:00.000000',
                   updated_at='1970-01-01T00:00:00.000000')


class Executions(resource.ResourceList):
    """A collection of Execution resources."""

    executions = [Execution]

    def __init__(self, **kwargs):
        self._type = 'executions'

        super(Executions, self).__init__(**kwargs)

    @classmethod
    def sample(cls):
        sample = cls()
        sample.executions = [Execution.sample()]
        sample.next = (
            "http://localhost:8989/v2/executions?"
            "sort_keys=id,workflow_name&sort_dirs=asc,desc&limit=10&"
            "marker=123e4567-e89b-12d3-a456-426655440000"
        )

        return sample
