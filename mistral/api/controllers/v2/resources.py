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

import wsme
from wsme import types as wtypes

from mistral.api.controllers import resource
from mistral.api.controllers.v2 import types
from mistral.workflow import states

SCOPE_TYPES = wtypes.Enum(str, 'private', 'public')


class Action(resource.Resource):
    """Action resource.

    NOTE: *name* is immutable. Note that name and description get inferred
    from action definition when Mistral service receives a POST request.
    So they can't be changed in another way.

    """

    id = wtypes.text
    name = wtypes.text
    is_system = bool
    input = wtypes.text

    description = wtypes.text
    tags = [wtypes.text]
    definition = wtypes.text
    scope = SCOPE_TYPES

    created_at = wtypes.text
    updated_at = wtypes.text

    @classmethod
    def sample(cls):
        return cls(
            id='123e4567-e89b-12d3-a456-426655440000',
            name='flow',
            definition='HERE GOES ACTION DEFINITION IN MISTRAL DSL v2',
            tags=['large', 'expensive'],
            scope='private',
            created_at='1970-01-01T00:00:00.000000',
            updated_at='1970-01-01T00:00:00.000000'
        )


class Actions(resource.ResourceList):
    """A collection of Actions."""

    actions = [Action]

    def __init__(self, **kwargs):
        self._type = 'actions'

        super(Actions, self).__init__(**kwargs)

    @classmethod
    def sample(cls):
        sample = cls()
        sample.actions = [Action.sample()]
        sample.next = (
            "http://localhost:8989/v2/actions?sort_keys=id,name&"
            "sort_dirs=asc,desc&limit=10&"
            "marker=123e4567-e89b-12d3-a456-426655440000"
        )

        return sample


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


class Task(resource.Resource):
    """Task resource."""

    id = wtypes.text
    name = wtypes.text

    workflow_name = wtypes.text
    workflow_id = wtypes.text
    workflow_execution_id = wtypes.text

    state = wtypes.text
    "state can take one of the following values: \
    IDLE, RUNNING, SUCCESS, ERROR, DELAYED"

    state_info = wtypes.text
    "an optional state information string"

    result = wtypes.text
    published = types.jsontype
    processed = bool

    created_at = wtypes.text
    updated_at = wtypes.text

    # Add this param to make Mistral API work with WSME 0.8.0 or higher version
    reset = wsme.wsattr(bool, mandatory=True)

    env = types.jsontype

    @classmethod
    def sample(cls):
        return cls(
            id='123e4567-e89b-12d3-a456-426655440000',
            workflow_name='flow',
            workflow_id='123e4567-e89b-12d3-a456-426655441111',
            workflow_execution_id='123e4567-e89b-12d3-a456-426655440000',
            name='task',
            state=states.SUCCESS,
            result='task result',
            published={'key': 'value'},
            processed=True,
            created_at='1970-01-01T00:00:00.000000',
            updated_at='1970-01-01T00:00:00.000000',
            reset=True
        )


class Tasks(resource.ResourceList):
    """A collection of tasks."""

    tasks = [Task]

    def __init__(self, **kwargs):
        self._type = 'tasks'

        super(Tasks, self).__init__(**kwargs)

    @classmethod
    def sample(cls):
        return cls(tasks=[Task.sample()])


class ActionExecution(resource.Resource):
    """ActionExecution resource."""

    id = wtypes.text

    workflow_name = wtypes.text
    task_name = wtypes.text
    task_execution_id = wtypes.text

    state = wtypes.text

    state_info = wtypes.text
    tags = [wtypes.text]
    name = wtypes.text
    description = wtypes.text
    accepted = bool
    input = types.jsontype
    output = types.jsontype
    created_at = wtypes.text
    updated_at = wtypes.text
    params = types.jsontype

    @classmethod
    def sample(cls):
        return cls(
            id='123e4567-e89b-12d3-a456-426655440000',
            workflow_name='flow',
            task_name='task1',
            workflow_execution_id='653e4127-e89b-12d3-a456-426655440076',
            task_execution_id='343e45623-e89b-12d3-a456-426655440090',
            state=states.SUCCESS,
            state_info=states.SUCCESS,
            tags=['foo', 'fee'],
            name='std.echo',
            description='My running action',
            accepted=True,
            input={'first_name': 'John', 'last_name': 'Doe'},
            output={'some_output': 'Hello, John Doe!'},
            created_at='1970-01-01T00:00:00.000000',
            updated_at='1970-01-01T00:00:00.000000',
            params={'save_result': True}
        )


class ActionExecutions(resource.ResourceList):
    """A collection of action_executions."""

    action_executions = [ActionExecution]

    def __init__(self, **kwargs):
        self._type = 'action_executions'

        super(ActionExecutions, self).__init__(**kwargs)

    @classmethod
    def sample(cls):
        return cls(action_executions=[ActionExecution.sample()])
