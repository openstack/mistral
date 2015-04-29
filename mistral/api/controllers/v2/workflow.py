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

import pecan
from pecan import hooks
from pecan import rest
from wsme import types as wtypes
import wsmeext.pecan as wsme_pecan

from mistral.api.controllers import resource
from mistral.api.controllers.v2 import validation
from mistral.api.hooks import content_type as ct_hook
from mistral.db.v2 import api as db_api
from mistral.openstack.common import log as logging
from mistral.services import workflows
from mistral.utils import rest_utils
from mistral.workbook import parser as spec_parser


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
        input_list = []

        for key, val in d.items():
            if hasattr(e, key):
                setattr(e, key, val)

        input = d['spec'].get('input', [])
        for param in input:
            if isinstance(param, dict):
                for k, v in param.items():
                    input_list.append("%s=%s" % (k, v))
            else:
                input_list.append(param)

        setattr(e, 'input', ", ".join(input_list) if input_list else None)

        return e


class Workflows(resource.ResourceList):
    """A collection of workflows."""

    workflows = [Workflow]

    @classmethod
    def sample(cls):
        return cls(workflows=[Workflow.sample()])


class WorkflowsController(rest.RestController, hooks.HookController):
    # TODO(nmakhotkin): Have a discussion with pecan/WSME folks in order
    # to have requests and response of different content types. Then
    # delete ContentTypeHook.
    __hooks__ = [ct_hook.ContentTypeHook("application/json", ['POST', 'PUT'])]

    validate = validation.SpecValidationController(
        spec_parser.get_workflow_list_spec_from_yaml)

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(Workflow, wtypes.text)
    def get(self, name):
        """Return the named workflow."""
        LOG.info("Fetch workflow [name=%s]" % name)

        db_model = db_api.get_workflow_definition(name)

        return Workflow.from_dict(db_model.to_dict())

    @rest_utils.wrap_pecan_controller_exception
    @pecan.expose(content_type="text/plain")
    def put(self):
        """Update one or more workflows.

        NOTE: The text is allowed to have definitions
            of multiple workflows. In this case they all will be updated.
        """
        definition = pecan.request.text

        LOG.info("Update workflow(s) [definition=%s]" % definition)

        db_wfs = workflows.update_workflows(definition)
        models_dicts = [db_wf.to_dict() for db_wf in db_wfs]

        workflow_list = [Workflow.from_dict(wf) for wf in models_dicts]

        return Workflows(workflows=workflow_list).to_string()

    @rest_utils.wrap_pecan_controller_exception
    @pecan.expose(content_type="text/plain")
    def post(self):
        """Create a new workflow.

        NOTE: The text is allowed to have definitions
            of multiple workflows. In this case they all will be created.
        """
        definition = pecan.request.text
        pecan.response.status = 201

        LOG.info("Create workflow(s) [definition=%s]" % definition)

        db_wfs = workflows.create_workflows(definition)
        models_dicts = [db_wf.to_dict() for db_wf in db_wfs]

        workflow_list = [Workflow.from_dict(wf) for wf in models_dicts]

        return Workflows(workflows=workflow_list).to_string()

    @rest_utils.wrap_pecan_controller_exception
    @wsme_pecan.wsexpose(None, wtypes.text, status_code=204)
    def delete(self, name):
        """Delete the named workflow."""
        LOG.info("Delete workflow [name=%s]" % name)

        db_api.delete_workflow_definition(name)

    @wsme_pecan.wsexpose(Workflows)
    def get_all(self):
        """Return all workflows.

        Where project_id is the same as the requester or
        project_id is different but the scope is public.
        """
        LOG.info("Fetch workflows.")

        workflows_list = [Workflow.from_dict(db_model.to_dict())
                          for db_model in db_api.get_workflow_definitions()]

        return Workflows(workflows=workflows_list)
