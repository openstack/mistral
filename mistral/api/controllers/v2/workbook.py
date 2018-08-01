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
from mistral.api.controllers.v2 import resources
from mistral.api.controllers.v2 import types
from mistral.api.controllers.v2 import validation
from mistral.api.hooks import content_type as ct_hook
from mistral import context
from mistral.db.v2 import api as db_api
from mistral.lang import parser as spec_parser
from mistral.services import workbooks
from mistral.utils import filter_utils
from mistral.utils import rest_utils


LOG = logging.getLogger(__name__)


class WorkbooksController(rest.RestController, hooks.HookController):
    __hooks__ = [ct_hook.ContentTypeHook("application/json", ['POST', 'PUT'])]

    validate = validation.SpecValidationController(
        spec_parser.get_workbook_spec_from_yaml)

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(resources.Workbook, wtypes.text, wtypes.text)
    def get(self, name, namespace=''):
        """Return the named workbook.

        :param name: Name of workbook to retrieve.
        :param namespace: Optional. Namespace of workbook to retrieve.
        """
        acl.enforce('workbooks:get', context.ctx())

        LOG.debug("Fetch workbook [name=%s, namespace=%s]", name, namespace)

        # Use retries to prevent possible failures.
        r = rest_utils.create_db_retry_object()
        db_model = r.call(db_api.get_workbook,
                          name,
                          namespace=namespace)

        return resources.Workbook.from_db_model(db_model)

    @rest_utils.wrap_pecan_controller_exception
    @pecan.expose(content_type="text/plain")
    def put(self, namespace=''):
        """Update a workbook.

        :param namespace: Optional. Namespace of workbook to update.
        """

        acl.enforce('workbooks:update', context.ctx())

        definition = pecan.request.text
        scope = pecan.request.GET.get('scope', 'private')

        resources.Workbook.validate_scope(scope)

        LOG.debug("Update workbook [definition=%s]", definition)

        wb_db = rest_utils.rest_retry_on_db_error(
            workbooks.update_workbook_v2)(
            definition,
            namespace=namespace,
            scope=scope
        )

        return resources.Workbook.from_db_model(wb_db).to_json()

    @rest_utils.wrap_pecan_controller_exception
    @pecan.expose(content_type="text/plain")
    def post(self, namespace=''):
        """Create a new workbook.

        :param namespace: Optional. The namespace to create the workbook
            in. Workbooks with the same name can be added to a given
            project if they are in two different namespaces.
        """
        acl.enforce('workbooks:create', context.ctx())

        definition = pecan.request.text
        scope = pecan.request.GET.get('scope', 'private')

        resources.Workbook.validate_scope(scope)

        LOG.debug("Create workbook [definition=%s]", definition)

        wb_db = rest_utils.rest_retry_on_db_error(
            workbooks.create_workbook_v2)(
            definition,
            namespace=namespace,
            scope=scope
        )

        pecan.response.status = 201

        return resources.Workbook.from_db_model(wb_db).to_json()

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(None, wtypes.text, wtypes.text, status_code=204)
    def delete(self, name, namespace=''):
        """Delete the named workbook.

        :param name: Name of workbook to delete.
        :param namespace: Optional. Namespace of workbook to delete.
        """
        acl.enforce('workbooks:delete', context.ctx())

        LOG.debug("Delete workbook [name=%s, namespace=%s]", name, namespace)

        rest_utils.rest_retry_on_db_error(db_api.delete_workbook)(
            name,
            namespace
        )

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(resources.Workbooks, types.uuid, int,
                         types.uniquelist, types.list, types.uniquelist,
                         wtypes.text, wtypes.text, wtypes.text,
                         resources.SCOPE_TYPES, wtypes.text,
                         wtypes.text, wtypes.text)
    def get_all(self, marker=None, limit=None, sort_keys='created_at',
                sort_dirs='asc', fields='', created_at=None,
                definition=None, name=None, scope=None, tags=None,
                updated_at=None, namespace=None):
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
        :param tags: Optional. Keep only resources containing specific tags.
        :param scope: Optional. Keep only resources with a specific scope.
        :param created_at: Optional. Keep only resources created at a specific
                           time and date.
        :param updated_at: Optional. Keep only resources with specific latest
                           update time and date.
        :param namespace: Optional. Keep only resources with specific
                          namespace.
        """
        acl.enforce('workbooks:list', context.ctx())

        filters = filter_utils.create_filters_from_request_params(
            created_at=created_at,
            definition=definition,
            name=name,
            scope=scope,
            tags=tags,
            updated_at=updated_at,
            namespace=namespace
        )

        LOG.debug("Fetch workbooks. marker=%s, limit=%s, sort_keys=%s, "
                  "sort_dirs=%s, fields=%s, filters=%s", marker, limit,
                  sort_keys, sort_dirs, fields, filters)

        return rest_utils.get_all(
            resources.Workbooks,
            resources.Workbook,
            db_api.get_workbooks,
            db_api.get_workbook,
            marker=marker,
            limit=limit,
            sort_keys=sort_keys,
            sort_dirs=sort_dirs,
            fields=fields,
            **filters
        )
