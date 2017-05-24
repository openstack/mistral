# Copyright 2013 - Mirantis, Inc.
# Copyright 2018 - Extreme Networks, Inc.
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


class Workbook(resource.Resource):
    """Workbook resource."""

    id = wtypes.text
    name = wtypes.text

    definition = wtypes.text
    "workbook definition in Mistral v2 DSL"
    tags = [wtypes.text]
    scope = SCOPE_TYPES
    "'private' or 'public'"
    project_id = wsme.wsattr(wtypes.text, readonly=True)

    created_at = wtypes.text
    updated_at = wtypes.text

    @classmethod
    def sample(cls):
        return cls(id='123e4567-e89b-12d3-a456-426655440000',
                   name='book',
                   definition='HERE GOES'
                        'WORKBOOK DEFINITION IN MISTRAL DSL v2',
                   tags=['large', 'expensive'],
                   scope='private',
                   project_id='a7eb669e9819420ea4bd1453e672c0a7',
                   created_at='1970-01-01T00:00:00.000000',
                   updated_at='1970-01-01T00:00:00.000000')


class Workbooks(resource.ResourceList):
    """A collection of Workbooks."""

    workbooks = [Workbook]

    def __init__(self, **kwargs):
        self._type = 'workbooks'

        super(Workbooks, self).__init__(**kwargs)

    @classmethod
    def sample(cls):
        return cls(workbooks=[Workbook.sample()])


class Workflow(resource.Resource):
    """Workflow resource."""

    id = wtypes.text
    name = wtypes.text
    namespace = wtypes.text
    input = wtypes.text

    definition = wtypes.text
    "Workflow definition in Mistral v2 DSL"
    tags = [wtypes.text]
    scope = SCOPE_TYPES
    "'private' or 'public'"
    project_id = wtypes.text

    created_at = wtypes.text
    updated_at = wtypes.text

    @classmethod
    def sample(cls):
        return cls(id='123e4567-e89b-12d3-a456-426655440000',
                   name='flow',
                   input='param1, param2',
                   definition='HERE GOES'
                        'WORKFLOW DEFINITION IN MISTRAL DSL v2',
                   tags=['large', 'expensive'],
                   scope='private',
                   project_id='a7eb669e9819420ea4bd1453e672c0a7',
                   created_at='1970-01-01T00:00:00.000000',
                   updated_at='1970-01-01T00:00:00.000000',
                   namespace='')

    @classmethod
    def _set_input(cls, obj, wf_spec):
        input_list = []

        if wf_spec:
            input = wf_spec.get('input', [])

            for param in input:
                if isinstance(param, dict):
                    for k, v in param.items():
                        input_list.append("%s=%s" % (k, v))
                else:
                    input_list.append(param)

            setattr(obj, 'input', ", ".join(input_list) if input_list else '')

        return obj

    @classmethod
    def from_dict(cls, d):
        obj = super(Workflow, cls).from_dict(d)

        return cls._set_input(obj, d.get('spec'))

    @classmethod
    def from_db_model(cls, db_model):
        obj = super(Workflow, cls).from_db_model(db_model)

        return cls._set_input(obj, db_model.spec)


