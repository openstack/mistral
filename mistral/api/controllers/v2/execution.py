# Copyright 2013 - Mirantis, Inc.
# Copyright 2015 - StackStorm, Inc.
# Copyright 2015 Huawei Technologies Co., Ltd.
# Copyright 2016 - Brocade Communications Systems, Inc.
# Copyright 2018 - Extreme Networks, Inc.
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
from oslo_utils import uuidutils
from pecan import rest
from wsme import types as wtypes
import wsmeext.pecan as wsme_pecan

from mistral.api import access_control as acl
from mistral.api.controllers.v2 import execution_report
from mistral.api.controllers.v2 import resources
from mistral.api.controllers.v2 import task
from mistral.api.controllers.v2 import types
from mistral import context
from mistral.db.v2 import api as db_api
from mistral.db.v2.sqlalchemy import models as db_models
from mistral import exceptions as exc
from mistral.rpc import clients as rpc
from mistral.services import workflows as wf_service
from mistral.utils import filter_utils
from mistral.utils import merge_dicts
from mistral.utils import rest_utils
from mistral.workflow import states

LOG = logging.getLogger(__name__)

STATE_TYPES = wtypes.Enum(
    str,
    states.IDLE,
    states.RUNNING,
    states.SUCCESS,
    states.ERROR,
    states.PAUSED,
    states.CANCELLED
)


def _load_deferred_output_field(ex):
    if ex:
        # We need to refer to this lazy-load field explicitly in
        # order to make sure that it is correctly loaded.
        hasattr(ex, 'output')

    return ex


def _get_workflow_execution_resource(wf_ex):
    _load_deferred_output_field(wf_ex)

    return resources.Execution.from_db_model(wf_ex)


# Use retries to prevent possible failures.
@rest_utils.rest_retry_on_db_error
def _get_workflow_execution(id, must_exist=True):
    with db_api.transaction():
        if must_exist:
            wf_ex = db_api.get_workflow_execution(id)
        else:
            wf_ex = db_api.load_workflow_execution(id)

        return _load_deferred_output_field(wf_ex)


# TODO(rakhmerov): Make sure to make all needed renaming on public API.


