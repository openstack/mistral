# -*- coding: utf-8 -*-
#
# Copyright 2013 - Mirantis, Inc.
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
from mistral.engine1 import rpc
from mistral.openstack.common import log as logging
from mistral.utils import rest_utils


LOG = logging.getLogger(__name__)


class Execution(resource.Resource):
    """Execution resource."""

    id = wtypes.text
    workflow_name = wtypes.text
    params = wtypes.text

    state = wtypes.text
    # Context is a JSON object but since WSME doesn't support arbitrary
    # dictionaries we have to use text type convert to json and back manually.
    input = wtypes.text
    output = wtypes.text

    created_at = wtypes.text
    updated_at = wtypes.text

    def to_dict(self):
        d = super(Execution, self).to_dict()

        if d.get('output'):
            d['output'] = json.loads(d['output'])

        if d.get('params'):
            params = json.loads(d['params'])
            del d['params']
            for k, v in params.items():
                d[k] = v

        return d

    @classmethod
    def from_dict(cls, d):
        e = cls()

        for key, val in d.items():
            if hasattr(e, key):
                # Nonetype check for dictionary must be explicit
                if key == 'input' or key == 'output' and val is not None:
                    val = json.dumps(val)
                setattr(e, key, val)

        setattr(e, 'workflow_name', d['wf_name'])

        return e

    @classmethod
    def sample(cls):
        return cls(id='123e4567-e89b-12d3-a456-426655440000',
                   workflow_name='flow',
                   state='SUCCESS',
                   input='{}',
                   output='{}',
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
        LOG.debug("Fetch execution [id=%s]" % id)

        return Execution.from_dict(db_api.get_execution(id).to_dict())

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(Execution, wtypes.text, body=Execution)
    def put(self, id, execution):
        """Update the specified Execution."""
        LOG.debug("Update execution [id=%s, execution=%s]" %
                  (id, execution))

        db_model = db_api.update_execution(id, execution.to_dict())

        return Execution.from_dict(db_model.to_dict())

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(Execution, body=Execution, status_code=201)
    def post(self, execution):
        """Create a new Execution."""
        LOG.debug("Create execution [execution=%s]" % execution)

        engine = rpc.get_engine_client()
        exec_dict = execution.to_dict()
        result = engine.start_workflow(
            workflow_name=exec_dict['workflow_name'],
            workflow_input=exec_dict.get('input'),
            **exec_dict.get('params') or {}
        )

        return Execution.from_dict(result)

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(None, wtypes.text, status_code=204)
    def delete(self, id):
        """Delete the specified Execution."""
        LOG.debug("Delete execution [id=%s]" % id)

        return db_api.delete_execution(id)

    @wsme_pecan.wsexpose(Executions)
    def get_all(self):
        """Return all Executions."""
        LOG.debug("Fetch executions")

        executions = [Execution.from_dict(db_model.to_dict())
                      for db_model in db_api.get_executions()]

        return Executions(executions=executions)
