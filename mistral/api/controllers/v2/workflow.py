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
from mistral.utils import rest_utils
from mistral.workbook import parser as spec_parser

LOG = logging.getLogger(__name__)
SCOPE_TYPES = wtypes.Enum(str, 'private', 'public')


class Workflow(resource.Resource):
    """Workflow resource."""

    id = wtypes.text
    name = wtypes.text

    definition = wtypes.text
    tags = [wtypes.text]
    scope = SCOPE_TYPES

    created_at = wtypes.text
    updated_at = wtypes.text

    @classmethod
    def sample(cls):
        return cls(id='123e4567-e89b-12d3-a456-426655440000',
                   name='flow',
                   definition='---',
                   tags=['large', 'expensive'],
                   scope='private',
                   created_at='1970-01-01T00:00:00.000000',
                   updated_at='1970-01-01T00:00:00.000000')


class Workflows(resource.Resource):
    """A collection of Workflows."""

    workflows = [Workflow]

    @classmethod
    def sample(cls):
        return cls(workflows=[Workflow.sample()])


def _get_workflow_values(workflow):
    # Build specification in order to validate DSL and store its
    # serialized version in DB.
    values = workflow.to_dict()

    spec = spec_parser.get_workflow_spec_from_yaml(
        workflow.definition,
        workflow.name
    )

    values['spec'] = spec.to_dict()

    return values


class WorkflowsController(rest.RestController):
    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(Workflow, wtypes.text)
    def get(self, name):
        """Return the named workflow."""
        LOG.debug("Fetch workflow [name=%s]" % name)

        db_model = db_api.get_workflow(name)

        return Workflow.from_dict(db_model.to_dict())

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(Workflow, wtypes.text, body=Workflow)
    def put(self, name, workflow):
        """Update the named workflow."""
        LOG.debug("Update workflow [name=%s, workflow=%s]" % (name, workflow))

        db_model = db_api.update_workflow(
            name,
            _get_workflow_values(workflow)
        )

        return Workflow.from_dict(db_model.to_dict())

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(Workflow, body=Workflow, status_code=201)
    def post(self, workflow):
        """Create a new workflow."""
        LOG.debug("Create workflow [workflow=%s]" % workflow)

        db_model = db_api.create_workflow(_get_workflow_values(workflow))

        return Workflow.from_dict(db_model.to_dict())

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
