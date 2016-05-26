# -*- coding: utf-8 -*-
#
# Copyright 2015 - Mirantis, Inc.
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

from mistral.api.controllers import resource
from mistral.api.controllers.v2 import types
from mistral.db.v2 import api as db_api
from mistral.engine import rpc
from mistral import exceptions as exc
from mistral.utils import rest_utils
from mistral.workflow import states
from mistral.workflow import utils as wf_utils


LOG = logging.getLogger(__name__)


class ActionExecution(resource.Resource):
    """ActionExecution resource."""

    id = wtypes.text

    workflow_name = wtypes.text
    task_name = wtypes.text
    task_execution_id = wtypes.text

    state = wtypes.text

    state_info = wtypes.text
    tags = [wtypes.text]
    name = wtypes.text
    description = wtypes.text
    accepted = bool
    input = types.jsontype
    output = types.jsontype
    created_at = wtypes.text
    updated_at = wtypes.text
    params = types.jsontype

    @classmethod
    def sample(cls):
        return cls(
            id='123e4567-e89b-12d3-a456-426655440000',
            workflow_name='flow',
            task_name='task1',
            workflow_execution_id='653e4127-e89b-12d3-a456-426655440076',
            task_execution_id='343e45623-e89b-12d3-a456-426655440090',
            state=states.SUCCESS,
            state_info=states.SUCCESS,
            tags=['foo', 'fee'],
            name='std.echo',
            description='My running action',
            accepted=True,
            input={'first_name': 'John', 'last_name': 'Doe'},
            output={'some_output': 'Hello, John Doe!'},
            created_at='1970-01-01T00:00:00.000000',
            updated_at='1970-01-01T00:00:00.000000',
            params={'save_result': True}
        )


class ActionExecutions(resource.Resource):
    """A collection of action_executions."""

    action_executions = [ActionExecution]

    @classmethod
    def sample(cls):
        return cls(action_executions=[ActionExecution.sample()])


def _load_deferred_output_field(action_ex):
    # We need to refer to this lazy-load field explicitly in
    # order to make sure that it is correctly loaded.
    hasattr(action_ex, 'output')


def _get_action_execution(id):
    action_ex = db_api.get_action_execution(id)

    return _get_action_execution_resource(action_ex)


def _get_action_execution_resource(action_ex):
    _load_deferred_output_field(action_ex)

    # TODO(nmakhotkin): Get rid of using dicts for constructing resources.
    # TODO(nmakhotkin): Use db_model for this instead.
    res = ActionExecution.from_dict(action_ex.to_dict())

    task_name = (action_ex.task_execution.name
                 if action_ex.task_execution else None)
    setattr(res, 'task_name', task_name)

    return res


def _get_action_executions(task_execution_id=None):
    kwargs = {'type': 'action_execution'}

    if task_execution_id:
        kwargs['task_execution_id'] = task_execution_id

    action_execs = [
        _get_action_execution_resource(a_ex)
        for a_ex in db_api.get_action_executions(**kwargs)
    ]

    return ActionExecutions(action_executions=action_execs)


class ActionExecutionsController(rest.RestController):
    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(ActionExecution, wtypes.text)
    def get(self, id):
        """Return the specified action_execution."""
        LOG.info("Fetch action_execution [id=%s]" % id)

        return _get_action_execution(id)

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(ActionExecution,
                         body=ActionExecution, status_code=201)
    def post(self, action_ex):
        """Create new action_execution."""
        LOG.info("Create action_execution [action_execution=%s]" % action_ex)

        name = action_ex.name
        description = action_ex.description or None
        action_input = action_ex.input or {}
        params = action_ex.params or {}

        if not name:
            raise exc.InputException(
                "Please provide at least action name to run action."
            )

        action_ex = rpc.get_engine_client().start_action(
            name,
            action_input,
            description=description,
            **params
        )

        return ActionExecution.from_dict(action_ex)

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(ActionExecution, wtypes.text, body=ActionExecution)
    def put(self, id, action_ex):
        """Update the specified action_execution."""
        LOG.info(
            "Update action_execution [id=%s, action_execution=%s]"
            % (id, action_ex)
        )

        output = action_ex.output

        if action_ex.state == states.SUCCESS:
            result = wf_utils.Result(data=output)
        elif action_ex.state == states.ERROR:
            if not output:
                output = 'Unknown error'
            result = wf_utils.Result(error=output)
        else:
            raise exc.InvalidResultException(
                "Error. Expected on of %s, actual: %s" %
                ([states.SUCCESS, states.ERROR], action_ex.state)
            )

        values = rpc.get_engine_client().on_action_complete(id, result)

        return ActionExecution.from_dict(values)

    @wsme_pecan.wsexpose(ActionExecutions)
    def get_all(self):
        """Return all action_executions within the execution."""
        LOG.info("Fetch action_executions")

        return _get_action_executions()

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(None, wtypes.text, status_code=204)
    def delete(self, id):
        """Delete the specified action_execution."""

        LOG.info("Delete action_execution [id=%s]" % id)

        if not cfg.CONF.api.allow_action_execution_deletion:
            raise exc.NotAllowedException("Action execution deletion is not "
                                          "allowed.")

        action_ex = db_api.get_action_execution(id)

        if action_ex.task_execution_id:
            raise exc.NotAllowedException("Only ad-hoc action execution can "
                                          "be deleted.")

        if not states.is_completed(action_ex.state):
            raise exc.NotAllowedException("Only completed action execution "
                                          "can be deleted.")

        return db_api.delete_action_execution(id)


class TasksActionExecutionController(rest.RestController):
    @wsme_pecan.wsexpose(ActionExecutions, wtypes.text)
    def get_all(self, task_execution_id):
        """Return all action executions within the task execution."""
        LOG.info("Fetch action executions")

        return _get_action_executions(task_execution_id=task_execution_id)

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(ActionExecution, wtypes.text, wtypes.text)
    def get(self, task_execution_id, action_ex_id):
        """Return the specified action_execution."""
        LOG.info("Fetch action_execution [id=%s]" % action_ex_id)

        return _get_action_execution(action_ex_id)
