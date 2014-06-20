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

import pecan
from pecan import rest
from wsme import types as wtypes
import wsmeext.pecan as wsme_pecan

from mistral.api.controllers import resource
from mistral.db import api as db_api
from mistral.openstack.common import log as logging
from mistral.utils import rest_utils


LOG = logging.getLogger(__name__)


class Task(resource.Resource):
    """Task resource."""

    id = wtypes.text
    "The ID of the Task."

    workbook_name = wtypes.text
    execution_id = wtypes.text
    name = wtypes.text
    description = wtypes.text
    state = wtypes.text
    tags = [wtypes.text]
    output = wtypes.text
    parameters = wtypes.text

    @classmethod
    def from_dict(cls, d):
        e = cls()

        for key, val in d.items():
            if hasattr(e, key):
                # Nonetype check for dictionary must be explicit
                if val is not None and (
                        key == 'parameters' or key == 'output'):
                    val = json.dumps(val)
                setattr(e, key, val)

        return e

    @classmethod
    def sample(cls):
        return cls(id='1234',
                   workbook_name='notifier',
                   execution_id='234',
                   name='build_greeting',
                   description='tell when you are done',
                   state='OK',
                   tags=['foo', 'fee'],
                   output='{"task": {"build_greeting": '
                          '{"greeting": "Hello, John Doe!"}}}',
                   parameters='{ "first_name": "John", "last_name": "Doe"}')


class Tasks(resource.Resource):
    """A collection of tasks."""

    tasks = [Task]
    "List of tasks."

    @classmethod
    def sample(cls):
        return cls(tasks=[Task.sample()])


class TasksController(rest.RestController):
    def _get(self, id):
        values = db_api.task_get(id)
        return Task.from_dict(values)

    def _put(self, id, task):
        if db_api.task_get(id):
            # TODO(rakhmerov): pass task result once it's implemented
            engine = pecan.request.context['engine']
            values = engine.convey_task_result(id,
                                               task.state, None)

            return Task.from_dict(values)

    def _get_all(self, **kwargs):
        tasks = [Task.from_dict(values)
                 for values in db_api.tasks_get(**kwargs)]

        return Tasks(tasks=tasks)


class WorkbookTasksController(TasksController):
    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(Task, wtypes.text, wtypes.text, wtypes.text)
    def get(self, workbook_name, execution_id, id):
        """Return the specified task."""
        LOG.debug("Fetch task [workbook_name=%s, execution_id=%s, id=%s]" %
                  (workbook_name, execution_id, id))

        return self._get(id)

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(Task, wtypes.text, wtypes.text, wtypes.text,
                         body=Task)
    def put(self, workbook_name, execution_id, id, task):
        """Update the specified task."""
        LOG.debug("Update task "
                  "[workbook_name=%s, execution_id=%s, id=%s, task=%s]" %
                  (workbook_name, execution_id, id, task))

        return self._put(id, task)

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(Tasks, wtypes.text, wtypes.text)
    def get_all(self, workbook_name, execution_id):
        """Return all tasks within the execution."""
        db_api.ensure_execution_exists(execution_id)

        LOG.debug("Fetch tasks [workbook_name=%s, execution_id=%s]" %
                  (workbook_name, execution_id))

        return self._get_all(workbook_name=workbook_name,
                             execution_id=execution_id)


class ExecutionTasksController(TasksController):
    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(Task, wtypes.text, wtypes.text)
    def get(self, execution_id, id):
        """Return the specified task."""
        LOG.debug("Fetch task [execution_id=%s, id=%s]" %
                  (execution_id, id))

        return self._get(id)

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(Task, wtypes.text, wtypes.text,
                         body=Task)
    def put(self, execution_id, id, task):
        """Update the specified task."""
        LOG.debug("Update task "
                  "[execution_id=%s, id=%s, task=%s]" %
                  (execution_id, id, task))

        return self._put(id, task)

    @wsme_pecan.wsexpose(Tasks, wtypes.text)
    def get_all(self, execution_id):
        """Return all tasks within the execution."""
        LOG.debug("Fetch tasks [execution_id=%s]" % execution_id)

        return self._get_all(execution_id=execution_id)


class RootTasksController(TasksController):
    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(Task, wtypes.text)
    def get(self, id):
        """Return the specified task."""
        LOG.debug("Fetch task [id=%s]" % id)

        return self._get(id)

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(Task, wtypes.text,
                         body=Task)
    def put(self, id, task):
        """Update the specified task."""
        LOG.debug("Update task "
                  "[id=%s, task=%s]" %
                  (id, task))

        return self._put(id, task)

    @wsme_pecan.wsexpose(Tasks)
    def get_all(self):
        """Return all tasks within the execution."""
        LOG.debug("Fetch tasks")

        return self._get_all()
