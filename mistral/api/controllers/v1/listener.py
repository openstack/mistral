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

from mistral.openstack.common import log as logging
from mistral.api.controllers import resource
from mistral.db import api as db_api

LOG = logging.getLogger(__name__)


class Event(resource.Resource):
    """Event descriptor."""
    pass


class TaskEvent(Event):
    type = "TASK_STATE"
    task = wtypes.text


class ExecutionEvent(Event):
    type = "EXECUTION_STATE"
    workbook_name = wtypes.text


class Listener(resource.Resource):
    """Listener resource."""

    id = wtypes.text
    description = wtypes.text
    workbook_name = wtypes.text
    webhook = wtypes.text
    events = [Event]


class Listeners(resource.Resource):
    """A collection of Listener resources."""

    listeners = [Listener]


class ListenersController(rest.RestController):
    @wsme_pecan.wsexpose(Listener, wtypes.text, wtypes.text)
    def get(self, workbook_name, id):
        LOG.debug("Fetch listener [workbook_name=%s, id=%s]" %
                  (workbook_name, id))

        values = db_api.listener_get(workbook_name, id)

        if not values:
            abort(404)
        else:
            return Listener.from_dict(values)

    @wsme_pecan.wsexpose(Listener, wtypes.text, wtypes.text, body=Listener)
    def put(self, workbook_name, id, listener):
        LOG.debug("Update listener [workbook_name=%s, id=%s, listener=%s]" %
                  (workbook_name, id, listener))

        values = db_api.listener_update(workbook_name, id, listener.to_dict())

        return Listener.from_dict(values)

    @wsme_pecan.wsexpose(Listener, wtypes.text, body=Listener, status_code=201)
    def post(self, workbook_name, listener):
        LOG.debug("Create listener [workbook_name=%s, listener=%s]" %
                  (workbook_name, listener))

        values = db_api.listener_create(workbook_name, listener.to_dict())

        return Listener.from_dict(values)

    @wsme_pecan.wsexpose(None, wtypes.text, wtypes.text, status_code=204)
    def delete(self, workbook_name, id):
        LOG.debug("Delete listener [workbook_name=%s, id=%s]" %
                  (workbook_name, id))

        db_api.listener_delete(workbook_name, id)

    @wsme_pecan.wsexpose(Listeners, wtypes.text)
    def get_all(self, workbook_name):
        LOG.debug("Fetch listeners [workbook_name=%s]" % workbook_name)

        listeners = [Listener.from_dict(values)
                     for values in db_api.listeners_get(workbook_name)]

        return Listeners(listeners=listeners)
