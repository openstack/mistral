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
from mistral.db.v2 import api as db_api
from mistral.engine1 import rpc
from mistral import exceptions as exc
from mistral.openstack.common import log as logging
from mistral.utils import rest_utils
from mistral.workflow import states
from mistral.workflow import utils as wf_utils


LOG = logging.getLogger(__name__)


class Task(resource.Resource):
    """Task resource."""

    id = wtypes.text
    name = wtypes.text

    # TODO(rakhmerov): Inconsistent with 'workflow_name' for executions.
    wf_name = wtypes.text
    execution_id = wtypes.text

    state = wtypes.text
    "state can take one of the following values: \
    IDLE, RUNNING, SUCCESS, ERROR, DELAYED"

    result = wtypes.text
    input = wtypes.text
    output = wtypes.text

    created_at = wtypes.text
    updated_at = wtypes.text

    @classmethod
    def from_dict(cls, d):
        e = cls()

        for key, val in d.items():
            if hasattr(e, key):
                # Nonetype check for dictionary must be explicit.
                if val is not None and (
                        key == 'input' or key == 'output'):
                    val = json.dumps(val)
                setattr(e, key, val)

        return e

    @classmethod
    def sample(cls):
        return cls(
            id='123e4567-e89b-12d3-a456-426655440000',
            wf_name='book',
            execution_id='123e4567-e89b-12d3-a456-426655440000',
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


class TasksController(rest.RestController):
    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(Task, wtypes.text)
    def get(self, id):
        """Return the specified task."""
        LOG.info("Fetch task [id=%s]" % id)

        db_model = db_api.get_task(id)

        return Task.from_dict(db_model.to_dict())

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(Task, wtypes.text, body=Task)
    def put(self, id, task):
        """Update the specified task."""
        LOG.info("Update task [id=%s, task=%s]" % (id, task))

        # Client must provide a valid json. It shouldn't  necessarily be an
        # object but it should be json complaint so strings have to be escaped.
        result = None

        if task.result:
            try:
                result = json.loads(task.result)
            except (ValueError, TypeError) as e:
                raise exc.InvalidResultException(str(e))

        if task.state == states.ERROR:
            raw_result = wf_utils.TaskResult(error=result)
        else:
            raw_result = wf_utils.TaskResult(data=result)

        engine = rpc.get_engine_client()

        values = engine.on_task_result(id, raw_result)

        return Task.from_dict(values)

    @wsme_pecan.wsexpose(Tasks)
    def get_all(self):
        """Return all tasks within the execution."""
        LOG.info("Fetch tasks")

        tasks = [Task.from_dict(db_model.to_dict())
                 for db_model in db_api.get_tasks()]

        return Tasks(tasks=tasks)


class ExecutionTasksController(rest.RestController):
    @wsme_pecan.wsexpose(Tasks, wtypes.text)
    def get_all(self, execution_id):
        """Return all tasks within the execution."""
        LOG.info("Fetch tasks")

        tasks = [Task.from_dict(db_model.to_dict())
                 for db_model in db_api.get_tasks(execution_id=execution_id)]

        return Tasks(tasks=tasks)