class ExecutionsController(rest.RestController):
    tasks = task.ExecutionTasksController()
    report = execution_report.ExecutionReportController()

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(resources.Execution, wtypes.text)
    def get(self, id):
        """Return the specified Execution.

        :param id: UUID of execution to retrieve.
        """
        acl.enforce("executions:get", context.ctx())

        LOG.debug("Fetch execution [id=%s]", id)

        wf_ex = _get_workflow_execution(id)

        return resources.Execution.from_db_model(wf_ex)

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(
        resources.Execution,
        wtypes.text,
        body=resources.Execution
    )
    def put(self, id, wf_ex):
        """Update the specified workflow execution.

        :param id: UUID of execution to update.
        :param wf_ex: Execution object.
        """
        acl.enforce('executions:update', context.ctx())

        LOG.debug('Update execution [id=%s, execution=%s]', id, wf_ex)

        @rest_utils.rest_retry_on_db_error
        def _compute_delta(wf_ex):
            with db_api.transaction():
                # ensure that workflow execution exists
                db_api.get_workflow_execution(
                    id,
                    fields=(db_models.WorkflowExecution.id,)
                )

                delta = {}

                if wf_ex.state:
                    delta['state'] = wf_ex.state

                if wf_ex.description:
                    delta['description'] = wf_ex.description

                if wf_ex.params and wf_ex.params.get('env'):
                    delta['env'] = wf_ex.params.get('env')

                # Currently we can change only state, description, or env.
                if len(delta.values()) <= 0:
                    raise exc.InputException(
                        'The property state, description, or env '
                        'is not provided for update.'
                    )

                # Description cannot be updated together with state.
                if delta.get('description') and delta.get('state'):
                    raise exc.InputException(
                        'The property description must be updated '
                        'separately from state.'
                    )

                # If state change, environment cannot be updated
                # if not RUNNING.
                if (delta.get('env') and
                        delta.get('state') and
                        delta['state'] != states.RUNNING):
                    raise exc.InputException(
                        'The property env can only be updated when workflow '
                        'execution is not running or on resume from pause.'
                    )

                if delta.get('description'):
                    wf_ex = db_api.update_workflow_execution(
                        id,
                        {'description': delta['description']}
                    )

                if not delta.get('state') and delta.get('env'):
                    wf_ex = db_api.get_workflow_execution(id)
                    wf_ex = wf_service.update_workflow_execution_env(
                        wf_ex,
                        delta.get('env')
                    )

                return delta, wf_ex

        delta, wf_ex = _compute_delta(wf_ex)

        if delta.get('state'):
            if states.is_paused(delta.get('state')):
                wf_ex = rpc.get_engine_client().pause_workflow(id)
            elif delta.get('state') == states.RUNNING:
                wf_ex = rpc.get_engine_client().resume_workflow(
                    id,
                    env=delta.get('env')
                )
            elif states.is_completed(delta.get('state')):
                msg = wf_ex.state_info if wf_ex.state_info else None
                wf_ex = rpc.get_engine_client().stop_workflow(
                    id,
                    delta.get('state'),
                    msg
                )
            else:
                # To prevent changing state in other cases throw a message.
                raise exc.InputException(
                    "Cannot change state to %s. Allowed states are: '%s" % (
                        wf_ex.state,
                        ', '.join([
                            states.RUNNING,
                            states.PAUSED,
                            states.SUCCESS,
                            states.ERROR,
                            states.CANCELLED
                        ])
                    )
                )

        return resources.Execution.from_dict(
            wf_ex if isinstance(wf_ex, dict) else wf_ex.to_dict()
        )

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(
        resources.Execution,
        body=resources.Execution,
        status_code=201
    )
    def post(self, wf_ex):
        """Create a new Execution.

        :param wf_ex: Execution object with input content.
        """
        acl.enforce('executions:create', context.ctx())

        LOG.debug("Create execution [execution=%s]", wf_ex)

        exec_dict = wf_ex.to_dict()

        exec_id = exec_dict.get('id')

        if not exec_id:
            exec_id = uuidutils.generate_uuid()
            LOG.debug("Generated execution id [exec_id=%s]", exec_id)
            exec_dict.update({'id': exec_id})
            wf_ex = None
        else:
            # If ID is present we need to check if such execution exists.
            # If yes, the method just returns the object. If not, the ID
            # will be used to create a new execution.
            wf_ex = _get_workflow_execution(exec_id, must_exist=False)
            if wf_ex:
                return resources.Execution.from_db_model(wf_ex)

        source_execution_id = exec_dict.get('source_execution_id')

        source_exec_dict = None

        if source_execution_id:
            # If source execution is present we will perform a lookup for
            # previous workflow execution model and the information to start
            # a new workflow based on that information.
            source_exec_dict = db_api.get_workflow_execution(
                source_execution_id).to_dict()

            exec_dict['description'] = "{} Based on the execution '{}'".format(
                exec_dict['description'], source_execution_id)
            exec_dict['description'] = exec_dict['description'].strip()

        result_exec_dict = merge_dicts(source_exec_dict, exec_dict)

        if not (result_exec_dict.get('workflow_id') or
                result_exec_dict.get('workflow_name')):
            raise exc.WorkflowException(
                "Workflow ID or workflow name must be provided. Workflow ID is"
                " recommended."
            )

        engine = rpc.get_engine_client()

        result = engine.start_workflow(
            result_exec_dict.get('workflow_id',
                                 result_exec_dict.get('workflow_name')),
            result_exec_dict.get('workflow_namespace', ''),
            result_exec_dict.get('id'),
            result_exec_dict.get('input'),
            description=result_exec_dict.get('description', ''),
            **result_exec_dict.get('params') or {}
        )

        return resources.Execution.from_dict(result)

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(None, wtypes.text, bool, status_code=204)
    def delete(self, id, force=False):
        """Delete the specified Execution.

        :param id: UUID of execution to delete.
        :param force: Optional. Force the deletion of unfinished executions.
                      Default: false. While the api is backward compatible
                      the behaviour is not the same. The new default is the
                      safer option
        """
        acl.enforce('executions:delete', context.ctx())

        LOG.debug("Delete execution [id=%s]", id)

        if not force:
            state = db_api.get_workflow_execution(
                id,
                fields=(db_models.WorkflowExecution.state,)
            )[0]

            if not states.is_completed(state):
                raise exc.NotAllowedException(
                    "Only completed executions can be deleted. "
                    "Use --force to override this. "
                    "Execution {} is in {} state".format(id, state)
                )

        return rest_utils.rest_retry_on_db_error(
            db_api.delete_workflow_execution
        )(id)

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(resources.Executions, types.uuid, int,
                         types.uniquelist, types.list, types.uniquelist,
                         wtypes.text, types.uuid, wtypes.text, types.jsontype,
                         types.uuid, types.uuid, STATE_TYPES, wtypes.text,
                         types.jsontype, types.jsontype, wtypes.text,
                         wtypes.text, bool, types.uuid, bool)
    def get_all(self, marker=None, limit=None, sort_keys='created_at',
                sort_dirs='asc', fields='', workflow_name=None,
                workflow_id=None, description=None, params=None,
                task_execution_id=None, root_execution_id=None, state=None,
                state_info=None, input=None, output=None, created_at=None,
                updated_at=None, include_output=None, project_id=None,
                all_projects=False):
        """Return all Executions.

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
        :param task_execution_id: Optional. Keep only resources with a
                                  specific task execution ID.
        :param root_execution_id: Optional. Keep only resources with a
                                  specific root execution ID.
        :param state: Optional. Keep only resources with a specific state.
        :param state_info: Optional. Keep only resources with specific
                           state information.
        :param input: Optional. Keep only resources with a specific input.
        :param output: Optional. Keep only resources with a specific output.
        :param created_at: Optional. Keep only resources created at a specific
                           time and date.
        :param updated_at: Optional. Keep only resources with specific latest
                           update time and date.
        :param include_output: Optional. Include the output for all executions
                               in the list.
        :param project_id: Optional. Only get exectuions belong to the project.
            Admin required.
        :param all_projects: Optional. Get resources of all projects. Admin
            required.
        """
        acl.enforce('executions:list', context.ctx())

        if all_projects or project_id:
            acl.enforce('executions:list:all_projects', context.ctx())

        filters = filter_utils.create_filters_from_request_params(
            created_at=created_at,
            workflow_name=workflow_name,
            workflow_id=workflow_id,
            params=params,
            task_execution_id=task_execution_id,
            state=state,
            state_info=state_info,
            input=input,
            output=output,
            updated_at=updated_at,
            description=description,
            project_id=project_id,
            root_execution_id=root_execution_id,
        )

        LOG.debug(
            "Fetch executions. marker=%s, limit=%s, sort_keys=%s, "
            "sort_dirs=%s, filters=%s, all_projects=%s", marker, limit,
            sort_keys, sort_dirs, filters, all_projects
        )

        if include_output:
            resource_function = _get_workflow_execution_resource
        else:
            resource_function = None

        return rest_utils.get_all(
            resources.Executions,
            resources.Execution,
            db_api.get_workflow_executions,
            db_api.get_workflow_execution,
            resource_function=resource_function,
            marker=marker,
            limit=limit,
            sort_keys=sort_keys,
            sort_dirs=sort_dirs,
            fields=fields,
            all_projects=all_projects,
            **filters
        )
