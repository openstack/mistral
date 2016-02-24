# Copyright 2013 - Mirantis, Inc.
# Copyright 2015 - StackStorm, Inc.
# Copyright 2015 Huawei Technologies Co., Ltd.
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
import pecan
from pecan import rest
from wsme import types as wtypes
import wsmeext.pecan as wsme_pecan

from mistral.api.controllers import resource
from mistral.api.controllers.v2 import task
from mistral.api.controllers.v2 import types
from mistral.db.v2 import api as db_api
from mistral.engine import rpc
from mistral import exceptions as exc
from mistral.services import workflows as wf_service
from mistral.utils import rest_utils
from mistral.workflow import states


LOG = logging.getLogger(__name__)

# TODO(rakhmerov): Make sure to make all needed renaming on public API.


class Execution(resource.Resource):
    """Execution resource."""

    id = wtypes.text
    "id is immutable and auto assigned."

    workflow_name = wtypes.text
    "reference to workflow definition"

    workflow_id = wtypes.text
    "reference to workflow ID"

    description = wtypes.text
    "description of workflow execution."

    params = types.jsontype
    "params define workflow type specific parameters. For example, reverse \
    workflow takes one parameter 'task_name' that defines a target task."

    task_execution_id = wtypes.text
    "reference to the parent task execution"

    state = wtypes.text
    "state can be one of: IDLE, RUNNING, SUCCESS, ERROR, PAUSED"

    state_info = wtypes.text
    "an optional state information string"

    input = types.jsontype
    "input is a JSON structure containing workflow input values."

    output = types.jsontype
    "output is a workflow output."

    created_at = wtypes.text
    updated_at = wtypes.text

    @classmethod
    def sample(cls):
        return cls(id='123e4567-e89b-12d3-a456-426655440000',
                   workflow_name='flow',
                   workflow_id='123e4567-e89b-12d3-a456-426655441111',
                   description='this is the first execution.',
                   state='SUCCESS',
                   input={},
                   output={},
                   params={'env': {'k1': 'abc', 'k2': 123}},
                   created_at='1970-01-01T00:00:00.000000',
                   updated_at='1970-01-01T00:00:00.000000')


class Executions(resource.ResourceList):
    """A collection of Execution resources."""

    executions = [Execution]

    def __init__(self, **kwargs):
        self._type = 'executions'

        super(Executions, self).__init__(**kwargs)

    @classmethod
    def sample(cls):
        executions_sample = cls()
        executions_sample.executions = [Execution.sample()]
        executions_sample.next = "http://localhost:8989/v2/executions?" \
                                 "sort_keys=id,workflow_name&" \
                                 "sort_dirs=asc,desc&limit=10&" \
                                 "marker=123e4567-e89b-12d3-a456-426655440000"

        return executions_sample


class ExecutionsController(rest.RestController):
    tasks = task.ExecutionTasksController()

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(Execution, wtypes.text)
    def get(self, id):
        """Return the specified Execution."""
        LOG.info("Fetch execution [id=%s]" % id)

        return Execution.from_dict(db_api.get_workflow_execution(id).to_dict())

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(Execution, wtypes.text, body=Execution)
    def put(self, id, wf_ex):
        """Update the specified workflow execution.

        :param id: execution ID.
        :param wf_ex: Execution object.
        """
        LOG.info('Update execution [id=%s, execution=%s]' % (id, wf_ex))

        db_api.ensure_workflow_execution_exists(id)

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

        # If state change, environment cannot be updated if not RUNNING.
        if (delta.get('env') and
                delta.get('state') and delta['state'] != states.RUNNING):
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
            with db_api.transaction():
                wf_ex = db_api.get_workflow_execution(id)
                wf_ex = wf_service.update_workflow_execution_env(
                    wf_ex,
                    delta.get('env')
                )

        if delta.get('state'):
            if delta.get('state') == states.PAUSED:
                wf_ex = rpc.get_engine_client().pause_workflow(id)
            elif delta.get('state') == states.RUNNING:
                wf_ex = rpc.get_engine_client().resume_workflow(
                    id,
                    env=delta.get('env')
                )
            elif delta.get('state') in [states.SUCCESS, states.ERROR]:
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
                            states.ERROR
                        ])
                    )
                )

        return Execution.from_dict(
            wf_ex if isinstance(wf_ex, dict) else wf_ex.to_dict()
        )

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(Execution, body=Execution, status_code=201)
    def post(self, wf_ex):
        """Create a new Execution.

        :param wf_ex: Execution object with input content.
        """
        LOG.info('Create execution [execution=%s]' % wf_ex)

        engine = rpc.get_engine_client()
        exec_dict = wf_ex.to_dict()

        if not (exec_dict.get('workflow_id')
                or exec_dict.get('workflow_name')):
            raise exc.WorkflowException(
                "Workflow ID or workflow name must be provided. Workflow ID is"
                " recommended."
            )

        result = engine.start_workflow(
            exec_dict.get('workflow_id', exec_dict.get('workflow_name')),
            exec_dict.get('input'),
            exec_dict.get('description', ''),
            **exec_dict.get('params') or {}
        )

        return Execution.from_dict(result)

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(None, wtypes.text, status_code=204)
    def delete(self, id):
        """Delete the specified Execution."""
        LOG.info('Delete execution [id=%s]' % id)

        return db_api.delete_workflow_execution(id)

    @wsme_pecan.wsexpose(Executions, types.uuid, int, types.uniquelist,
                         types.list)
    def get_all(self, marker=None, limit=None, sort_keys='created_at',
                sort_dirs='asc'):
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
        """
        LOG.info(
            "Fetch executions. marker=%s, limit=%s, sort_keys=%s, "
            "sort_dirs=%s", marker, limit, sort_keys, sort_dirs
        )

        rest_utils.validate_query_params(limit, sort_keys, sort_dirs)

        marker_obj = None

        if marker:
            marker_obj = db_api.get_workflow_execution(marker)

        db_workflow_exs = db_api.get_workflow_executions(
            limit=limit,
            marker=marker_obj,
            sort_keys=sort_keys,
            sort_dirs=sort_dirs
        )

        wf_executions = [
            Execution.from_dict(db_model.to_dict())
            for db_model in db_workflow_exs
        ]

        return Executions.convert_with_links(
            wf_executions,
            limit,
            pecan.request.host_url,
            sort_keys=','.join(sort_keys),
            sort_dirs=','.join(sort_dirs)
        )
