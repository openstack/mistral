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
from mistral.db.v2 import api as db_api
from mistral.openstack.common import log as logging
from mistral.services import workbooks
from mistral.utils import rest_utils

LOG = logging.getLogger(__name__)
SCOPE_TYPES = wtypes.Enum(str, 'private', 'public')


class Workbook(resource.Resource):
    """Workbook resource."""

    id = wtypes.text
    name = wtypes.text

    definition = wtypes.text
    "workbook definition in Mistral v2 DSL"
    tags = [wtypes.text]
    scope = SCOPE_TYPES
    "'private' or 'public'"

    created_at = wtypes.text
    updated_at = wtypes.text

    @classmethod
    def sample(cls):
        return cls(id='123e4567-e89b-12d3-a456-426655440000',
                   name='book',
                   definition='HERE GOES'
                        'WORKBOOK DEFINITION IN MISTRAL DSL v2',
                   tags=['large', 'expensive'],
                   scope='private',
                   created_at='1970-01-01T00:00:00.000000',
                   updated_at='1970-01-01T00:00:00.000000')


class Workbooks(resource.Resource):
    """A collection of Workbooks."""

    workbooks = [Workbook]

    @classmethod
    def sample(cls):
        return cls(workbooks=[Workbook.sample()])


class WorkbooksController(rest.RestController):
    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(Workbook, wtypes.text)
    def get(self, name):
        """Return the named workbook."""
        LOG.debug("Fetch workbook [name=%s]" % name)

        db_model = db_api.get_workbook(name)

        return Workbook.from_dict(db_model.to_dict())

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(Workbook, body=Workbook)
    def put(self, workbook):
        """Update a workbook."""
        LOG.debug("Update workbook [workbook=%s]" % workbook)

        db_model = workbooks.update_workbook_v2(workbook.to_dict())

        return Workbook.from_dict(db_model.to_dict())

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(Workbook, body=Workbook, status_code=201)
    def post(self, workbook):
        """Create a new workbook."""
        LOG.debug("Create workbook [workbook=%s]" % workbook)

        db_model = workbooks.create_workbook_v2(workbook.to_dict())

        return Workbook.from_dict(db_model.to_dict())

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(None, wtypes.text, status_code=204)
    def delete(self, name):
        """Delete the named workbook."""
        LOG.debug("Delete workbook [name=%s]" % name)

        db_api.delete_workbook(name)

    @wsme_pecan.wsexpose(Workbooks)
    def get_all(self):
        """Return all workbooks.

        Where project_id is the same as the requestor or
        project_id is different but the scope is public.
        """
        LOG.debug("Fetch workbooks.")

        workbooks_list = [Workbook.from_dict(db_model.to_dict())
                          for db_model in db_api.get_workbooks()]

        return Workbooks(workbooks=workbooks_list)
