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
from mistral.api.controllers import resource
from mistral.api.controllers.v2 import types
from mistral.api.controllers.v2 import validation
from mistral.api.hooks import content_type as ct_hook
from mistral import context
from mistral.db.v2 import api as db_api
from mistral import exceptions as exc
from mistral.services import actions
from mistral.utils import rest_utils
from mistral.workbook import parser as spec_parser

LOG = logging.getLogger(__name__)
SCOPE_TYPES = wtypes.Enum(str, 'private', 'public')


class Action(resource.Resource):
    """Action resource.

    NOTE: *name* is immutable. Note that name and description get inferred
    from action definition when Mistral service receives a POST request.
    So they can't be changed in another way.

    """

    id = wtypes.text
    name = wtypes.text
    is_system = bool
    input = wtypes.text

    description = wtypes.text
    tags = [wtypes.text]
    definition = wtypes.text
    scope = SCOPE_TYPES

    created_at = wtypes.text
    updated_at = wtypes.text

    @classmethod
    def sample(cls):
        return cls(id='123e4567-e89b-12d3-a456-426655440000',
                   name='flow',
                   definition='HERE GOES ACTION DEFINITION IN MISTRAL DSL v2',
                   tags=['large', 'expensive'],
                   scope='private',
                   created_at='1970-01-01T00:00:00.000000',
                   updated_at='1970-01-01T00:00:00.000000')


class Actions(resource.ResourceList):
    """A collection of Actions."""

    actions = [Action]

    def __init__(self, **kwargs):
        self._type = 'actions'

        super(Actions, self).__init__(**kwargs)

    @classmethod
    def sample(cls):
        actions_sample = cls()
        actions_sample.actions = [Action.sample()]
        actions_sample.next = "http://localhost:8989/v2/actions?" \
                              "sort_keys=id,name&" \
                              "sort_dirs=asc,desc&limit=10&" \
                              "marker=123e4567-e89b-12d3-a456-426655440000"

        return actions_sample


class ActionsController(rest.RestController, hooks.HookController):
    # TODO(nmakhotkin): Have a discussion with pecan/WSME folks in order
    # to have requests and response of different content types. Then
    # delete ContentTypeHook.
    __hooks__ = [ct_hook.ContentTypeHook("application/json", ['POST', 'PUT'])]

    validate = validation.SpecValidationController(
        spec_parser.get_action_list_spec_from_yaml)

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(Action, wtypes.text)
    def get(self, name):
        """Return the named action."""
        acl.enforce('actions:get', context.ctx())
        LOG.info("Fetch action [name=%s]" % name)

        db_model = db_api.get_action_definition(name)

        return Action.from_dict(db_model.to_dict())

    @rest_utils.wrap_pecan_controller_exception
    @pecan.expose(content_type="text/plain")
    def put(self):
        """Update one or more actions.

        NOTE: This text is allowed to have definitions
            of multiple actions. In this case they all will be updated.
        """
        acl.enforce('actions:update', context.ctx())
        definition = pecan.request.text
        LOG.info("Update action(s) [definition=%s]" % definition)
        scope = pecan.request.GET.get('scope', 'private')

        if scope not in SCOPE_TYPES.values:
            raise exc.InvalidModelException(
                "Scope must be one of the following: %s; actual: "
                "%s" % (SCOPE_TYPES.values, scope)
            )

        with db_api.transaction():
            db_acts = actions.update_actions(definition, scope=scope)

        models_dicts = [db_act.to_dict() for db_act in db_acts]
        action_list = [Action.from_dict(act) for act in models_dicts]

        return Actions(actions=action_list).to_json()

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

        if scope not in SCOPE_TYPES.values:
            raise exc.InvalidModelException(
                "Scope must be one of the following: %s; actual: "
                "%s" % (SCOPE_TYPES.values, scope)
            )

        LOG.info("Create action(s) [definition=%s]" % definition)

        with db_api.transaction():
            db_acts = actions.create_actions(definition, scope=scope)

        models_dicts = [db_act.to_dict() for db_act in db_acts]
        action_list = [Action.from_dict(act) for act in models_dicts]

        return Actions(actions=action_list).to_json()

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(None, wtypes.text, status_code=204)
    def delete(self, name):
        """Delete the named action."""
        acl.enforce('actions:delete', context.ctx())
        LOG.info("Delete action [name=%s]" % name)

        with db_api.transaction():
            db_model = db_api.get_action_definition(name)

            if db_model.is_system:
                msg = "Attempt to delete a system action: %s" % name
                raise exc.DataAccessException(msg)

            db_api.delete_action_definition(name)

    @wsme_pecan.wsexpose(Actions, types.uuid, int, types.uniquelist,
                         types.list, types.uniquelist, wtypes.text,
                         wtypes.text, SCOPE_TYPES, wtypes.text,
                         types.uniquelist, wtypes.text, wtypes.text,
                         wtypes.text, bool, wtypes.text)
    def get_all(self, marker=None, limit=None, sort_keys='name',
                sort_dirs='asc', fields='', created_at=None, name=None,
                scope=None, tag=None, tags=None, updated_at=None,
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
        :param tag: Optional. Keep only resources with a specific tag. If it is
                    used with 'tags', it will be appended to the list of
                    matching tags.
        :param tags: Optional. Keep only resources containing specific tags.
        :param created_at: Optional. Keep only resources created at a specific
                           time and date.
        :param updated_at: Optional. Keep only resources with specific latest
                           update time and date.

        Where project_id is the same as the requester or
        project_id is different but the scope is public.
        """
        acl.enforce('actions:list', context.ctx())

        if tag is not None:
            if tags is None:
                tags = [tag]
            else:
                tags.append(tag)

        filters = rest_utils.filters_to_dict(
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
            Actions,
            Action,
            db_api.get_action_definitions,
            db_api.get_action_definition_by_id,
            resource_function=None,
            marker=marker,
            limit=limit,
            sort_keys=sort_keys,
            sort_dirs=sort_dirs,
            fields=fields,
            **filters
        )
