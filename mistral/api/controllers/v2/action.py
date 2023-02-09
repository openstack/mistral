# Copyright 2014 - Mirantis, Inc.
# Copyright 2015 Huawei Technologies Co., Ltd.
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

import functools
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
from mistral.lang import parser as spec_parser
from mistral.services import actions as action_service
from mistral.services import adhoc_actions
from mistral.utils import filter_utils
from mistral.utils import rest_utils

from mistral_lib import utils


LOG = logging.getLogger(__name__)


def _action_descriptor_to_resource(action_desc):
    return resources.Action(
        id=getattr(action_desc, 'id', action_desc.name),
        name=action_desc.name,
        description=action_desc.description,
        input=action_desc.params_spec,
        namespace=action_desc.namespace,
        project_id=action_desc.project_id,
        scope=action_desc.scope,
        definition=getattr(action_desc, 'definition', ''),
        is_system=False,
        tags=getattr(action_desc, 'tags', None),
        created_at=utils.datetime_to_str(
            getattr(action_desc, 'created_at', '')
        ),
        updated_at=utils.datetime_to_str(
            getattr(action_desc, 'updated_at', '')
        )
    )


class ActionsController(rest.RestController, hooks.HookController):
    # TODO(nmakhotkin): Have a discussion with pecan/WSME folks in order
    # to have requests and response of different content types. Then
    # delete ContentTypeHook.
    __hooks__ = [ct_hook.ContentTypeHook("application/json", ['POST', 'PUT'])]

    validate = validation.SpecValidationController(
        spec_parser.get_action_list_spec_from_yaml)

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(resources.Action, wtypes.text, wtypes.text)
    def get(self, identifier, namespace=''):
        """Return the named action.

        :param identifier: ID or name of the Action to get.
        :param namespace: The namespace of the action.
        :param fields: Optional. A specified list of fields of the resource to
                       be returned. 'id' will be included automatically in
                       fields if it's not provided.
        """

        acl.enforce('actions:get', context.ctx())

        LOG.debug("Fetch action [identifier=%s]", identifier)

        action_provider = action_service.get_system_action_provider()

        # Here we assume that the action search might involve DB operations
        # so we need to apply the regular retrying logic as everywhere else.
        action_desc = rest_utils.rest_retry_on_db_error(
            action_provider.find
        )(identifier, namespace=namespace)

        if action_desc is None:
            # TODO(rakhmerov): We need to change exception class so that
            # it's not DB specific. But it should be associated with the
            # same HTTP code.
            raise exc.DBEntityNotFoundError(
                'Action not found [name=%s, namespace=%s]'
                % (identifier, namespace)
            )

        return _action_descriptor_to_resource(action_desc)

    @rest_utils.wrap_pecan_controller_exception
    @pecan.expose(content_type="text/plain")
    def put(self, identifier=None, namespace=''):
        """Update one or more actions.

        :param identifier: Optional. If provided, it's UUID or name of an
            action. Only one action can be updated with identifier param.
        :param namespace: Optional. If provided, it's the namespace that
            the action is under.

        NOTE: This text is allowed to have definitions
            of multiple actions. In this case they all will be updated.
        """
        acl.enforce('actions:update', context.ctx())

        definition = pecan.request.text

        LOG.debug("Update action(s) [definition=%s]", definition)

        namespace = namespace or ''

        scope = pecan.request.GET.get('scope', 'private')

        resources.Action.validate_scope(scope)

        if scope == 'public':
            acl.enforce('actions:publicize', context.ctx())

        @rest_utils.rest_retry_on_db_error
        def _update_actions():
            with db_api.transaction():
                return adhoc_actions.update_actions(
                    definition,
                    scope=scope,
                    identifier=identifier,
                    namespace=namespace
                )

        db_acts = _update_actions()

        action_list = [
            resources.Action.from_db_model(db_act) for db_act in db_acts
        ]

        return resources.Actions(actions=action_list).to_json()

    @rest_utils.wrap_pecan_controller_exception
    @pecan.expose(content_type="text/plain")
    def post(self, namespace=''):
        """Create a new action.

        :param namespace: Optional. The namespace to create the ad-hoc action
            in. actions with the same name can be added to a given
            project if they are in two different namespaces.
            (default namespace is '')

        NOTE: This text is allowed to have definitions
            of multiple actions. In this case they all will be created.
        """
        acl.enforce('actions:create', context.ctx())

        namespace = namespace or ''

        definition = pecan.request.text
        scope = pecan.request.GET.get('scope', 'private')
        pecan.response.status = 201

        resources.Action.validate_scope(scope)

        if scope == 'public':
            acl.enforce('actions:publicize', context.ctx())

        LOG.debug("Create action(s) [definition=%s]", definition)

        @rest_utils.rest_retry_on_db_error
        def _create_action_definitions():
            with db_api.transaction():
                return adhoc_actions.create_actions(
                    definition,
                    scope=scope,
                    namespace=namespace
                )

        db_acts = _create_action_definitions()

        action_list = [
            resources.Action.from_db_model(db_act) for db_act in db_acts
        ]

        return resources.Actions(actions=action_list).to_json()

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(None, wtypes.text, wtypes.text, status_code=204)
    def delete(self, identifier, namespace=''):
        """Delete the named action.

        :param identifier: Name or UUID of the action to delete.
        :param namespace: The namespace of which the action is in.
        """
        acl.enforce('actions:delete', context.ctx())

        LOG.debug("Delete action [identifier=%s]", identifier)

        @rest_utils.rest_retry_on_db_error
        def _delete_action_definition():
            with db_api.transaction():
                db_model = db_api.get_action_definition(
                    identifier,
                    namespace=namespace
                )

                if db_model.is_system:
                    raise exc.DataAccessException(
                        "Attempt to delete a system action: %s" % identifier
                    )

                db_api.delete_action_definition(
                    identifier,
                    namespace=namespace
                )

        _delete_action_definition()

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(resources.Actions, wtypes.text, int, types.uniquelist,
                         types.list, types.uniquelist, wtypes.text,
                         wtypes.text, resources.SCOPE_TYPES, wtypes.text,
                         wtypes.text, wtypes.text, wtypes.text,
                         wtypes.text, wtypes.text, wtypes.text)
    def get_all(self, marker=None, limit=None, sort_keys='name',
                sort_dirs='asc', fields='', created_at=None,
                name=None, scope=None, tags=None,
                updated_at=None, description=None, definition=None,
                is_system=None, input=None, namespace=''):
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
                       fields if it's not provided, since it will be used when
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
        :param namespace: Optional. The namespace of the action.
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
            input=input,
            namespace=namespace
        )

        LOG.debug(
            "Fetch actions. marker=%s, limit=%s, sort_keys=%s, "
            "sort_dirs=%s, filters=%s",
            marker,
            limit,
            sort_keys,
            sort_dirs,
            filters
        )

        sort_keys = ['name'] if sort_keys is None else sort_keys
        sort_dirs = ['asc'] if sort_dirs is None else sort_dirs
        fields = [] if fields is None else fields

        if fields and 'name' not in fields:
            fields.insert(0, 'name')

        rest_utils.validate_query_params(limit, sort_keys, sort_dirs)

        action_provider = action_service.get_system_action_provider()

        # Here we assume that the action search might involve DB operations
        # so we need to apply the regular retrying logic as everywhere else.
        action_descriptors = rest_utils.rest_retry_on_db_error(
            action_provider.find_all
        )(
            namespace=namespace,
            limit=limit,
            sort_fields=sort_keys,
            sort_dirs=sort_dirs,
            filters=filters
        )

        # We can't guarantee that at this point the collection of action
        # descriptors is properly filtered and sorted.

        # Apply filters.
        action_descriptors = filter(
            lambda a_d: filter_utils.match_filters(a_d, filters),
            action_descriptors
        )

        # Apply sorting.
        def action_descriptor_sort(a_ds, keys, dirs):
            def compare_(a_d1, a_d2):
                for key, dir in zip(keys, dirs):
                    a_d1 = getattr(a_d1, key, None)
                    a_d2 = getattr(a_d2, key, None)

                    if a_d1 is None and a_d2 is None:
                        ret = 0
                    elif a_d1 is None and a_d2 is not None:
                        ret = -1
                    elif a_d1 is not None and a_d2 is None:
                        ret = 1
                    else:
                        if type(a_d1) is type(a_d2):
                            ret = (a_d1 > a_d2) - (a_d1 < a_d2)
                        else:
                            ret = 1
                    if ret:
                        return ret * (1 if dir == 'asc' else -1)
                return 0
            return sorted(a_ds, key=functools.cmp_to_key(compare_))

        action_descriptors = action_descriptor_sort(action_descriptors,
                                                    sort_keys, sort_dirs)
        start = 0
        for i, a_d in enumerate(action_descriptors):
            if a_d.name == marker:
                start = i
                break

        if limit and limit > 0:
            end = start + limit
            action_descriptors = action_descriptors[start:end]

        action_resources = [
            _action_descriptor_to_resource(a_d)
            for a_d in action_descriptors
        ]

        # TODO(rakhmerov): Fix pagination so that it doesn't work with
        # the 'id' field as a marker. We can't use IDs anymore. "name"
        # seems a good candidate for this.
        return resources.Actions.convert_with_links(
            action_resources,
            limit,
            pecan.request.application_url,
            sort_keys=','.join(sort_keys),
            sort_dirs=','.join(sort_dirs),
            **filters
        )
