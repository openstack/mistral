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
from pecan import abort
from wsme import types as wtypes
import wsmeext.pecan as wsme_pecan

from mistral import exceptions as ex
from mistral.api.controllers.v1 import workbook_definition
from mistral.api.controllers.v1 import listener
from mistral.api.controllers.v1 import execution
from mistral.api.controllers import resource
from mistral.services import workbooks

from mistral.openstack.common import log as logging
from mistral.db import api as db_api

LOG = logging.getLogger(__name__)


class Workbook(resource.Resource):
    """Workbook resource."""

    name = wtypes.text
    description = wtypes.text
    tags = [wtypes.text]


class Workbooks(resource.Resource):
    """A collection of Workbooks."""

    workbooks = [Workbook]


class WorkbooksController(rest.RestController):
    definition = workbook_definition.WorkbookDefinitionController()
    listeners = listener.ListenersController()
    executions = execution.ExecutionsController()

    @wsme_pecan.wsexpose(Workbook, wtypes.text)
    def get(self, name):
        LOG.debug("Fetch workbook [name=%s]" % name)

        values = db_api.workbook_get(name)

        if not values:
            abort(404)
        else:
            return Workbook.from_dict(values)

    @wsme_pecan.wsexpose(Workbook, wtypes.text, body=Workbook)
    def put(self, name, workbook):
        LOG.debug("Update workbook [name=%s, workbook=%s]" % (name, workbook))

        return Workbook.from_dict(db_api.workbook_update(name,
                                                         workbook.to_dict()))

    @wsme_pecan.wsexpose(Workbook, body=Workbook, status_code=201)
    def post(self, workbook):
        LOG.debug("Create workbook [workbook=%s]" % workbook)
        try:
            wb = workbooks.create_workbook(workbook.to_dict())
            return Workbook.from_dict(wb)
        except ex.MistralException as e:
            #TODO(nmakhotkin) we should use thing such a decorator here
            abort(400, e.message)

    @wsme_pecan.wsexpose(None, wtypes.text, status_code=204)
    def delete(self, name):
        LOG.debug("Delete workbook [name=%s]" % name)

        db_api.workbook_delete(name)

    @wsme_pecan.wsexpose(Workbooks)
    def get_all(self):
        LOG.debug("Fetch workbooks.")

        workbooks_list = [Workbook.from_dict(values)
                          for values in db_api.workbooks_get()]

        return Workbooks(workbooks=workbooks_list)