class Workflows(resource.ResourceList):
    """A collection of workflows."""

    workflows = [Workflow]

    def __init__(self, **kwargs):
        self._type = 'workflows'

        super(Workflows, self).__init__(**kwargs)

    @classmethod
    def sample(cls):
        workflows_sample = cls()
        workflows_sample.workflows = [Workflow.sample()]
        workflows_sample.next = ("http://localhost:8989/v2/workflows?"
                                 "sort_keys=id,name&"
                                 "sort_dirs=asc,desc&limit=10&"
                                 "marker=123e4567-e89b-12d3-a456-426655440000")

        return workflows_sample


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
    project_id = wsme.wsattr(wtypes.text, readonly=True)

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
            project_id='a7eb669e9819420ea4bd1453e672c0a7',
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
    "execution ID. It is immutable and auto assigned or determined by the API "
    "client on execution creation. "
    "If it's passed to POST method from a client it'll be assigned to the "
    "newly created execution object, but only if an execution with such ID "
    "doesn't exist. If it exists, then the endpoint will just return "
    "execution properties in JSON."

    workflow_id = wtypes.text
    "workflow ID"

    workflow_name = wtypes.text
    "workflow name"

    workflow_namespace = wtypes.text
    """Workflow namespace. The workflow namespace is also saved
     under params and passed to all sub-workflow executions. When looking for
     the next sub-workflow to run, The correct workflow will be found by
     name and namespace, where the namespace can be the workflow namespace or
     the default namespace. Workflows in the same namespace as the top workflow
     will be given a higher priority."""

    description = wtypes.text
    "description of workflow execution"

    params = types.jsontype
    """'params' define workflow type specific parameters. Specific parameters
     are:
     'task_name' - the name of the target task. Only for reverse workflows.
     'env' - A string value containing the name of the stored environment
     object or a dictionary with the environment variables used during
     workflow execution and accessible as 'env()' from within expressions
     (YAQL or Jinja) defined in the workflow text.
     'evaluate_env' - If present, controls whether or not Mistral should
     recursively find and evaluate all expressions (YAQL or Jinja) within
     the specified environment (via 'env' parameter). 'True' - evaluate
     all expressions recursively in the environment structure. 'False' -
     don't evaluate expressions. 'True' by default.
    """

    task_execution_id = wtypes.text
    "reference to the parent task execution"

    root_execution_id = wtypes.text
    "reference to the root execution"

    source_execution_id = wtypes.text
    """reference to a workflow execution id which will signal the api to
    perform a lookup of a current workflow_execution and create a replica
    based on that workflow inputs and parameters"""

    state = wtypes.text
    "state can be one of: IDLE, RUNNING, SUCCESS, ERROR, PAUSED"

    state_info = wtypes.text
    "an optional state information string"

    input = types.jsontype
    "input is a JSON structure containing workflow input values"

    output = types.jsontype
    "output is a workflow output"

    created_at = wtypes.text
    updated_at = wtypes.text

    project_id = wsme.wsattr(wtypes.text, readonly=True)

    @classmethod
    def sample(cls):
        return cls(
            id='123e4567-e89b-12d3-a456-426655440000',
            workflow_name='flow',
            workflow_namespace='some_namespace',
            workflow_id='123e4567-e89b-12d3-a456-426655441111',
            description='this is the first execution.',
            project_id='40a908dbddfe48ad80a87fb30fa70a03',
            state='SUCCESS',
            input={},
            output={},
            params={
                'env': {'k1': 'abc', 'k2': 123},
                'notify': [
                    {
                        'type': 'webhook',
                        'url': 'http://endpoint/of/webhook',
                        'headers': {
                            'Content-Type': 'application/json',
                            'X-Auth-Token': '123456789'
                        }
                    },
                    {
                        'type': 'queue',
                        'topic': 'failover_queue',
                        'backend': 'rabbitmq',
                        'host': '127.0.0.1',
                        'port': 5432
                    }
                ]
            },
            created_at='1970-01-01T00:00:00.000000',
            updated_at='1970-01-01T00:00:00.000000'
        )


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
    type = wtypes.text

    workflow_name = wtypes.text
    workflow_namespace = wtypes.text
    workflow_id = wtypes.text
    workflow_execution_id = wtypes.text

    state = wtypes.text
    """state can take one of the following values:
     IDLE, RUNNING, SUCCESS, ERROR, DELAYED"""

    state_info = wtypes.text
    "an optional state information string"

    project_id = wsme.wsattr(wtypes.text, readonly=True)

    runtime_context = types.jsontype

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
            project_id='40a908dbddfe48ad80a87fb30fa70a03',
            runtime_context={
                'triggered_by': [
                    {
                        'task_id': '123-123-123',
                        'event': 'on-success'
                    }
                ]
            },
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
    workflow_namespace = wtypes.text
    task_name = wtypes.text
    task_execution_id = wtypes.text

    state = wtypes.text

    state_info = wtypes.text
    tags = [wtypes.text]
    name = wtypes.text
    description = wtypes.text
    project_id = wsme.wsattr(wtypes.text, readonly=True)
    accepted = bool
    input = types.jsontype
    output = types.jsontype
    created_at = wtypes.text
    updated_at = wtypes.text
    params = types.jsontype  # TODO(rakhmerov): What is this??

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
            project_id='40a908dbddfe48ad80a87fb30fa70a03',
            accepted=True,
            input={'first_name': 'John', 'last_name': 'Doe'},
            output={'some_output': 'Hello, John Doe!'},
            created_at='1970-01-01T00:00:00.000000',
            updated_at='1970-01-01T00:00:00.000000',
            params={'save_result': True, "run_sync": False}
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


class CronTrigger(resource.Resource):
    """CronTrigger resource."""

    id = wtypes.text
    name = wtypes.text
    workflow_name = wtypes.text
    workflow_id = wtypes.text
    workflow_input = types.jsontype
    workflow_params = types.jsontype
    project_id = wsme.wsattr(wtypes.text, readonly=True)

    scope = SCOPE_TYPES

    pattern = wtypes.text
    remaining_executions = wtypes.IntegerType(minimum=1)
    first_execution_time = wtypes.text
    next_execution_time = wtypes.text

    created_at = wtypes.text
    updated_at = wtypes.text

    @classmethod
    def sample(cls):
        return cls(
            id='123e4567-e89b-12d3-a456-426655440000',
            name='my_trigger',
            workflow_name='my_wf',
            workflow_id='123e4567-e89b-12d3-a456-426655441111',
            workflow_input={},
            workflow_params={},
            project_id='40a908dbddfe48ad80a87fb30fa70a03',
            scope='private',
            pattern='* * * * *',
            remaining_executions=42,
            created_at='1970-01-01T00:00:00.000000',
            updated_at='1970-01-01T00:00:00.000000'
        )


