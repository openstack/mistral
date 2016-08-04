# Copyright 2013 - Mirantis, Inc.
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
from mistral.api.controllers.v2 import action_execution
from mistral.api.controllers.v2 import resources
from mistral.api.controllers.v2 import types
from mistral import context
from mistral.db.v2 import api as db_api
from mistral.engine.rpc_backend import rpc
from mistral import exceptions as exc
from mistral.utils import filter_utils
from mistral.utils import rest_utils
from mistral.workbook import parser as spec_parser
from mistral.workflow import data_flow
from mistral.workflow import states


LOG = logging.getLogger(__name__)
STATE_TYPES = wtypes.Enum(str, states.IDLE, states.RUNNING, states.SUCCESS,
                          states.ERROR, states.RUNNING_DELAYED)


def _get_task_resource_with_result(task_ex):
    task = resources.Task.from_dict(task_ex.to_dict())
    task.result = json.dumps(data_flow.get_task_execution_result(task_ex))

    return task


class TaskExecutionsController(rest.RestController):
    @wsme_pecan.wsexpose(resources.Executions, types.uuid, types.uuid, int,
                         types.uniquelist, types.list, types.uniquelist,
                         wtypes.text, types.uuid, wtypes.text, types.jsontype,
                         STATE_TYPES, wtypes.text, types.jsontype,
                         types.jsontype, wtypes.text, wtypes.text)
    def get_all(self, task_execution_id, marker=None, limit=None,
                sort_keys='created_at', sort_dirs='asc', fields='',
                workflow_name=None, workflow_id=None, description=None,
                params=None, state=None, state_info=None, input=None,
                output=None, created_at=None, updated_at=None):
        """Return all executions that belong to the given task execution.

        :param task_execution_id: Task task execution ID.
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
        :param workflow_name: Optional. Keep only resources with a specific
                              workflow name.
        :param workflow_id: Optional. Keep only resources with a specific
                            workflow ID.
        :param description: Optional. Keep only resources with a specific
                            description.
        :param params: Optional. Keep only resources with specific parameters.
        :param state: Optional. Keep only resources with a specific state.
        :param state_info: Optional. Keep only resources with specific
                           state information.
        :param input: Optional. Keep only resources with a specific input.
        :param output: Optional. Keep only resources with a specific output.
        :param created_at: Optional. Keep only resources created at a specific
                           time and date.
        :param updated_at: Optional. Keep only resources with specific latest
                           update time and date.
        """
        acl.enforce('executions:list', context.ctx())

        filters = filter_utils.create_filters_from_request_params(
            task_execution_id=task_execution_id,
            created_at=created_at,
            workflow_name=workflow_name,
            workflow_id=workflow_id,
            params=params,
            state=state,
            state_info=state_info,
            input=input,
            output=output,
            updated_at=updated_at,
            description=description
        )

        LOG.info(
            "Fetch executions. marker=%s, limit=%s, sort_keys=%s, "
            "sort_dirs=%s, filters=%s", marker, limit, sort_keys, sort_dirs,
            filters
        )

        return rest_utils.get_all(
            resources.Executions,
            resources.Execution,
            db_api.get_workflow_executions,
            db_api.get_workflow_execution,
            marker=marker,
            limit=limit,
            sort_keys=sort_keys,
            sort_dirs=sort_dirs,
            fields=fields,
            **filters
        )


