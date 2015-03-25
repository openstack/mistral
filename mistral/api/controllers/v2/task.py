# -*- coding: utf-8 -*-
#
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

import json

from pecan import rest
from wsme import types as wtypes
import wsmeext.pecan as wsme_pecan

from mistral.api.controllers import resource
from mistral.api.controllers.v2 import action_execution
from mistral.db.v2 import api as db_api
from mistral.openstack.common import log as logging
from mistral.utils import rest_utils
from mistral.workflow import data_flow
from mistral.workflow import states


LOG = logging.getLogger(__name__)


class Task(resource.Resource):
    """Task resource."""

    id = wtypes.text
    name = wtypes.text

    workflow_name = wtypes.text
    workflow_execution_id = wtypes.text

    state = wtypes.text
    "state can take one of the following values: \
    IDLE, RUNNING, SUCCESS, ERROR, DELAYED"

    result = wtypes.text
    published = wtypes.text

    created_at = wtypes.text
    updated_at = wtypes.text

    @classmethod
    def from_dict(cls, d):
        e = cls()

        for key, val in d.items():
            if hasattr(e, key):
                # Nonetype check for dictionary must be explicit.
                if val is not None and key == 'published':
                    val = json.dumps(val)
                setattr(e, key, val)

        return e

    @classmethod
    def sample(cls):
        return cls(
            id='123e4567-e89b-12d3-a456-426655440000',
            workflow_name='flow',
            workflow_execution_id='123e4567-e89b-12d3-a456-426655440000',
            name='task',
            description='tell when you are done',
            state=states.SUCCESS,
            tags=['foo', 'fee'],
            input='{"first_name": "John", "last_name": "Doe"}',
            output='{"task": {"build_greeting": '
                   '{"greeting": "Hello, John Doe!"}}}',
            created_at='1970-01-01T00:00:00.000000',
            updated_at='1970-01-01T00:00:00.000000'
        )


class Tasks(resource.Resource):
    """A collection of tasks."""

    tasks = [Task]

    @classmethod
    def sample(cls):
        return cls(tasks=[Task.sample()])


def _get_task_resources_with_results(wf_ex_id=None):
    filters = {}

    if wf_ex_id:
        filters['workflow_execution_id'] = wf_ex_id

    tasks = []
    task_execs = db_api.get_task_executions(**filters)
    for task_ex in task_execs:
        task = Task.from_dict(task_ex.to_dict())
        task.result = json.dumps(
            data_flow.get_task_execution_result(task_ex)
        )

        tasks += [task]

    return Tasks(tasks=tasks)


class TasksController(rest.RestController):
    action_executions = action_execution.TasksActionExecutionController()

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(Task, wtypes.text)
    def get(self, id):
        """Return the specified task."""
        LOG.info("Fetch task [id=%s]" % id)

        task_ex = db_api.get_task_execution(id)
        task = Task.from_dict(task_ex.to_dict())

        task.result = json.dumps(data_flow.get_task_execution_result(task_ex))

        return task

    @wsme_pecan.wsexpose(Tasks)
    def get_all(self):
        """Return all tasks within the execution."""
        LOG.info("Fetch tasks")

        return _get_task_resources_with_results()


class ExecutionTasksController(rest.RestController):
    @wsme_pecan.wsexpose(Tasks, wtypes.text)
    def get_all(self, workflow_execution_id):
        """Return all tasks within the workflow execution."""
        LOG.info("Fetch tasks")

        return _get_task_resources_with_results(workflow_execution_id)