class CronTriggers(resource.ResourceList):
    """A collection of cron triggers."""

    cron_triggers = [CronTrigger]

    def __init__(self, **kwargs):
        self._type = 'cron_triggers'

        super(CronTriggers, self).__init__(**kwargs)

    @classmethod
    def sample(cls):
        return cls(cron_triggers=[CronTrigger.sample()])


class Environment(resource.Resource):
    """Environment resource."""

    id = wtypes.text
    name = wtypes.text
    description = wtypes.text
    variables = types.jsontype
    scope = SCOPE_TYPES
    project_id = wsme.wsattr(wtypes.text, readonly=True)
    created_at = wtypes.text
    updated_at = wtypes.text

    @classmethod
    def sample(cls):
        return cls(
            id='123e4567-e89b-12d3-a456-426655440000',
            name='sample',
            description='example environment entry',
            variables={
                'server': 'localhost',
                'database': 'temp',
                'timeout': 600,
                'verbose': True
            },
            scope='private',
            project_id='40a908dbddfe48ad80a87fb30fa70a03',
            created_at='1970-01-01T00:00:00.000000',
            updated_at='1970-01-01T00:00:00.000000'
        )


class Environments(resource.ResourceList):
    """A collection of Environment resources."""

    environments = [Environment]

    def __init__(self, **kwargs):
        self._type = 'environments'

        super(Environments, self).__init__(**kwargs)

    @classmethod
    def sample(cls):
        return cls(environments=[Environment.sample()])


class Member(resource.Resource):
    id = types.uuid
    resource_id = wtypes.text
    resource_type = wtypes.text
    project_id = wtypes.text
    member_id = wtypes.text
    status = wtypes.Enum(str, 'pending', 'accepted', 'rejected')
    created_at = wtypes.text
    updated_at = wtypes.text

    @classmethod
    def sample(cls):
        return cls(
            id='123e4567-e89b-12d3-a456-426655440000',
            resource_id='123e4567-e89b-12d3-a456-426655440011',
            resource_type='workflow',
            project_id='40a908dbddfe48ad80a87fb30fa70a03',
            member_id='a7eb669e9819420ea4bd1453e672c0a7',
            status='accepted',
            created_at='1970-01-01T00:00:00.000000',
            updated_at='1970-01-01T00:00:00.000000'
        )


class Members(resource.ResourceList):
    members = [Member]

    @classmethod
    def sample(cls):
        return cls(members=[Member.sample()])


class Service(resource.Resource):
    """Service resource."""

    name = wtypes.text

    type = wtypes.text

    @classmethod
    def sample(cls):
        return cls(name='host1_1234', type='executor_group')


class Services(resource.Resource):
    """A collection of Services."""

    services = [Service]

    @classmethod
    def sample(cls):
        return cls(services=[Service.sample()])


class EventTrigger(resource.Resource):
    """EventTrigger resource."""

    id = wsme.wsattr(wtypes.text, readonly=True)
    created_at = wsme.wsattr(wtypes.text, readonly=True)
    updated_at = wsme.wsattr(wtypes.text, readonly=True)
    project_id = wsme.wsattr(wtypes.text, readonly=True)
    name = wtypes.text
    workflow_id = types.uuid
    workflow_input = types.jsontype
    workflow_params = types.jsontype
    exchange = wtypes.text
    topic = wtypes.text
    event = wtypes.text
    scope = SCOPE_TYPES

    @classmethod
    def sample(cls):
        return cls(id='123e4567-e89b-12d3-a456-426655441414',
                   created_at='1970-01-01T00:00:00.000000',
                   updated_at='1970-01-01T00:00:00.000000',
                   project_id='project',
                   name='expiration_event_trigger',
                   workflow_id='123e4567-e89b-12d3-a456-426655441414',
                   workflow_input={},
                   workflow_params={},
                   exchange='nova',
                   topic='notifications',
                   event='compute.instance.create.end')


class EventTriggers(resource.ResourceList):
    """A collection of event triggers."""

    event_triggers = [EventTrigger]

    def __init__(self, **kwargs):
        self._type = 'event_triggers'

        super(EventTriggers, self).__init__(**kwargs)

    @classmethod
    def sample(cls):
        triggers_sample = cls()
        triggers_sample.event_triggers = [EventTrigger.sample()]
        triggers_sample.next = ("http://localhost:8989/v2/event_triggers?"
                                "sort_keys=id,name&"
                                "sort_dirs=asc,desc&limit=10&"
                                "marker=123e4567-e89b-12d3-a456-426655440000")

        return triggers_sample
