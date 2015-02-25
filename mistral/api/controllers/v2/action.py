# -*- coding: utf-8 -*-
#
# Copyright 2014 - Mirantis, Inc.
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
from pecan import hooks
from pecan import rest
from wsme import types as wtypes
import wsmeext.pecan as wsme_pecan

from mistral.api.controllers import resource
from mistral.api.hooks import content_type as ct_hook
from mistral.db.v2 import api as db_api
from mistral import exceptions as exc
from mistral.openstack.common import log as logging
from mistral.services import actions
from mistral.utils import rest_utils

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

    @classmethod
    def sample(cls):
        return cls(actions=[Action.sample()])


class ActionsController(rest.RestController, hooks.HookController):
    # TODO(nmakhotkin): Have a discussion with pecan/WSME folks in order
    # to have requests and response of different content types. Then
    # delete ContentTypeHook.
    __hooks__ = [ct_hook.ContentTypeHook("application/json", ['POST', 'PUT'])]

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(Action, wtypes.text)
    def get(self, name):
        """Return the named action."""
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
        definition = pecan.request.text
        LOG.info("Update action(s) [definition=%s]" % definition)

        db_acts = actions.update_actions(definition)
        models_dicts = [db_act.to_dict() for db_act in db_acts]

        action_list = [Action.from_dict(act) for act in models_dicts]

        return Actions(actions=action_list).to_string()

    @rest_utils.wrap_pecan_controller_exception
    @pecan.expose(content_type="text/plain")
    def post(self):
        """Create a new action.

        NOTE: This text is allowed to have definitions
            of multiple actions. In this case they all will be created.
        """
        definition = pecan.request.text
        pecan.response.status = 201

        LOG.info("Create action(s) [definition=%s]" % definition)

        db_acts = actions.create_actions(definition)
        models_dicts = [db_act.to_dict() for db_act in db_acts]

        action_list = [Action.from_dict(act) for act in models_dicts]

        return Actions(actions=action_list).to_string()

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(None, wtypes.text, status_code=204)
    def delete(self, name):
        """Delete the named action."""
        LOG.info("Delete action [name=%s]" % name)

        with db_api.transaction():
            db_model = db_api.get_action_definition(name)

            if db_model.is_system:
                msg = "Attempt to delete a system action: %s" % name
                raise exc.DataAccessException(msg)

            db_api.delete_action_definition(name)

    @wsme_pecan.wsexpose(Actions)
    def get_all(self):
        """Return all actions.

        Where project_id is the same as the requester or
        project_id is different but the scope is public.
        """
        LOG.info("Fetch actions.")

        action_list = [Action.from_dict(db_model.to_dict())
                       for db_model in db_api.get_action_definitions()]

        return Actions(actions=action_list)
