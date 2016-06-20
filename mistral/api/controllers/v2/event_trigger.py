# Copyright 2016 - IBM Corp.
# Copyright 2016 Catalyst IT Limited
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
import wsmeext.pecan as wsme_pecan

from mistral.api import access_control as acl
from mistral.api.controllers.v2 import resources
from mistral.api.controllers.v2 import types
from mistral import context as auth_ctx
from mistral.db.v2 import api as db_api
from mistral import exceptions as exc
from mistral.services import triggers
from mistral.utils import rest_utils

LOG = logging.getLogger(__name__)

UPDATE_NOT_ALLOWED = ['exchange', 'topic', 'event']
CREATE_MANDATORY = set(['exchange', 'topic', 'event', 'workflow_id'])


class EventTriggersController(rest.RestController):
    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(resources.EventTrigger, types.uuid)
    def get(self, id):
        """Returns the specified event_trigger."""
        acl.enforce('event_trigger:get', auth_ctx.ctx())

        LOG.info('Fetch event trigger [id=%s]', id)

        db_model = db_api.get_event_trigger(id)

        return resources.EventTrigger.from_dict(db_model.to_dict())

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(resources.EventTrigger, body=resources.EventTrigger,
                         status_code=201)
    def post(self, event_trigger):
        """Creates a new event trigger."""
        acl.enforce('event_trigger:create', auth_ctx.ctx())

        values = event_trigger.to_dict()
        input_keys = [k for k in values if values[k]]

        if CREATE_MANDATORY - set(input_keys):
            raise exc.EventTriggerException(
                "Params %s must be provided for creating event trigger." %
                CREATE_MANDATORY
            )

        LOG.info('Create event trigger: %s', values)

        db_model = triggers.create_event_trigger(
            values.get('name', ''),
            values.get('exchange'),
            values.get('topic'),
            values.get('event'),
            values.get('workflow_id'),
            workflow_input=values.get('workflow_input'),
            workflow_params=values.get('workflow_params'),
        )

        return resources.EventTrigger.from_dict(db_model.to_dict())

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(resources.EventTrigger, types.uuid,
                         body=resources.EventTrigger)
    def put(self, id, event_trigger):
        """Updates an existing event trigger.

        The exchange, topic and event can not be updated. The right way to
        change them is to delete the event trigger first, then create a new
        event trigger with new params.
        """
        acl.enforce('event_trigger:update', auth_ctx.ctx())

        values = event_trigger.to_dict()

        for field in UPDATE_NOT_ALLOWED:
            if values.get(field, None):
                raise exc.EventTriggerException(
                    "Can not update fields %s of event trigger." %
                    UPDATE_NOT_ALLOWED
                )

        db_api.ensure_event_trigger_exists(id)

        LOG.info('Update event trigger: [id=%s, values=%s]', id, values)

        db_model = triggers.update_event_trigger(id, values)

        return resources.EventTrigger.from_dict(db_model.to_dict())

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(None, types.uuid, status_code=204)
    def delete(self, id):
        """Delete event trigger."""
        acl.enforce('event_trigger:delete', auth_ctx.ctx())

        LOG.info("Delete event trigger [id=%s]", id)

        event_trigger = db_api.get_event_trigger(id)

        triggers.delete_event_trigger(event_trigger.to_dict())

    @wsme_pecan.wsexpose(resources.EventTriggers, types.uuid, int,
                         types.uniquelist, types.list, types.uniquelist,
                         types.jsontype)
    def get_all(self, marker=None, limit=None, sort_keys='created_at',
                sort_dirs='asc', fields='', **filters):
        """Return all event triggers."""
        acl.enforce('event_trigger:list', auth_ctx.ctx())

        LOG.info("Fetch event triggers. marker=%s, limit=%s, sort_keys=%s, "
                 "sort_dirs=%s, fields=%s, filters=%s", marker, limit,
                 sort_keys, sort_dirs, fields, filters)

        return rest_utils.get_all(
            resources.EventTriggers,
            resources.EventTrigger,
            db_api.get_event_triggers,
            db_api.get_event_trigger,
            resource_function=None,
            marker=marker,
            limit=limit,
            sort_keys=sort_keys,
            sort_dirs=sort_dirs,
            fields=fields,
            **filters
        )
