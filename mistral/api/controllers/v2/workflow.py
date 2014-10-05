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

from pecan import rest
from wsme import types as wtypes
import wsmeext.pecan as wsme_pecan

from mistral.api.controllers import resource
from mistral.db.v2 import api as db_api
from mistral.openstack.common import log as logging
from mistral.services import workflows
from mistral.utils import rest_utils

LOG = logging.getLogger(__name__)
SCOPE_TYPES = wtypes.Enum(str, 'private', 'public')


class Workflow(resource.Resource):
    """Workflow resource."""

    id = wtypes.text
    name = wtypes.text
    input = wtypes.text

    definition = wtypes.text
    "Workflow definition in Mistral v2 DSL"
    tags = [wtypes.text]
    scope = SCOPE_TYPES
    "'private' or 'public'"

    created_at = wtypes.text
    updated_at = wtypes.text

    @classmethod
    def sample(cls):
        return cls(id='123e4567-e89b-12d3-a456-426655440000',
                   name='flow',
                   input='param1, param2',
                   definition='HERE GOES'
                        'WORKFLOW DEFINITION IN MISTRAL DSL v2',
                   tags=['large', 'expensive'],
                   scope='private',
                   created_at='1970-01-01T00:00:00.000000',
                   updated_at='1970-01-01T00:00:00.000000')

    @classmethod
    def from_dict(cls, d):
        e = cls()

        for key, val in d.items():
            if hasattr(e, key):
                setattr(e, key, val)

        input = d['spec'].get('input')
        setattr(e, 'input', ", ".join(input) if input else None)

        return e


class Workflows(resource.Resource):
    """A collection of workflows."""

    workflows = [Workflow]

    @classmethod
    def sample(cls):
        return cls(workflows=[Workflow.sample()])


class WorkflowsController(rest.RestController):
    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(Workflow, wtypes.text)
    def get(self, name):
        """Return the named workflow."""
        LOG.debug("Fetch workflow [name=%s]" % name)

        db_model = db_api.get_workflow(name)

        return Workflow.from_dict(db_model.to_dict())

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(Workflows, body=Workflow)
    def put(self, workflow):
        """Update one or more workflows.

        NOTE: Field 'definition' is allowed to have definitions
            of multiple workflows. In this case they all will be updated.
        """
        LOG.debug("Update workflow(s) [definition=%s]" % workflow.definition)

        db_models = workflows.update_workflows(workflow.definition)

        workflows_list = [Workflow.from_dict(db_model.to_dict())
                          for db_model in db_models]

        return Workflows(workflows=workflows_list)

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(Workflows, body=Workflow, status_code=201)
    def post(self, workflow):
        """Create a new workflow.

        NOTE: Field 'definition' is allowed to have definitions
            of multiple workflows. In this case they all will be created.
        """
        LOG.debug("Create workflow(s) [definition=%s]" % workflow.definition)

        db_models = workflows.create_workflows(workflow.definition)

        workflows_list = [Workflow.from_dict(db_model.to_dict())
                          for db_model in db_models]

        return Workflows(workflows=workflows_list)

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(None, wtypes.text, status_code=204)
    def delete(self, name):
        """Delete the named workflow."""
        LOG.debug("Delete workflow [name=%s]" % name)

        db_api.delete_workflow(name)

    @wsme_pecan.wsexpose(Workflows)
    def get_all(self):
        """Return all workflows.

        Where project_id is the same as the requester or
        project_id is different but the scope is public.
        """
        LOG.debug("Fetch workflows.")

        workflows_list = [Workflow.from_dict(db_model.to_dict())
                          for db_model in db_api.get_workflows()]

        return Workflows(workflows=workflows_list)
