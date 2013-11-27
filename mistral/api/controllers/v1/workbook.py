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
import wsme
from wsme import types as wtypes
import wsmeext.pecan as wsme_pecan

from mistral.api.controllers.v1 import listener
from mistral.openstack.common import log as logging


LOG = logging.getLogger("%s" % __name__)


class Workbook(wtypes.Base):
    """Workbook resource."""

    name = wtypes.text
    description = wtypes.text
    tags = [wtypes.text]

    def __str__(self):
        return "Workbook [name='%s', description='%s', tags='%s']" % \
               (self.name, self.description, self.tags)


class Workbooks(wtypes.Base):
    """A collection of Workbooks."""

    workbooks = [Workbook]

    def __str__(self):
        return "Workbooks [workbooks=%s]" % self.workbooks


class WorkbooksController(rest.RestController):
    """Operations on collection of workbooks."""

    listeners = listener.ListenersController()

    #@pecan.expose()
    #def _lookup(self, workbook_name, *remainder):
    #    # Standard Pecan delegation.
    #    return WorkbookController(workbook_name), remainder

    @wsme_pecan.wsexpose(Workbook, wtypes.text)
    def get(self, name):
        LOG.debug("Fetch workbook [name=%s]" % name)

        # TODO: fetch the workbook from the DB

        error = "Not implemented"
        pecan.response.translatable_error = error

        raise wsme.exc.ClientSideError(unicode(error))

    @wsme_pecan.wsexpose(Workbook, wtypes.text, body=Workbook)
    def put(self, name, workbook):
        LOG.debug("Update workbook [name=%s, workbook=%s]" % (name, workbook))

        # TODO: modify the workbook in DB

        error = "Not implemented"
        pecan.response.translatable_error = error

        raise wsme.exc.ClientSideError(unicode(error))

    @wsme_pecan.wsexpose(None, wtypes.text, status_code=204)
    def delete(self, name):
        LOG.debug("Delete workbook [name=%s]" % name)

        # TODO: delete the workbook from DB

        error = "Not implemented"
        pecan.response.translatable_error = error

        raise wsme.exc.ClientSideError(unicode(error))

    @wsme_pecan.wsexpose(Workbook, body=Workbook, status_code=201)
    def post(self, workbook):
        LOG.debug("Create workbook [workbook=%s]" % workbook)

        # TODO: create the listener in DB

        error = "Not implemented"
        pecan.response.translatable_error = error

        raise wsme.exc.ClientSideError(unicode(error))

    @wsme_pecan.wsexpose(Workbooks)
    def get_all(self):
        LOG.debug("Fetch workbooks.")

        workbooks = []
        # TODO: fetch workbooks from DB

        return Workbooks(workbooks=workbooks)
