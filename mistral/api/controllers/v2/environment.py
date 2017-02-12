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
import uuid

from oslo_log import log as logging
from pecan import rest
from wsme import types as wtypes
import wsmeext.pecan as wsme_pecan

from mistral.api.controllers import resource
from mistral.api.controllers.v2 import types
from mistral.db.v2 import api as db_api
from mistral import exceptions as exceptions
from mistral.utils import rest_utils


LOG = logging.getLogger(__name__)

SAMPLE = {
    'server': 'localhost',
    'database': 'temp',
    'timeout': 600,
    'verbose': True
}


class Environment(resource.Resource):
    """Environment resource."""

    id = wtypes.text
    name = wtypes.text
    description = wtypes.text
    variables = types.jsontype
    scope = wtypes.Enum(str, 'private', 'public')
    created_at = wtypes.text
    updated_at = wtypes.text

    @classmethod
    def sample(cls):
        return cls(id=str(uuid.uuid4()),
                   name='sample',
                   description='example environment entry',
                   variables=SAMPLE,
                   scope='private',
                   created_at='1970-01-01T00:00:00.000000',
                   updated_at='1970-01-01T00:00:00.000000')


class Environments(resource.ResourceList):
    """A collection of Environment resources."""

    environments = [Environment]

    def __init__(self, **kwargs):
        self._type = 'environments'

        super(Environments, self).__init__(**kwargs)

    @classmethod
    def sample(cls):
        return cls(environments=[Environment.sample()])


class EnvironmentController(rest.RestController):
    @wsme_pecan.wsexpose(Environments, types.uuid, int, types.uniquelist,
                         types.list, types.uniquelist)
    def get_all(self, marker=None, limit=None, sort_keys='created_at',
                sort_dirs='asc', fields=''):
        """Return all environments.

        Where project_id is the same as the requestor or
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
                       fields if it's provided, since it will be used when
                       constructing 'next' link.

        """

        return rest_utils.get_all(Environments,
                                  Environment,
                                  db_api.get_environments,
                                  db_api.get_environment,
                                  "environments",
                                  marker=marker,
                                  limit=limit,
                                  sort_keys=sort_keys,
                                  sort_dirs=sort_dirs,
                                  fields=fields)

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(Environment, wtypes.text)
    def get(self, name):
        """Return the named environment."""
        LOG.info("Fetch environment [name=%s]" % name)

        db_model = db_api.get_environment(name)

        return Environment.from_dict(db_model.to_dict())

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(Environment, body=Environment, status_code=201)
    def post(self, env):
        """Create a new environment."""
        LOG.info("Create environment [env=%s]" % env)

        self._validate_environment(
            json.loads(wsme_pecan.pecan.request.body.decode()),
            ['name', 'description', 'variables']
        )

        db_model = db_api.create_environment(env.to_dict())

        return Environment.from_dict(db_model.to_dict())

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(Environment, body=Environment)
    def put(self, env):
        """Update an environment."""
        if not env.name:
            raise exceptions.InputException(
                'Name of the environment is not provided.'
            )

        LOG.info("Update environment [name=%s, env=%s]" % (env.name, env))

        definition = json.loads(wsme_pecan.pecan.request.body.decode())
        definition.pop('name')

        self._validate_environment(
            definition,
            ['description', 'variables', 'scope']
        )

        db_model = db_api.update_environment(env.name, env.to_dict())

        return Environment.from_dict(db_model.to_dict())

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(None, wtypes.text, status_code=204)
    def delete(self, name):
        """Delete the named environment."""
        LOG.info("Delete environment [name=%s]" % name)

        db_api.delete_environment(name)

    @staticmethod
    def _validate_environment(env_dict, legal_keys):
        if env_dict is None:
            return

        if set(env_dict) - set(legal_keys):
            raise exceptions.InputException(
                "Please, check your environment definition. Only: "
                "%s are allowed as definition keys." % legal_keys
            )
