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

import json
from pecan import rest
from wsme import types as wtypes
import wsmeext.pecan as wsme_pecan

from mistral.api.controllers import resource
from mistral.db.v2 import api as db_api
from mistral.openstack.common import log as logging
from mistral.services import triggers
from mistral.utils import rest_utils

LOG = logging.getLogger(__name__)
SCOPE_TYPES = wtypes.Enum(str, 'private', 'public')


class CronTrigger(resource.Resource):
    """CronTrigger resource."""

    id = wtypes.text
    name = wtypes.text
    workflow_name = wtypes.text
    workflow_input = wtypes.text
    workflow_params = wtypes.text

    scope = SCOPE_TYPES

    pattern = wtypes.text
    remaining_executions = wtypes.IntegerType(minimum=1)
    first_execution_time = wtypes.text
    next_execution_time = wtypes.text

    created_at = wtypes.text
    updated_at = wtypes.text

    def to_dict(self):
        d = super(CronTrigger, self).to_dict()

        self._transform_string_to_dict(
            d, ['workflow_input', 'workflow_params']
        )

        return d

    def _transform_string_to_dict(self, d, keys):
        """Transforms values of dict by given key list.
        :param d: dict to transform.
        :param keys: list of key names in dict
        """
        for k in keys:
            if d.get(k):
                d[k] = json.loads(d[k])

    @classmethod
    def from_dict(cls, d):
        e = cls()

        for key, val in d.items():
            if hasattr(e, key):
                # Nonetype check for dictionary must be explicit.
                if (key in ['workflow_input', 'workflow_params']
                        and val is not None):
                    val = json.dumps(val)

                setattr(e, key, val)

        return e

    @classmethod
    def sample(cls):
        return cls(id='123e4567-e89b-12d3-a456-426655440000',
                   name='my_trigger',
                   workflow_name='my_wf',
                   workflow_input={},
                   workflow_params={},
                   scope='private',
                   pattern='* * * * *',
                   remaining_executions=42,
                   created_at='1970-01-01T00:00:00.000000',
                   updated_at='1970-01-01T00:00:00.000000')


class CronTriggers(resource.Resource):
    """A collection of cron triggers."""

    cron_triggers = [CronTrigger]

    @classmethod
    def sample(cls):
        return cls(cron_triggers=[CronTrigger.sample()])


class CronTriggersController(rest.RestController):
    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(CronTrigger, wtypes.text)
    def get(self, name):
        """Returns the named cron_trigger."""

        LOG.info('Fetch cron trigger [name=%s]' % name)

        db_model = db_api.get_cron_trigger(name)

        return CronTrigger.from_dict(db_model.to_dict())

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(CronTrigger, body=CronTrigger, status_code=201)
    def post(self, cron_trigger):
        """Creates a new cron trigger."""

        LOG.info('Create cron trigger: %s' % cron_trigger)

        values = cron_trigger.to_dict()

        db_model = triggers.create_cron_trigger(
            values['name'],
            values['workflow_name'],
            values.get('workflow_input'),
            values.get('workflow_params'),
            values.get('pattern'),
            values.get('first_execution_time'),
            values.get('remaining_executions')
        )

        return CronTrigger.from_dict(db_model.to_dict())

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(None, wtypes.text, status_code=204)
    def delete(self, name):
        """Delete cron trigger."""
        LOG.info("Delete cron trigger [name=%s]" % name)

        db_api.delete_cron_trigger(name)

    @wsme_pecan.wsexpose(CronTriggers)
    def get_all(self):
        """Return all cron triggers."""

        LOG.info("Fetch cron triggers.")

        _list = [
            CronTrigger.from_dict(db_model.to_dict())
            for db_model in db_api.get_cron_triggers()
        ]

        return CronTriggers(cron_triggers=_list)