class TasksController(rest.RestController):
    action_executions = action_execution.TasksActionExecutionController()
    workflow_executions = TaskExecutionsController()

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(resources.Task, wtypes.text)
    def get(self, id):
        """Return the specified task."""
        acl.enforce('tasks:get', context.ctx())
        LOG.info("Fetch task [id=%s]" % id)

        task_ex = db_api.get_task_execution(id)

        return _get_task_resource_with_result(task_ex)

    @wsme_pecan.wsexpose(resources.Tasks, types.uuid, int, types.uniquelist,
                         types.list, types.uniquelist, wtypes.text,
                         wtypes.text, types.uuid, types.uuid, STATE_TYPES,
                         wtypes.text, wtypes.text, types.jsontype, bool,
                         wtypes.text, wtypes.text, bool, types.jsontype)
    def get_all(self, marker=None, limit=None, sort_keys='created_at',
                sort_dirs='asc', fields='', name=None, workflow_name=None,
                workflow_id=None, workflow_execution_id=None, state=None,
                state_info=None, result=None, published=None, processed=None,
                created_at=None, updated_at=None, reset=None, env=None):
        """Return all tasks.

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
        :param workflow_id: Optional. Keep only resources with a specific
                            workflow ID.
        :param workflow_execution_id: Optional. Keep only resources with a
                                      specific workflow execution ID.
        :param state: Optional. Keep only resources with a specific state.
        :param state_info: Optional. Keep only resources with specific
                           state information.
        :param result: Optional. Keep only resources with a specific result.
        :param published: Optional. Keep only resources with specific
                          published content.
        :param processed: Optional. Keep only resources which have been
                          processed or not.
        :param reset: Optional. Keep only resources which have been reset or
                      not.
        :param env: Optional. Keep only resources with a specific environment.
        :param created_at: Optional. Keep only resources created at a specific
                           time and date.
        :param updated_at: Optional. Keep only resources with specific latest
                           update time and date.
        """
        acl.enforce('tasks:list', context.ctx())

        filters = filter_utils.create_filters_from_request_params(
            created_at=created_at,
            workflow_name=workflow_name,
            workflow_id=workflow_id,
            state=state,
            state_info=state_info,
            updated_at=updated_at,
            name=name,
            workflow_execution_id=workflow_execution_id,
            result=result,
            published=published,
            processed=processed,
            reset=reset,
            env=env
        )

        LOG.info(
            "Fetch tasks. marker=%s, limit=%s, sort_keys=%s, sort_dirs=%s,"
            " filters=%s", marker, limit, sort_keys, sort_dirs, filters
        )

        return rest_utils.get_all(
            resources.Tasks,
            resources.Task,
            db_api.get_task_executions,
            db_api.get_task_execution,
            marker=marker,
            limit=limit,
            sort_keys=sort_keys,
            sort_dirs=sort_dirs,
            fields=fields,
            **filters
        )

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(resources.Task, wtypes.text, body=resources.Task)
    def put(self, id, task):
        """Update the specified task execution.

        :param id: Task execution ID.
        :param task: Task execution object.
        """
        acl.enforce('tasks:update', context.ctx())

        LOG.info("Update task execution [id=%s, task=%s]" % (id, task))

        task_ex = db_api.get_task_execution(id)
        task_spec = spec_parser.get_task_spec(task_ex.spec)
        task_name = task.name or None
        reset = task.reset
        env = task.env or None

        if task_name and task_name != task_ex.name:
            raise exc.WorkflowException('Task name does not match.')

        wf_ex = db_api.get_workflow_execution(task_ex.workflow_execution_id)
        wf_name = task.workflow_name or None

        if wf_name and wf_name != wf_ex.name:
            raise exc.WorkflowException('Workflow name does not match.')

        if task.state != states.RUNNING:
            raise exc.WorkflowException(
                'Invalid task state. Only updating task to rerun is supported.'
            )

        if task_ex.state != states.ERROR:
            raise exc.WorkflowException(
                'The current task execution must be in ERROR for rerun.'
                ' Only updating task to rerun is supported.'
            )

        if not task_spec.get_with_items() and not reset:
            raise exc.WorkflowException(
                'Only with-items task has the option to not reset.'
            )

        rpc.get_engine_client().rerun_workflow(
            task_ex.id,
            reset=reset,
            env=env
        )

        task_ex = db_api.get_task_execution(id)

        return _get_task_resource_with_result(task_ex)


class ExecutionTasksController(rest.RestController):
    @wsme_pecan.wsexpose(resources.Tasks, types.uuid, types.uuid, int,
                         types.uniquelist, types.list, types.uniquelist,
                         wtypes.text, wtypes.text, types.uuid, STATE_TYPES,
                         wtypes.text, wtypes.text, types.jsontype, bool,
                         wtypes.text, wtypes.text, bool, types.jsontype)
    def get_all(self, workflow_execution_id, marker=None, limit=None,
                sort_keys='created_at', sort_dirs='asc', fields='', name=None,
                workflow_name=None, workflow_id=None, state=None,
                state_info=None, result=None, published=None, processed=None,
                created_at=None, updated_at=None, reset=None, env=None):
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
        :param workflow_id: Optional. Keep only resources with a specific
                            workflow ID.
        :param workflow_execution_id: Optional. Keep only resources with a
                                      specific workflow execution ID.
        :param state: Optional. Keep only resources with a specific state.
        :param state_info: Optional. Keep only resources with specific
                           state information.
        :param result: Optional. Keep only resources with a specific result.
        :param published: Optional. Keep only resources with specific
                          published content.
        :param processed: Optional. Keep only resources which have been
                          processed or not.
        :param reset: Optional. Keep only resources which have been reset or
                      not.
        :param env: Optional. Keep only resources with a specific environment.
        :param created_at: Optional. Keep only resources created at a specific
                           time and date.
        :param updated_at: Optional. Keep only resources with specific latest
                           update time and date.
        """
        acl.enforce('tasks:list', context.ctx())

        filters = filter_utils.create_filters_from_request_params(
            workflow_execution_id=workflow_execution_id,
            created_at=created_at,
            workflow_name=workflow_name,
            workflow_id=workflow_id,
            state=state,
            state_info=state_info,
            updated_at=updated_at,
            name=name,
            result=result,
            published=published,
            processed=processed,
            reset=reset,
            env=env
        )

        LOG.info(
            "Fetch tasks. workflow_execution_id=%s, marker=%s, limit=%s, "
            "sort_keys=%s, sort_dirs=%s, filters=%s",
            workflow_execution_id, marker, limit, sort_keys, sort_dirs,
            filters
        )

        return rest_utils.get_all(
            resources.Tasks,
            resources.Task,
            db_api.get_task_executions,
            db_api.get_task_execution,
            marker=marker,
            limit=limit,
            sort_keys=sort_keys,
            sort_dirs=sort_dirs,
            fields=fields,
            **filters
        )
