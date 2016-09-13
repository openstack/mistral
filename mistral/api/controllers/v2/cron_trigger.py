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

from oslo_log import log as logging
from pecan import rest
from wsme import types as wtypes
import wsmeext.pecan as wsme_pecan

from mistral.api import access_control as acl
from mistral.api.controllers.v2 import resources
from mistral.api.controllers.v2 import types
from mistral import context
from mistral.db.v2 import api as db_api
from mistral.services import triggers
from mistral.utils import filter_utils
from mistral.utils import rest_utils

LOG = logging.getLogger(__name__)


class CronTriggersController(rest.RestController):
    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(resources.CronTrigger, wtypes.text)
    def get(self, name):
        """Returns the named cron_trigger."""
        acl.enforce('cron_triggers:get', context.ctx())

        LOG.info('Fetch cron trigger [name=%s]' % name)

        db_model = db_api.get_cron_trigger(name)

        return resources.CronTrigger.from_dict(db_model.to_dict())

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(
        resources.CronTrigger,
        body=resources.CronTrigger,
        status_code=201
    )
    def post(self, cron_trigger):
        """Creates a new cron trigger.

        :param cron_trigger: Required. Cron trigger structure.

        """
        acl.enforce('cron_triggers:create', context.ctx())

        LOG.info('Create cron trigger: %s' % cron_trigger)

        values = cron_trigger.to_dict()

        db_model = triggers.create_cron_trigger(
            values['name'],
            values.get('workflow_name'),
            values.get('workflow_input'),
            values.get('workflow_params'),
            values.get('pattern'),
            values.get('first_execution_time'),
            values.get('remaining_executions'),
            workflow_id=values.get('workflow_id')
        )

        return resources.CronTrigger.from_dict(db_model.to_dict())

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(None, wtypes.text, status_code=204)
    def delete(self, name):
        """Delete cron trigger."""
        acl.enforce('cron_triggers:delete', context.ctx())

        LOG.info("Delete cron trigger [name=%s]" % name)

        db_api.delete_cron_trigger(name)

    @wsme_pecan.wsexpose(resources.CronTriggers, types.uuid, int,
                         types.uniquelist, types.list, types.uniquelist,
                         wtypes.text, wtypes.text, types.uuid, types.jsontype,
                         types.jsontype, resources.SCOPE_TYPES, wtypes.text,
                         wtypes.IntegerType(minimum=1), wtypes.text,
                         wtypes.text, wtypes.text, wtypes.text)
    def get_all(self, marker=None, limit=None, sort_keys='created_at',
                sort_dirs='asc', fields='', name=None, workflow_name=None,
                workflow_id=None, workflow_input=None, workflow_params=None,
                scope=None, pattern=None, remaining_executions=None,
                first_execution_time=None, next_execution_time=None,
                created_at=None, updated_at=None):
        """Return all cron triggers.

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
        :param name: Optional. Keep only resources with a specific name.
        :param workflow_name: Optional. Keep only resources with a specific
                              workflow name.
        :param workflow_id: Optional. Keep only resources with a specific
                            workflow ID.
        :param workflow_input: Optional. Keep only resources with a specific
                               workflow input.
        :param workflow_params: Optional. Keep only resources with specific
                                workflow parameters.
        :param scope: Optional. Keep only resources with a specific scope.
        :param pattern: Optional. Keep only resources with a specific pattern.
        :param remaining_executions: Optional. Keep only resources with a
                                     specific number of remaining executions.
        :param first_execution_time: Optional. Keep only resources with a
                                     specific time and date of first execution.
        :param next_execution_time: Optional. Keep only resources with a
                                    specific time and date of next execution.
        :param created_at: Optional. Keep only resources created at a specific
                           time and date.
        :param updated_at: Optional. Keep only resources with specific latest
                           update time and date.
        """
        acl.enforce('cron_triggers:list', context.ctx())

        filters = filter_utils.create_filters_from_request_params(
            created_at=created_at,
            name=name,
            updated_at=updated_at,
            workflow_name=workflow_name,
            workflow_id=workflow_id,
            workflow_input=workflow_input,
            workflow_params=workflow_params,
            scope=scope,
            pattern=pattern,
            remaining_executions=remaining_executions,
            first_execution_time=first_execution_time,
            next_execution_time=next_execution_time
        )

        LOG.info(
            "Fetch cron triggers. marker=%s, limit=%s, sort_keys=%s, "
            "sort_dirs=%s, filters=%s",
            marker, limit, sort_keys, sort_dirs, filters
        )

        return rest_utils.get_all(
            resources.CronTriggers,
            resources.CronTrigger,
            db_api.get_cron_triggers,
            db_api.get_cron_trigger,
            marker=marker,
            limit=limit,
            sort_keys=sort_keys,
            sort_dirs=sort_dirs,
            fields=fields,
            **filters
        )
