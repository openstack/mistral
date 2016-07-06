# Copyright 2013 - Mirantis, Inc.
# Copyright 2015 - StackStorm, Inc.
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

from oslo_log import log as logging
import pecan
from pecan import hooks
from pecan import rest
from wsme import types as wtypes
import wsmeext.pecan as wsme_pecan

from mistral.api import access_control as acl
from mistral.api.controllers import resource
from mistral.api.controllers.v2 import types
from mistral.api.controllers.v2 import validation
from mistral.api.hooks import content_type as ct_hook
from mistral import context
from mistral.db.v2 import api as db_api
from mistral.services import workbooks
from mistral.utils import rest_utils
from mistral.workbook import parser as spec_parser


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


class Workbooks(resource.ResourceList):
    """A collection of Workbooks."""

    workbooks = [Workbook]

    def __init__(self, **kwargs):
        self._type = 'workbooks'

        super(Workbooks, self).__init__(**kwargs)

    @classmethod
    def sample(cls):
        return cls(workbooks=[Workbook.sample()])


class WorkbooksController(rest.RestController, hooks.HookController):
    __hooks__ = [ct_hook.ContentTypeHook("application/json", ['POST', 'PUT'])]

    validate = validation.SpecValidationController(
        spec_parser.get_workbook_spec_from_yaml)

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(Workbook, wtypes.text)
    def get(self, name):
        """Return the named workbook."""
        acl.enforce('workbooks:get', context.ctx())
        LOG.info("Fetch workbook [name=%s]" % name)

        db_model = db_api.get_workbook(name)

        return Workbook.from_dict(db_model.to_dict())

    @rest_utils.wrap_pecan_controller_exception
    @pecan.expose(content_type="text/plain")
    def put(self):
        """Update a workbook."""
        acl.enforce('workbooks:update', context.ctx())
        definition = pecan.request.text
        LOG.info("Update workbook [definition=%s]" % definition)

        wb_db = workbooks.update_workbook_v2(definition)

        return Workbook.from_dict(wb_db.to_dict()).to_json()

    @rest_utils.wrap_pecan_controller_exception
    @pecan.expose(content_type="text/plain")
    def post(self):
        """Create a new workbook."""
        acl.enforce('workbooks:create', context.ctx())
        definition = pecan.request.text
        LOG.info("Create workbook [definition=%s]" % definition)

        wb_db = workbooks.create_workbook_v2(definition)
        pecan.response.status = 201

        return Workbook.from_dict(wb_db.to_dict()).to_json()

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(None, wtypes.text, status_code=204)
    def delete(self, name):
        """Delete the named workbook."""
        acl.enforce('workbooks:delete', context.ctx())
        LOG.info("Delete workbook [name=%s]" % name)

        db_api.delete_workbook(name)

    @wsme_pecan.wsexpose(Workbooks, types.uuid, int, types.uniquelist,
                         types.list, types.uniquelist, wtypes.text,
                         wtypes.text, wtypes.text, SCOPE_TYPES, wtypes.text,
                         types.uniquelist, wtypes.text)
    def get_all(self, marker=None, limit=None, sort_keys='created_at',
                sort_dirs='asc', fields='', created_at=None,
                definition=None, name=None, scope=None, tag=None, tags=None,
                updated_at=None):
        """Return a list of workbooks.

        :param marker: Optional. Pagination marker for large data sets.
        :param limit: Optional. Maximum number of resources to return in a
                      single result. Default value is None for backward
                      compatibility.
        :param sort_keys: Optional. Columns to sort results by.
                          Default: created_at.
        :param sort_dirs: Optional. Directions to sort corresponding to
                          sort_keys, "asc" or "desc" can be chosen.
                          Default: asc.
        :param fields: Optional. A specified list of fields of the resource to
                       be returned. 'id' will be included automatically in
                       fields if it's provided, since it will be used when
                       constructing 'next' link.
        :param name: Optional. Keep only resources with a specific name.
        :param definition: Optional. Keep only resources with a specific
                           definition.
        :param tag: Optional. Keep only resources with a specific tag. If it is
                    used with 'tags', it will be appended to the list of
                    matching tags.
        :param tags: Optional. Keep only resources containing specific tags.
        :param scope: Optional. Keep only resources with a specific scope.
        :param created_at: Optional. Keep only resources created at a specific
                           time and date.
        :param updated_at: Optional. Keep only resources with specific latest
                           update time and date.

        Where project_id is the same as the requester or
        project_id is different but the scope is public.
        """
        acl.enforce('workbooks:list', context.ctx())

        if tag is not None:
            if tags is None:
                tags = [tag]
            else:
                tags.append(tag)

        filters = rest_utils.filters_to_dict(
            created_at=created_at,
            definition=definition,
            name=name,
            scope=scope,
            tags=tags,
            updated_at=updated_at
        )

        LOG.info("Fetch workbooks. marker=%s, limit=%s, sort_keys=%s, "
                 "sort_dirs=%s, fields=%s, filters=%s", marker, limit,
                 sort_keys, sort_dirs, fields, filters)

        return rest_utils.get_all(
            Workbooks,
            Workbook,
            db_api.get_workbooks,
            db_api.get_workbook,
            resource_function=None,
            marker=marker,
            limit=limit,
            sort_keys=sort_keys,
            sort_dirs=sort_dirs,
            fields=fields,
            **filters
        )
