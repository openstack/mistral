# Copyright 2015 - Mirantis, Inc.
# Copyright 2016 - Brocade Communications Systems, Inc.
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

from oslo_config import cfg
from oslo_log import log as logging
from pecan import rest
from wsme import types as wtypes
import wsmeext.pecan as wsme_pecan

from mistral.api import access_control as acl
from mistral.api.controllers.v2 import resources
from mistral.api.controllers.v2 import types
from mistral import context
from mistral.db.v2 import api as db_api
from mistral import exceptions as exc
from mistral.rpc import clients as rpc
from mistral.utils import filter_utils
from mistral.utils import rest_utils
from mistral.workflow import states
from mistral_lib import actions as ml_actions


LOG = logging.getLogger(__name__)

SUPPORTED_TRANSITION_STATES = [
    states.SUCCESS,
    states.ERROR,
    states.CANCELLED,
    states.PAUSED,
    states.RUNNING
]


def _load_deferred_output_field(action_ex):
    # We need to refer to this lazy-load field explicitly in
    # order to make sure that it is correctly loaded.
    hasattr(action_ex, 'output')


# Use retries to prevent possible failures.
@rest_utils.rest_retry_on_db_error
def _get_action_execution(id):
    with db_api.transaction():
        return _get_action_execution_resource(db_api.get_action_execution(id))


def _get_action_execution_resource(action_ex):
    _load_deferred_output_field(action_ex)

    return _get_action_execution_resource_for_list(action_ex)


def _get_action_execution_resource_for_list(action_ex):
    # TODO(nmakhotkin): Get rid of using dicts for constructing resources.
    # TODO(nmakhotkin): Use db_model for this instead.
    res = resources.ActionExecution.from_db_model(action_ex)

    task_name = (action_ex.task_execution.name
                 if action_ex.task_execution else None)
    setattr(res, 'task_name', task_name)

    return res


def _get_action_executions(task_execution_id=None, marker=None, limit=None,
                           sort_keys='created_at', sort_dirs='asc',
                           fields='', include_output=False, **filters):
    """Return all action executions.

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
                   fields if it's provided, since it will be used when
                   constructing 'next' link.
    :param filters: Optional. A list of filters to apply to the result.
    """
    if task_execution_id:
        filters['task_execution_id'] = task_execution_id

    if include_output:
        resource_function = _get_action_execution_resource
    else:
        resource_function = _get_action_execution_resource_for_list

    return rest_utils.get_all(
        resources.ActionExecutions,
        resources.ActionExecution,
        db_api.get_action_executions,
        db_api.get_action_execution,
        resource_function=resource_function,
        marker=marker,
        limit=limit,
        sort_keys=sort_keys,
        sort_dirs=sort_dirs,
        fields=fields,
        **filters
    )


