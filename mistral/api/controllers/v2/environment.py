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

import json

from oslo_log import log as logging
from pecan import rest
from wsme import types as wtypes
import wsmeext.pecan as wsme_pecan

from mistral.api import access_control as acl
from mistral.api.controllers.v2 import resources
from mistral.api.controllers.v2 import types
from mistral import context
from mistral.db.v2 import api as db_api
from mistral import exceptions
from mistral.utils import filter_utils
from mistral.utils import rest_utils
from mistral_lib.utils import cut


LOG = logging.getLogger(__name__)


class EnvironmentController(rest.RestController):
    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(resources.Environments, types.uuid, int,
                         types.uniquelist, types.list, types.uniquelist,
                         wtypes.text, wtypes.text, types.jsontype,
                         resources.SCOPE_TYPES, wtypes.text, wtypes.text)
    def get_all(self, marker=None, limit=None, sort_keys='created_at',
                sort_dirs='asc', fields='', name=None, description=None,
                variables=None, scope=None, created_at=None, updated_at=None):
        """Return all environments.

        Where project_id is the same as the requester or
        project_id is different but the scope is public.

        :param marker: Optional. Pagination marker for large data sets.
        :param limit: Optional. Maximum number of resources to return in a
                      single result. Default value is None for backward
                      compatibility.
        :param sort_keys: Optional. Columns to sort results by.
                          Default: created_at, which is backward compatible.
        :param sort_dirs: Optional. Directions to sort corresponding to
                          sort_keys, "asc" or "desc" can be chosen.
                          Default: desc. The length of sort_dirs can be equal
                          or less than that of sort_keys.
        :param fields: Optional. A specified list of fields of the resource to
                       be returned. 'id' will be included automatically in
                       fields if it's not provided, since it will be used when
                       constructing 'next' link.
        :param name: Optional. Keep only resources with a specific name.
        :param description: Optional. Keep only resources with a specific
                            description.
        :param variables: Optional. Keep only resources with specific
                          variables.
        :param scope: Optional. Keep only resources with a specific scope.
        :param created_at: Optional. Keep only resources created at a specific
                           time and date.
        :param updated_at: Optional. Keep only resources with specific latest
                           update time and date.
        """
        acl.enforce('environments:list', context.ctx())

        filters = filter_utils.create_filters_from_request_params(
            created_at=created_at,
            name=name,
            updated_at=updated_at,
            description=description,
            variables=variables,
            scope=scope
        )

        LOG.debug("Fetch environments. marker=%s, limit=%s, sort_keys=%s, "
                  "sort_dirs=%s, filters=%s", marker, limit, sort_keys,
                  sort_dirs, filters)

        return rest_utils.get_all(
            resources.Environments,
            resources.Environment,
            db_api.get_environments,
            db_api.get_environment,
            marker=marker,
            limit=limit,
            sort_keys=sort_keys,
            sort_dirs=sort_dirs,
            fields=fields,
            **filters
        )

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(resources.Environment, wtypes.text, types.uniquelist)
    def get(self, name, fields=''):
        """Return the named environment.

        :param name: Name of environment to retrieve
        :param fields: Optional. A specified list of fields of the resource to
                       be returned. 'id' will be included automatically in
                       fields if it's not provided.
        """
        acl.enforce('environments:get', context.ctx())

        LOG.debug("Fetch environment [name=%s]", name)

        if fields and 'id' not in fields:
            fields.insert(0, 'id')

        # Use retries to prevent possible failures.
        r = rest_utils.create_db_retry_object()
        db_model = r.call(db_api.get_environment, name, fields=fields)
        if fields:
            return resources.Environment.from_tuples(zip(fields, db_model))
        return resources.Environment.from_db_model(db_model, fields=fields)

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(
        resources.Environment,
        body=resources.Environment,
        status_code=201
    )
    def post(self, env):
        """Create a new environment.

        :param env: Required. Environment structure to create
        """
        acl.enforce('environments:create', context.ctx())

        LOG.debug("Create environment [env=%s]", cut(env))

        self._validate_environment(
            json.loads(wsme_pecan.pecan.request.body.decode()),
            ['name', 'description', 'variables']
        )

        db_model = rest_utils.rest_retry_on_db_error(
            db_api.create_environment
        )(env.to_dict())

        return resources.Environment.from_db_model(db_model)

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(resources.Environment, body=resources.Environment)
    def put(self, env):
        """Update an environment.

        :param env: Required. Environment structure to update
        """
        acl.enforce('environments:update', context.ctx())

        if not env.name:
            raise exceptions.InputException(
                'Name of the environment is not provided.'
            )

        LOG.debug("Update environment [name=%s, env=%s]", env.name, cut(env))

        definition = json.loads(wsme_pecan.pecan.request.body.decode())
        definition.pop('name')

        self._validate_environment(
            definition,
            ['description', 'variables', 'scope']
        )

        db_model = rest_utils.rest_retry_on_db_error(
            db_api.update_environment
        )(env.name, env.to_dict())

        return resources.Environment.from_db_model(db_model)

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(None, wtypes.text, status_code=204)
    def delete(self, name):
        """Delete the named environment.

        :param name: Name of environment to delete
        """
        acl.enforce('environments:delete', context.ctx())

        LOG.debug("Delete environment [name=%s]", name)

        rest_utils.rest_retry_on_db_error(db_api.delete_environment)(name)

    @staticmethod
    def _validate_environment(env_dict, legal_keys):
        if env_dict is None:
            return

        if set(env_dict) - set(legal_keys):
            raise exceptions.InputException(
                "Please, check your environment definition. Only: "
                "%s are allowed as definition keys." % legal_keys
            )
