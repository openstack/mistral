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
from pecan import rest
from wsme import types as wtypes
import wsmeext.pecan as wsme_pecan

from mistral.api.controllers import resource
from mistral.api.controllers.v2 import task
from mistral.db.v2 import api as db_api
from mistral.engine import rpc
from mistral import exceptions as exc
from mistral.openstack.common import log as logging
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

    params = wtypes.text
    "params define workflow type specific parameters. For example, reverse \
    workflow takes one parameter 'task_name' that defines a target task."

    state = wtypes.text
    "state can be one of: RUNNING, SUCCESS, ERROR, PAUSED"

    state_info = wtypes.text
    "an optional state information string"

    input = wtypes.text
    "input is a JSON structure containing workflow input values."
    output = wtypes.text
    "output is a workflow output."

    created_at = wtypes.text
    updated_at = wtypes.text

    # Context is a JSON object but since WSME doesn't support arbitrary
    # dictionaries we have to use text type convert to json and back manually.
    def to_dict(self):
        d = super(Execution, self).to_dict()

        if d.get('input'):
            d['input'] = json.loads(d['input'])

        if d.get('output'):
            d['output'] = json.loads(d['output'])

        if d.get('params'):
            d['params'] = json.loads(d['params'])

        return d

    @classmethod
    def from_dict(cls, d):
        e = cls()

        for key, val in d.items():
            if hasattr(e, key):
                # Nonetype check for dictionary must be explicit
                if key in ['input', 'output', 'params'] and val is not None:
                    val = json.dumps(val)
                setattr(e, key, val)

        return e

    @classmethod
    def sample(cls):
        return cls(id='123e4567-e89b-12d3-a456-426655440000',
                   workflow_name='flow',
                   state='SUCCESS',
                   input='{}',
                   output='{}',
                   params='{"env": {"k1": "abc", "k2": 123}}',
                   created_at='1970-01-01T00:00:00.000000',
                   updated_at='1970-01-01T00:00:00.000000')


class Executions(resource.Resource):
    """A collection of Execution resources."""

    executions = [Execution]

    @classmethod
    def sample(cls):
        return cls(executions=[Execution.sample()])


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
    def put(self, id, execution):
        """Update the specified Execution.

        :param id: execution ID.
        :param execution: Execution objects
        """
        LOG.info("Update execution [id=%s, execution=%s]" %
                 (id, execution))
        db_api.ensure_workflow_execution_exists(id)

        # Currently we can change only state.
        if not execution.state:
            raise exc.DataAccessException(
                "Only state of execution can change. "
                "Missing 'state' property."
            )

        new_state = execution.state
        msg = execution.state_info

        if new_state == states.PAUSED:
            wf_ex = rpc.get_engine_client().pause_workflow(id)
        elif new_state == states.RUNNING:
            wf_ex = rpc.get_engine_client().resume_workflow(id)
        elif new_state in [states.SUCCESS, states.ERROR]:
            wf_ex = rpc.get_engine_client().stop_workflow(id, new_state, msg)
        else:
            # To prevent changing state in other cases throw a message.
            raise exc.DataAccessException(
                "Can not change state to %s. Allowed states are: '%s" %
                (new_state, ", ".join([states.RUNNING, states.PAUSED,
                 states.SUCCESS, states.ERROR]))
            )

        return Execution.from_dict(
            wf_ex if isinstance(wf_ex, dict) else wf_ex.to_dict()
        )

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(Execution, body=Execution, status_code=201)
    def post(self, execution):
        """Create a new Execution.

        :param execution: Execution object with input content.
        """
        LOG.info("Create execution [execution=%s]" % execution)

        engine = rpc.get_engine_client()
        exec_dict = execution.to_dict()

        result = engine.start_workflow(
            exec_dict['workflow_name'],
            exec_dict.get('input'),
            **exec_dict.get('params') or {}
        )

        return Execution.from_dict(result)

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(None, wtypes.text, status_code=204)
    def delete(self, id):
        """Delete the specified Execution."""
        LOG.info("Delete execution [id=%s]" % id)

        return db_api.delete_workflow_execution(id)

    @wsme_pecan.wsexpose(Executions)
    def get_all(self):
        """Return all Executions."""
        LOG.info("Fetch executions")

        wf_executions = [
            Execution.from_dict(db_model.to_dict())
            for db_model in db_api.get_workflow_executions()
        ]

        return Executions(executions=wf_executions)
