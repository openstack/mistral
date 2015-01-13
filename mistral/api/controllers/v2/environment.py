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

from pecan import rest
import six
from wsme import types as wtypes
import wsmeext.pecan as wsme_pecan

from mistral.api.controllers import resource
from mistral.db.v2 import api as db_api
from mistral.openstack.common import log as logging
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
    variables = wtypes.text
    scope = wtypes.Enum(str, 'private', 'public')
    created_at = wtypes.text
    updated_at = wtypes.text

    def __init__(self, *args, **kwargs):
        super(Environment, self).__init__()

        for key, val in six.iteritems(kwargs):
            if key == 'variables' and val is not None:
                val = json.dumps(val)

            setattr(self, key, val)

    def to_dict(self):
        d = super(Environment, self).to_dict()

        if d.get('variables'):
            d['variables'] = json.loads(d['variables'])

        return d

    @classmethod
    def from_dict(cls, d):
        return cls(**d)

    @classmethod
    def sample(cls):
        return cls(id=str(uuid.uuid4()),
                   name='sample',
                   description='example environment entry',
                   variables=json.dumps(SAMPLE),
                   scope='private',
                   created_at='1970-01-01T00:00:00.000000',
                   updated_at='1970-01-01T00:00:00.000000')


class Environments(resource.Resource):
    """A collection of Environment resources."""

    environments = [Environment]

    @classmethod
    def sample(cls):
        return cls(environments=[Environment.sample()])


class EnvironmentController(rest.RestController):

    @wsme_pecan.wsexpose(Environments)
    def get_all(self):
        """Return all environments.
        Where project_id is the same as the requestor or
        project_id is different but the scope is public.
        """
        LOG.info("Fetch environments.")

        environments = [Environment(**db_model.to_dict())
                        for db_model in db_api.get_environments()]

        return Environments(environments=environments)

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(Environment, wtypes.text)
    def get(self, name):
        """Return the named environment."""
        LOG.info("Fetch environment [name=%s]" % name)

        db_model = db_api.get_environment(name)

        return Environment(**db_model.to_dict())

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(Environment, body=Environment, status_code=201)
    def post(self, environment):
        """Create a new environment."""
        LOG.info("Create environment [env=%s]" % environment)

        db_model = db_api.create_environment(environment.to_dict())

        return Environment(**db_model.to_dict())

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(Environment, body=Environment)
    def put(self, environment):
        """Update an environment."""
        if not environment.name:
            raise ValueError('Name of the environment is not provided.')

        LOG.info("Update environment [name=%s, env=%s]" %
                 (environment.name, environment))

        db_model = db_api.update_environment(environment.name,
                                             environment.to_dict())

        return Environment(**db_model.to_dict())

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(None, wtypes.text, status_code=204)
    def delete(self, name):
        """Delete the named environment."""
        LOG.info("Delete environment [name=%s]" % name)

        db_api.delete_environment(name)
