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
from pecan import abort
from wsme import types as wtypes
import wsmeext.pecan as wsme_pecan

from mistral import exceptions as ex
from mistral.api.controllers.v1 import task
from mistral.openstack.common import log as logging
from mistral.api.controllers import resource
from mistral.db import api as db_api
from mistral.engine import engine

LOG = logging.getLogger(__name__)


class Execution(resource.Resource):
    """Execution resource."""

    id = wtypes.text
    workbook_name = wtypes.text
    task = wtypes.text
    state = wtypes.text
    # Context is a JSON object but since WSME doesn't support arbitrary
    # dictionaries we have to use text type convert to json and back manually.
    context = wtypes.text

    def to_dict(self):
        d = super(Execution, self).to_dict()

        if d.get('context'):
            d['context'] = json.loads(d['context'])

        return d

    @classmethod
    def from_dict(cls, d):
        e = cls()

        for key, val in d.items():
            if hasattr(e, key):
                if key == 'context' and val:
                    val = json.dumps(val)
                setattr(e, key, val)

        return e


class Executions(resource.Resource):
    """A collection of Execution resources."""

    executions = [Execution]


class ExecutionsController(rest.RestController):

    tasks = task.TasksController()

    @wsme_pecan.wsexpose(Execution, wtypes.text, wtypes.text)
    def get(self, workbook_name, id):
        LOG.debug("Fetch execution [workbook_name=%s, id=%s]" %
                  (workbook_name, id))

        values = db_api.execution_get(workbook_name, id)

        if not values:
            abort(404)
        else:
            return Execution.from_dict(values)

    @wsme_pecan.wsexpose(Execution, wtypes.text, wtypes.text, body=Execution)
    def put(self, workbook_name, id, execution):
        LOG.debug("Update execution [workbook_name=%s, id=%s, execution=%s]" %
                  (workbook_name, id, execution))

        values = db_api.execution_update(workbook_name,
                                         id,
                                         execution.to_dict())

        return Execution.from_dict(values)

    @wsme_pecan.wsexpose(Execution, wtypes.text, body=Execution,
                         status_code=201)
    def post(self, workbook_name, execution):
        LOG.debug("Create execution [workbook_name=%s, execution=%s]" %
                  (workbook_name, execution))
        try:
            context = None
            if execution.context:
                context = json.loads(execution.context)

            values = engine.start_workflow_execution(execution.workbook_name,
                                                     execution.task,
                                                     context)
        except ex.MistralException as e:
            #TODO(nmakhotkin) we should use thing such a decorator here
            abort(400, e.message)

        return Execution.from_dict(values)

    @wsme_pecan.wsexpose(None, wtypes.text, wtypes.text, status_code=204)
    def delete(self, workbook_name, id):
        LOG.debug("Delete execution [workbook_name=%s, id=%s]" %
                  (workbook_name, id))

        db_api.execution_delete(workbook_name, id)

    @wsme_pecan.wsexpose(Executions, wtypes.text)
    def get_all(self, workbook_name):
        LOG.debug("Fetch executions [workbook_name=%s]" % workbook_name)

        executions = [Execution.from_dict(values)
                      for values in db_api.executions_get(workbook_name)]

        return Executions(executions=executions)
