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

from pecan import rest
from wsme import types as wtypes
import wsmeext.pecan as wsme_pecan

from mistral.api.controllers import resource
from mistral.api.controllers.v1 import execution
from mistral.api.controllers.v1 import listener
from mistral.api.controllers.v1 import workbook_definition
from mistral.db import api as db_api
from mistral.openstack.common import log as logging
from mistral.services import workbooks
from mistral.utils import rest_utils

LOG = logging.getLogger(__name__)
SCOPE_TYPES = wtypes.Enum(str, 'private', 'public')


class Workbook(resource.Resource):
    """Workbook resource."""

    name = wtypes.text
    description = wtypes.text
    tags = [wtypes.text]
    scope = SCOPE_TYPES

    @classmethod
    def sample(cls):
        return cls(name='flow',
                   description='my workflow',
                   tags=['large', 'expensive'])


class Workbooks(resource.Resource):
    """A collection of Workbooks."""

    workbooks = [Workbook]

    @classmethod
    def sample(cls):
        return cls(workbooks=[Workbook.sample()])


class WorkbooksController(rest.RestController):
    definition = workbook_definition.WorkbookDefinitionController()
    listeners = listener.ListenersController()
    executions = execution.WorkbookExecutionsController()

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(Workbook, wtypes.text)
    def get(self, name):
        """Return the named workbook."""
        LOG.debug("Fetch workbook [name=%s]" % name)

        values = db_api.workbook_get(name)
        return Workbook.from_dict(values)

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(Workbook, wtypes.text, body=Workbook)
    def put(self, name, workbook):
        """Update the named workbook."""
        LOG.debug("Update workbook [name=%s, workbook=%s]" % (name, workbook))

        return Workbook.from_dict(db_api.workbook_update(name,
                                                         workbook.to_dict()))

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(Workbook, body=Workbook, status_code=201)
    def post(self, workbook):
        """Create a new workbook."""
        LOG.debug("Create workbook [workbook=%s]" % workbook)
        wb = workbooks.create_workbook(workbook.to_dict())
        return Workbook.from_dict(wb)

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(None, wtypes.text, status_code=204)
    def delete(self, name):
        """Delete the named workbook."""
        LOG.debug("Delete workbook [name=%s]" % name)
        db_api.workbook_delete(name)

    @wsme_pecan.wsexpose(Workbooks)
    def get_all(self):
        """return all workbooks.

        Where project_id is the same as the requestor or
        project_id is different but the scope is public.
        """
        LOG.debug("Fetch workbooks.")

        workbooks_list = [Workbook.from_dict(values)
                          for values in db_api.workbooks_get()]

        return Workbooks(workbooks=workbooks_list)
