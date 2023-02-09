# Copyright 2020 Nokia Software.
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
from pecan import hooks
from pecan import rest
from wsme import types as wtypes
import wsmeext.pecan as wsme_pecan

from mistral.api import access_control as acl
from mistral.api.controllers.v2 import resources
from mistral.api.controllers.v2 import types
from mistral.api.hooks import content_type as ct_hook
from mistral import context
from mistral import exceptions as exc

from mistral.db.v2 import api as db_api

from mistral.utils import filter_utils
from mistral.utils import rest_utils

LOG = logging.getLogger(__name__)


class DynamicActionsController(rest.RestController, hooks.HookController):
    __hooks__ = [ct_hook.ContentTypeHook("application/json", ['POST', 'PUT'])]

    @rest_utils.wrap_pecan_controller_exception
    @wsme_pecan.wsexpose(
        resources.DynamicAction,
        body=resources.DynamicAction,
        status_code=201
    )
    def post(self, dyn_action):
        """Creates new dynamic action.

        :param dyn_action: Dynamic action to create.
        """
        acl.enforce('dynamic_actions:create', context.ctx())

        LOG.debug('Creating dynamic action [action=%s]', dyn_action)

        if not dyn_action.code_source_id and not dyn_action.code_source_name:
            raise exc.InputException(
                "Either 'code_source_id' or 'code_source_name'"
                " must be provided."
            )

        code_source = db_api.get_code_source(
            dyn_action.code_source_id or dyn_action.code_source_name,
            namespace=dyn_action.namespace
        )

        # TODO(rakhmerov): Ideally we also need to check if the specified
        # class exists in the specified code source. But probably it's not
        # a controller responsibility.

        db_model = rest_utils.rest_retry_on_db_error(
            db_api.create_dynamic_action_definition
        )(
            {
                'name': dyn_action.name,
                'namespace': dyn_action.namespace,
                'class_name': dyn_action.class_name,
                'code_source_id': code_source.id,
                'code_source_name': code_source.name
            }
        )

        return resources.DynamicAction.from_db_model(db_model)

    @rest_utils.wrap_pecan_controller_exception
    @wsme_pecan.wsexpose(
        resources.DynamicAction,
        body=resources.DynamicAction
    )
    def put(self, dyn_action):
        """Update dynamic action.

        :param dyn_action: Dynamic action to create.
        """
        acl.enforce('dynamic_actions:update', context.ctx())

        LOG.debug('Updating dynamic action [action=%s]', dyn_action)

        if not dyn_action.id and not dyn_action.name:
            raise exc.InputException("Either 'name' or 'id' must be provided.")

        values = {'class_name': dyn_action.class_name}

        if dyn_action.scope:
            values['scope'] = dyn_action.scope

        # A client may also want to update a source code.
        if dyn_action.code_source_id or dyn_action.code_source_name:
            code_source = db_api.get_code_source(
                dyn_action.code_source_id or dyn_action.code_source_name,
                namespace=dyn_action.namespace
            )

            values['code_source_id'] = code_source.id
            values['code_source_name'] = code_source.name

        # TODO(rakhmerov): Ideally we also need to check if the specified
        # class exists in the specified code source. But probably it's not
        # a controller responsibility.

        db_model = rest_utils.rest_retry_on_db_error(
            db_api.update_dynamic_action_definition
        )(
            dyn_action.id or dyn_action.name,
            values,
            namespace=dyn_action.namespace
        )

        return resources.DynamicAction.from_db_model(db_model)

    @wsme_pecan.wsexpose(resources.DynamicActions, types.uuid, int,
                         types.uniquelist, types.list, types.uniquelist,
                         wtypes.text, wtypes.text,
                         resources.SCOPE_TYPES, types.uuid, wtypes.text,
                         wtypes.text, bool, wtypes.text)
    def get_all(self, marker=None, limit=None, sort_keys='created_at',
                sort_dirs='asc', fields='', name=None,
                tags=None, scope=None,
                project_id=None, created_at=None, updated_at=None,
                all_projects=False, namespace=None):
        """Return a list of Actions.

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
        :param namespace: Optional. Keep only resources with a specific
                          namespace
        :param input: Optional. Keep only resources with a specific input.
        :param definition: Optional. Keep only resources with a specific
                           definition.
        :param tags: Optional. Keep only resources containing specific tags.
        :param scope: Optional. Keep only resources with a specific scope.
        :param project_id: Optional. The same as the requester project_id
                           or different if the scope is public.
        :param created_at: Optional. Keep only resources created at a specific
                           time and date.
        :param updated_at: Optional. Keep only resources with specific latest
                           update time and date.
        :param all_projects: Optional. Get resources of all projects.
        """

        acl.enforce('dynamic_actions:list', context.ctx())

        filters = filter_utils.create_filters_from_request_params(
            created_at=created_at,
            name=name,
            scope=scope,
            tags=tags,
            updated_at=updated_at,
            project_id=project_id,
            namespace=namespace
        )

        LOG.debug(
            "Fetch dynamic actions. marker=%s, limit=%s, sort_keys=%s, "
            "sort_dirs=%s, fields=%s, filters=%s, all_projects=%s",
            marker,
            limit,
            sort_keys,
            sort_dirs,
            fields,
            filters,
            all_projects
        )

        return rest_utils.get_all(
            resources.DynamicActions,
            resources.DynamicAction,
            db_api.get_dynamic_action_definitions,
            db_api.get_dynamic_action_definition,
            marker=marker,
            limit=limit,
            sort_keys=sort_keys,
            sort_dirs=sort_dirs,
            fields=fields,
            all_projects=all_projects,
            **filters
        )

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(resources.DynamicAction, wtypes.text,
                         wtypes.text, types.uniquelist)
    def get(self, identifier, namespace='', fields=''):
        """Return the named action.

        :param identifier: Name or UUID of the action to retrieve.
        :param namespace: Optional. Namespace of the action to retrieve.
        """
        acl.enforce('dynamic_actions:get', context.ctx())

        LOG.debug(
            'Fetch dynamic action [identifier=%s, namespace=%s]',
            identifier,
            namespace
        )
        if fields and 'id' not in fields:
            fields.insert(0, 'id')

        db_model = rest_utils.rest_retry_on_db_error(
            db_api.get_dynamic_action_definition
        )(
            identifier=identifier,
            namespace=namespace,
            fields=fields
        )

        if fields:
            return resources.DynamicAction.from_tuples(zip(fields, db_model))
        return resources.DynamicAction.from_db_model(db_model)

    @rest_utils.wrap_pecan_controller_exception
    @wsme_pecan.wsexpose(None, wtypes.text, wtypes.text, status_code=204)
    def delete(self, identifier, namespace=''):
        """Delete a dynamic action.

        :param identifier: Name or ID of the action to delete.
        :param namespace: Optional. Namespace of the action to delete.
        """

        acl.enforce('dynamic_actions:delete', context.ctx())

        LOG.debug(
            'Delete dynamic action [identifier=%s, namespace=%s]',
            identifier,
            namespace
        )

        rest_utils.rest_retry_on_db_error(
            db_api.delete_dynamic_action_definition
        )(
            identifier=identifier,
            namespace=namespace
        )
