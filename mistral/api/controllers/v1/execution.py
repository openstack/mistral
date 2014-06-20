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
from mistral.api.controllers.v1 import task
from mistral.db import api as db_api
from mistral.openstack.common import log as logging
from mistral.utils import rest_utils


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
                # Nonetype check for dictionary must be explicit
                if key == 'context' and val is not None:
                    val = json.dumps(val)
                setattr(e, key, val)

        return e

    @classmethod
    def sample(cls):
        return cls(id='1234',
                   workbook_name='flow',
                   task='doit',
                   state='SUCCESS',
                   context='{}')


class Executions(resource.Resource):
    """A collection of Execution resources."""

    executions = [Execution]

    @classmethod
    def sample(cls):
        return cls(executions=[Execution.sample()])


class ExecutionsController(rest.RestController):

    def _get(self, id):
        values = db_api.execution_get(id)
        return Execution.from_dict(values)

    def _put(self, id, execution):
        values = db_api.execution_update(id, execution.to_dict())

        return Execution.from_dict(values)

    def _delete(self, id):
        db_api.execution_delete(id)

    def _get_all(self, **kwargs):
        executions = [Execution.from_dict(values) for values
                      in db_api.executions_get(**kwargs)]

        return Executions(executions=executions)


class WorkbookExecutionsController(ExecutionsController):

    tasks = task.WorkbookTasksController()

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(Execution, wtypes.text, wtypes.text)
    def get(self, workbook_name, id):
        """Return the specified Execution."""
        LOG.debug("Fetch execution [workbook_name=%s, id=%s]" %
                  (workbook_name, id))
        return self._get(id)

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(Execution, wtypes.text, wtypes.text, body=Execution)
    def put(self, workbook_name, id, execution):
        """Update the specified Execution."""
        LOG.debug("Update execution [workbook_name=%s, id=%s, execution=%s]" %
                  (workbook_name, id, execution))
        return self._put(id, execution)

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(Execution, wtypes.text, body=Execution,
                         status_code=201)
    def post(self, workbook_name, execution):
        """Create a new Execution."""
        LOG.debug("Create execution [workbook_name=%s, execution=%s]" %
                  (workbook_name, execution))

        if (db_api.workbook_get(workbook_name)
                and db_api.workbook_definition_get(workbook_name)):
            context = None
            if execution.context:
                context = json.loads(execution.context)

            engine = pecan.request.context['engine']
            values = engine.start_workflow_execution(execution.workbook_name,
                                                     execution.task,
                                                     context)

            return Execution.from_dict(values)

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(None, wtypes.text, wtypes.text, status_code=204)
    def delete(self, workbook_name, id):
        """Delete the specified Execution."""
        LOG.debug("Delete execution [workbook_name=%s, id=%s]" %
                  (workbook_name, id))
        return self._delete(id)

    @wsme_pecan.wsexpose(Executions, wtypes.text)
    def get_all(self, workbook_name):
        """Return all Executions."""
        LOG.debug("Fetch executions [workbook_name=%s]" % workbook_name)

        if db_api.workbook_get(workbook_name):
            return self._get_all(workbook_name=workbook_name)


class RootExecutionsController(ExecutionsController):

    tasks = task.ExecutionTasksController()

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(Execution, wtypes.text)
    def get(self, id):
        """Return the specified Execution."""
        LOG.debug("Fetch execution [id=%s]" % id)
        return self._get(id)

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(Execution, wtypes.text, body=Execution)
    def put(self, id, execution):
        """Update the specified Execution."""
        LOG.debug("Update execution [id=%s, execution=%s]" %
                  (id, execution))
        return self._put(id, execution)

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(None, wtypes.text, status_code=204)
    def delete(self, id):
        """Delete the specified Execution."""
        LOG.debug("Delete execution [id=%s]" % id)
        return self._delete(id)

    @wsme_pecan.wsexpose(Executions)
    def get_all(self):
        """Return all Executions."""
        LOG.debug("Fetch executions")

        return self._get_all()