class ActionExecutionsController(rest.RestController):
    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(resources.ActionExecution, wtypes.text)
    def get(self, id):
        """Return the specified action_execution.

        :param id: UUID of action execution to retrieve
        """
        acl.enforce('action_executions:get', context.ctx())

        LOG.debug("Fetch action_execution [id=%s]", id)

        return _get_action_execution(id)

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(resources.ActionExecution,
                         body=resources.ActionExecution, status_code=201)
    def post(self, action_ex):
        """Create new action_execution.

        :param action_ex: Action to execute
        """
        acl.enforce('action_executions:create', context.ctx())

        LOG.debug(
            "Create action_execution [action_execution=%s]",
            action_ex
        )

        name = action_ex.name
        description = action_ex.description or None
        action_input = action_ex.input or {}
        params = action_ex.params or {}

        if not name:
            raise exc.InputException(
                "Please provide at least action name to run action."
            )

        values = rpc.get_engine_client().start_action(
            name,
            action_input,
            description=description,
            **params
        )

        return resources.ActionExecution.from_dict(values)

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(
        resources.ActionExecution,
        wtypes.text,
        body=resources.ActionExecution
    )
    def put(self, id, action_ex):
        """Update the specified action_execution.

        :param id: UUID of action execution to update
        :param action_ex: Action execution for update
        """
        acl.enforce('action_executions:update', context.ctx())

        LOG.debug(
            "Update action_execution [id=%s, action_execution=%s]",
            id,
            action_ex
        )

        if action_ex.state not in SUPPORTED_TRANSITION_STATES:
            raise exc.InvalidResultException(
                "Error. Expected one of %s, actual: %s" % (
                    SUPPORTED_TRANSITION_STATES,
                    action_ex.state
                )
            )

        if states.is_completed(action_ex.state):
            output = action_ex.output

            if action_ex.state == states.SUCCESS:
                result = ml_actions.Result(data=output)
            elif action_ex.state == states.ERROR:
                if not output:
                    output = 'Unknown error'
                result = ml_actions.Result(error=output)
            elif action_ex.state == states.CANCELLED:
                result = ml_actions.Result(cancel=True)

            values = rpc.get_engine_client().on_action_complete(id, result)

        if action_ex.state in [states.PAUSED, states.RUNNING]:
            state = action_ex.state
            values = rpc.get_engine_client().on_action_update(id, state)

        return resources.ActionExecution.from_dict(values)

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(resources.ActionExecutions, types.uuid, int,
                         types.uniquelist, types.list, types.uniquelist,
                         wtypes.text, wtypes.text, wtypes.text,
                         wtypes.text, wtypes.text, wtypes.text, types.uuid,
                         wtypes.text, wtypes.text, bool, types.jsontype,
                         types.jsontype, types.jsontype, wtypes.text, bool)
    def get_all(self, marker=None, limit=None, sort_keys='created_at',
                sort_dirs='asc', fields='', created_at=None, name=None,
                tags=None, updated_at=None, workflow_name=None,
                task_name=None, task_execution_id=None, state=None,
                state_info=None, accepted=None, input=None, output=None,
                params=None, description=None, include_output=False):
        """Return all tasks within the execution.

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
                       fields if it's provided, since it will be used when
                       constructing 'next' link.
        :param name: Optional. Keep only resources with a specific name.
        :param workflow_name: Optional. Keep only resources with a specific
                              workflow name.
        :param task_name: Optional. Keep only resources with a specific
                          task name.
        :param task_execution_id: Optional. Keep only resources within a
                                  specific task execution.
        :param state: Optional. Keep only resources with a specific state.
        :param state_info: Optional. Keep only resources with specific state
                           information.
        :param accepted: Optional. Keep only resources which have been accepted
                         or not.
        :param input: Optional. Keep only resources with a specific input.
        :param output: Optional. Keep only resources with a specific output.
        :param params: Optional. Keep only resources with specific parameters.
        :param description: Optional. Keep only resources with a specific
                            description.
        :param tags: Optional. Keep only resources containing specific tags.
        :param created_at: Optional. Keep only resources created at a specific
                           time and date.
        :param updated_at: Optional. Keep only resources with specific latest
                           update time and date.
        :param include_output: Optional. Include the output for all executions
                               in the list
        """
        acl.enforce('action_executions:list', context.ctx())

        filters = filter_utils.create_filters_from_request_params(
            created_at=created_at,
            name=name,
            tags=tags,
            updated_at=updated_at,
            workflow_name=workflow_name,
            task_name=task_name,
            task_execution_id=task_execution_id,
            state=state,
            state_info=state_info,
            accepted=accepted,
            input=input,
            output=output,
            params=params,
            description=description
        )

        LOG.debug(
            "Fetch action_executions. marker=%s, limit=%s, "
            "sort_keys=%s, sort_dirs=%s, filters=%s",
            marker,
            limit,
            sort_keys,
            sort_dirs,
            filters
        )

        return _get_action_executions(
            marker=marker,
            limit=limit,
            sort_keys=sort_keys,
            sort_dirs=sort_dirs,
            fields=fields,
            include_output=include_output,
            **filters
        )

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(None, wtypes.text, status_code=204)
    def delete(self, id):
        """Delete the specified action_execution.

        :param id: UUID of action execution to delete
        """
        acl.enforce('action_executions:delete', context.ctx())

        LOG.debug("Delete action_execution [id=%s]", id)

        if not cfg.CONF.api.allow_action_execution_deletion:
            raise exc.NotAllowedException("Action execution deletion is not "
                                          "allowed.")

        with db_api.transaction():
            action_ex = db_api.get_action_execution(id)

            if action_ex.task_execution_id:
                raise exc.NotAllowedException(
                    "Only ad-hoc action execution can be deleted."
                )

            if not states.is_completed(action_ex.state):
                raise exc.NotAllowedException(
                    "Only completed action execution can be deleted."
                )

            return db_api.delete_action_execution(id)


