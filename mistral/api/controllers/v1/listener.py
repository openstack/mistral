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

from mistral.openstack.common import log as logging


LOG = logging.getLogger(__name__)


class Event(wtypes.Base):
    """Event descriptor."""
    pass


class TaskEvent(Event):
    type = "TASK_STATE"
    task = wtypes.text


class ExecutionEvent(Event):
    type = "EXECUTION_STATE"
    workbook_name = wtypes.text


class Listener(wtypes.Base):
    """Workbook resource."""

    id = wtypes.text
    description = wtypes.text
    workbook_name = wtypes.text
    webhook = wtypes.text
    events = [Event]


class Listeners(wtypes.Base):
    """A collection of Listeners."""

    listeners = [Listener]

    def __str__(self):
        return "Listeners [listeners=%s]" % self.listeners


class ListenersController(rest.RestController):
    """Operations on collection of listeners."""

    @wsme_pecan.wsexpose(Listener, wtypes.text, wtypes.text)
    def get(self, workbook_name, id):
        LOG.debug("Fetch listener [workbook_name=%s, id=%s]" %
                  (workbook_name, id))

        # TODO: fetch the listener from DB

        error = "Not implemented"
        pecan.response.translatable_error = error

        raise wsme.exc.ClientSideError(unicode(error))

    @wsme_pecan.wsexpose(Listener, wtypes.text, wtypes.text, body=Listener)
    def put(self, workbook_name, id, listener):
        LOG.debug("Update listener [workbook_name=%s, id=%s, listener=%s]" %
                  (workbook_name, id, listener))

        # TODO: modify the listener in DB

        error = "Not implemented"
        pecan.response.translatable_error = error

        raise wsme.exc.ClientSideError(unicode(error))

    @wsme_pecan.wsexpose(None, wtypes.text, wtypes.text, status_code=204)
    def delete(self, workbook_name, id):
        LOG.debug("Delete listener [workbook_name=%s, id=%s]" %
                  (workbook_name, id))

        # TODO: delete the listener from DB

        error = "Not implemented"
        pecan.response.translatable_error = error

        raise wsme.exc.ClientSideError(unicode(error))

    @wsme_pecan.wsexpose(Listener, wtypes.text, body=Listener, status_code=201)
    def post(self, workbook_name, listener):
        LOG.debug("Create listener [workbook_name=%s, listener=%s]" %
                  (workbook_name, listener))

        # TODO: create listener in DB

        error = "Not implemented"
        pecan.response.translatable_error = error

        raise wsme.exc.ClientSideError(unicode(error))

    @wsme_pecan.wsexpose(Listeners, wtypes.text)
    def get_all(self, workbook_name):
        LOG.debug("Fetch listeners [workbook_name=%s]" % workbook_name)

        listeners = []
        # TODO: fetch listeners from DB

        return Listeners(listeners=listeners)
