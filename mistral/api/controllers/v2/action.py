# Copyright 2014 - Mirantis, Inc.
# Copyright 2015 Huawei Technologies Co., Ltd.
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
from mistral import exceptions as exc
from mistral.services import actions
from mistral.utils import filter_utils
from mistral.utils import rest_utils
from mistral.workbook import parser as spec_parser

LOG = logging.getLogger(__name__)


class ActionsController(rest.RestController, hooks.HookController):
    # TODO(nmakhotkin): Have a discussion with pecan/WSME folks in order
    # to have requests and response of different content types. Then
    # delete ContentTypeHook.
    __hooks__ = [ct_hook.ContentTypeHook("application/json", ['POST', 'PUT'])]

    validate = validation.SpecValidationController(
        spec_parser.get_action_list_spec_from_yaml)

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(resources.Action, wtypes.text)
    def get(self, identifier):
        """Return the named action.

        :param identifier: ID or name of the Action to get.
        """

        acl.enforce('actions:get', context.ctx())
        LOG.info("Fetch action [identifier=%s]" % identifier)

        db_model = db_api.get_action_definition(identifier)

        return resources.Action.from_dict(db_model.to_dict())

    @rest_utils.wrap_pecan_controller_exception
    @pecan.expose(content_type="text/plain")
    def put(self, identifier=None):
        """Update one or more actions.

        NOTE: This text is allowed to have definitions
            of multiple actions. In this case they all will be updated.
        """
        acl.enforce('actions:update', context.ctx())
        definition = pecan.request.text
        LOG.info("Update action(s) [definition=%s]" % definition)
        scope = pecan.request.GET.get('scope', 'private')

        if scope not in resources.SCOPE_TYPES.values:
            raise exc.InvalidModelException(
                "Scope must be one of the following: %s; actual: "
                "%s" % (resources.SCOPE_TYPES.values, scope)
            )

        with db_api.transaction():
            db_acts = actions.update_actions(
                definition,
                scope=scope,
                identifier=identifier
            )

        models_dicts = [db_act.to_dict() for db_act in db_acts]
        action_list = [resources.Action.from_dict(act) for act in models_dicts]

        return resources.Actions(actions=action_list).to_json()

    @rest_utils.wrap_pecan_controller_exception
    @pecan.expose(content_type="text/plain")
    def post(self):
        """Create a new action.

        NOTE: This text is allowed to have definitions
            of multiple actions. In this case they all will be created.
        """
        acl.enforce('actions:create', context.ctx())
        definition = pecan.request.text
        scope = pecan.request.GET.get('scope', 'private')
        pecan.response.status = 201

        if scope not in resources.SCOPE_TYPES.values:
            raise exc.InvalidModelException(
                "Scope must be one of the following: %s; actual: "
                "%s" % (resources.SCOPE_TYPES.values, scope)
            )

        LOG.info("Create action(s) [definition=%s]" % definition)

        with db_api.transaction():
            db_acts = actions.create_actions(definition, scope=scope)

        models_dicts = [db_act.to_dict() for db_act in db_acts]
        action_list = [resources.Action.from_dict(act) for act in models_dicts]

        return resources.Actions(actions=action_list).to_json()

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(None, wtypes.text, status_code=204)
    def delete(self, identifier):
        """Delete the named action."""
        acl.enforce('actions:delete', context.ctx())
        LOG.info("Delete action [identifier=%s]" % identifier)

        with db_api.transaction():
            db_model = db_api.get_action_definition(identifier)

            if db_model.is_system:
                msg = "Attempt to delete a system action: %s" % identifier
                raise exc.DataAccessException(msg)

            db_api.delete_action_definition(identifier)

    @wsme_pecan.wsexpose(resources.Actions, types.uuid, int, types.uniquelist,
                         types.list, types.uniquelist, wtypes.text,
                         wtypes.text, resources.SCOPE_TYPES, wtypes.text,
                         wtypes.text, wtypes.text, wtypes.text, wtypes.text,
                         wtypes.text)
    def get_all(self, marker=None, limit=None, sort_keys='name',
                sort_dirs='asc', fields='', created_at=None, name=None,
                scope=None, tags=None, updated_at=None,
                description=None, definition=None, is_system=None, input=None):
        """Return all actions.

        :param marker: Optional. Pagination marker for large data sets.
        :param limit: Optional. Maximum number of resources to return in a
                      single result. Default value is None for backward
                      compatibility.
        :param sort_keys: Optional. Columns to sort results by.
                          Default: name.
        :param sort_dirs: Optional. Directions to sort corresponding to
                          sort_keys, "asc" or "desc" can be chosen.
                          Default: asc.
        :param fields: Optional. A specified list of fields of the resource to
                       be returned. 'id' will be included automatically in
                       fields if it's provided, since it will be used when
                       constructing 'next' link.
        :param name: Optional. Keep only resources with a specific name.
        :param scope: Optional. Keep only resources with a specific scope.
        :param definition: Optional. Keep only resources with a specific
                           definition.
        :param is_system: Optional. Keep only system actions or ad-hoc
                          actions (if False).
        :param input: Optional. Keep only resources with a specific input.
        :param description: Optional. Keep only resources with a specific
                            description.
        :param tags: Optional. Keep only resources containing specific tags.
        :param created_at: Optional. Keep only resources created at a specific
                           time and date.
        :param updated_at: Optional. Keep only resources with specific latest
                           update time and date.

        Where project_id is the same as the requester or
        project_id is different but the scope is public.
        """
        acl.enforce('actions:list', context.ctx())

        filters = filter_utils.create_filters_from_request_params(
            created_at=created_at,
            name=name,
            scope=scope,
            tags=tags,
            updated_at=updated_at,
            description=description,
            definition=definition,
            is_system=is_system,
            input=input
        )

        LOG.info("Fetch actions. marker=%s, limit=%s, sort_keys=%s, "
                 "sort_dirs=%s, filters=%s", marker, limit, sort_keys,
                 sort_dirs, filters)

        return rest_utils.get_all(
            resources.Actions,
            resources.Action,
            db_api.get_action_definitions,
            db_api.get_action_definition_by_id,
            marker=marker,
            limit=limit,
            sort_keys=sort_keys,
            sort_dirs=sort_dirs,
            fields=fields,
            **filters
        )