class TasksActionExecutionController(rest.RestController):
    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(resources.ActionExecutions, types.uuid, types.uuid,
                         int, types.uniquelist, types.list, types.uniquelist,
                         wtypes.text, types.uniquelist, wtypes.text,
                         wtypes.text, wtypes.text, wtypes.text, wtypes.text,
                         wtypes.text, bool, types.jsontype, types.jsontype,
                         types.jsontype, wtypes.text, bool)
    def get_all(self, task_execution_id, marker=None, limit=None,
                sort_keys='created_at', sort_dirs='asc', fields='',
                created_at=None, name=None, tags=None,
                updated_at=None, workflow_name=None, task_name=None,
                state=None, state_info=None, accepted=None, input=None,
                output=None, params=None, description=None,
                include_output=None):
        """Return all tasks within the execution.

        Where project_id is the same as the requester or
        project_id is different but the scope is public.

        :param task_execution_id: Keep only resources within a specific task
                                  execution.
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
        :param task_name: Optional. Keep only resources with a specific
                          task name.
        :param state: Optional. Keep only resources with a specific state.
        :param state_info: Optional. Keep only resources with specific state
                           information.
        :param accepted: Optional. Keep only resources which have been accepted
                         or not.
        :param input: Optional. Keep only resources with a specific input.
        :param output: Optional. Keep only resources with a specific output.
        :param params: Optional. Keep only resources with specific parameters.
        :param description: Optional. Keep only resources with a specific
                            description.
        :param tags: Optional. Keep only resources containing specific tags.
        :param created_at: Optional. Keep only resources created at a specific
                           time and date.
        :param updated_at: Optional. Keep only resources with specific latest
                           update time and date.
        :param include_output: Optional. Include the output for all executions
                               in the list
        """
        acl.enforce('action_executions:list', context.ctx())

        filters = filter_utils.create_filters_from_request_params(
            created_at=created_at,
            name=name,
            tags=tags,
            updated_at=updated_at,
            workflow_name=workflow_name,
            task_name=task_name,
            task_execution_id=task_execution_id,
            state=state,
            state_info=state_info,
            accepted=accepted,
            input=input,
            output=output,
            params=params,
            description=description
        )

        LOG.debug(
            "Fetch action_executions. marker=%s, limit=%s, "
            "sort_keys=%s, sort_dirs=%s, filters=%s",
            marker,
            limit,
            sort_keys,
            sort_dirs,
            filters
        )

        return _get_action_executions(
            marker=marker,
            limit=limit,
            sort_keys=sort_keys,
            sort_dirs=sort_dirs,
            fields=fields,
            include_output=include_output,
            **filters
        )

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(resources.ActionExecution, wtypes.text, wtypes.text)
    def get(self, task_execution_id, action_ex_id):
        """Return the specified action_execution.

        :param task_execution_id: Task execution UUID
        :param action_ex_id: Action execution UUID
        """
        acl.enforce('action_executions:get', context.ctx())

        LOG.debug("Fetch action_execution [id=%s]", action_ex_id)

        return _get_action_execution(action_ex_id)
