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

import pecan
from pecan import rest
from pecan import abort
from wsme import types as wtypes
import wsmeext.pecan as wsme_pecan

from mistral.openstack.common import log as logging
from mistral.api.controllers import resource
from mistral.db import api as db_api


LOG = logging.getLogger(__name__)


class Task(resource.Resource):
    """Task resource."""

    id = wtypes.text
    workbook_name = wtypes.text
    execution_id = wtypes.text
    name = wtypes.text
    description = wtypes.text
    action = wtypes.text
    state = wtypes.text
    tags = [wtypes.text]


class Tasks(resource.Resource):
    """A collection of tasks."""

    tasks = [Task]


class TasksController(rest.RestController):
    @wsme_pecan.wsexpose(Task, wtypes.text, wtypes.text, wtypes.text)
    def get(self, workbook_name, execution_id, id):
        LOG.debug("Fetch task [workbook_name=%s, execution_id=%s, id=%s]" %
                  (workbook_name, execution_id, id))

        values = db_api.task_get(workbook_name, execution_id, id)

        if not values:
            abort(404)

        return Task.from_dict(values)

    @wsme_pecan.wsexpose(Task, wtypes.text, wtypes.text, wtypes.text,
                         body=Task)
    def put(self, workbook_name, execution_id, id, task):
        LOG.debug("Update task "
                  "[workbook_name=%s, execution_id=%s, id=%s, task=%s]" %
                  (workbook_name, execution_id, id, task))

        # TODO(rakhmerov): pass task result once it's implemented
        engine = pecan.request.context['engine']
        values = engine.convey_task_result(workbook_name,
                                           execution_id,
                                           id,
                                           task.state, None)

        return Task.from_dict(values)

    @wsme_pecan.wsexpose(Tasks, wtypes.text, wtypes.text)
    def get_all(self, workbook_name, execution_id):
        LOG.debug("Fetch tasks [workbook_name=%s, execution_id=%s]" %
                  (workbook_name, execution_id))

        tasks = [Task.from_dict(values)
                 for values in db_api.tasks_get(workbook_name, execution_id)]

        return Tasks(tasks=tasks)
