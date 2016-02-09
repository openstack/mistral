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
from oslo_utils import uuidutils
import pecan
from pecan import hooks
from pecan import rest
from wsme import types as wtypes
import wsmeext.pecan as wsme_pecan

from mistral.api.controllers import resource
from mistral.api.controllers.v2 import member
from mistral.api.controllers.v2 import types
from mistral.api.controllers.v2 import validation
from mistral.api.hooks import content_type as ct_hook
from mistral.db.v2 import api as db_api
from mistral import exceptions as exc
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
    project_id = wtypes.text

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
                   project_id='a7eb669e9819420ea4bd1453e672c0a7',
                   created_at='1970-01-01T00:00:00.000000',
                   updated_at='1970-01-01T00:00:00.000000')

    @classmethod
    def from_dict(cls, d):
        e = cls()
        input_list = []

        for key, val in d.items():
            if hasattr(e, key):
                setattr(e, key, val)

        if 'spec' in d:
            input = d.get('spec', {}).get('input', [])
            for param in input:
                if isinstance(param, dict):
                    for k, v in param.items():
                        input_list.append("%s=%s" % (k, v))
                else:
                    input_list.append(param)

            setattr(e, 'input', ", ".join(input_list) if input_list else '')

        return e


class Workflows(resource.ResourceList):
    """A collection of workflows."""

    workflows = [Workflow]

    def __init__(self, **kwargs):
        self._type = 'workflows'

        super(Workflows, self).__init__(**kwargs)

    @classmethod
    def sample(cls):
        workflows_sample = cls()
        workflows_sample.workflows = [Workflow.sample()]
        workflows_sample.next = ("http://localhost:8989/v2/workflows?"
                                 "sort_keys=id,name&"
                                 "sort_dirs=asc,desc&limit=10&"
                                 "marker=123e4567-e89b-12d3-a456-426655440000")

        return workflows_sample


class WorkflowsController(rest.RestController, hooks.HookController):
    # TODO(nmakhotkin): Have a discussion with pecan/WSME folks in order
    # to have requests and response of different content types. Then
    # delete ContentTypeHook.
    __hooks__ = [ct_hook.ContentTypeHook("application/json", ['POST', 'PUT'])]

    validate = validation.SpecValidationController(
        spec_parser.get_workflow_list_spec_from_yaml)

    @pecan.expose()
    def _lookup(self, identifier, sub_resource, *remainder):
        LOG.info(
            "Lookup subcontrollers of WorkflowsController, "
            "sub_resource: %s, remainder: %s.",
            sub_resource,
            remainder
        )

        if sub_resource == 'members':
            if not uuidutils.is_uuid_like(identifier):
                raise exc.WorkflowException(
                    "Only support UUID as resource identifier in resource "
                    "sharing feature."
                )

            # We don't check workflow's existence here, since a user may query
            # members of a workflow, which doesn't belong to him/her.
            return member.MembersController('workflow', identifier), remainder

        return super(WorkflowsController, self)._lookup(
            identifier,
            sub_resource,
            *remainder
        )

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(Workflow, wtypes.text)
    def get(self, identifier):
        """Return the named workflow."""
        LOG.info("Fetch workflow [identifier=%s]" % identifier)

        db_model = db_api.get_workflow_definition(identifier)

        return Workflow.from_dict(db_model.to_dict())

    @rest_utils.wrap_pecan_controller_exception
    @pecan.expose(content_type="text/plain")
    def put(self, identifier=None):
        """Update one or more workflows.

        :param identifier: Optional. If provided, it's UUID of a workflow.
            Only one workflow can be updated with identifier param.

        The text is allowed to have definitions of multiple workflows. In this
        case they all will be updated.
        """
        definition = pecan.request.text
        scope = pecan.request.GET.get('scope', 'private')

        if scope not in SCOPE_TYPES.values:
            raise exc.InvalidModelException(
                "Scope must be one of the following: %s; actual: "
                "%s" % (SCOPE_TYPES.values, scope)
            )

        LOG.info("Update workflow(s) [definition=%s]" % definition)

        db_wfs = workflows.update_workflows(
            definition,
            scope=scope,
            identifier=identifier
        )

        models_dicts = [db_wf.to_dict() for db_wf in db_wfs]
        workflow_list = [Workflow.from_dict(wf) for wf in models_dicts]

        return (workflow_list[0].to_string() if identifier
                else Workflows(workflows=workflow_list).to_string())

    @rest_utils.wrap_pecan_controller_exception
    @pecan.expose(content_type="text/plain")
    def post(self):
        """Create a new workflow.

        NOTE: The text is allowed to have definitions
            of multiple workflows. In this case they all will be created.
        """
        definition = pecan.request.text
        scope = pecan.request.GET.get('scope', 'private')
        pecan.response.status = 201

        if scope not in SCOPE_TYPES.values:
            raise exc.InvalidModelException(
                "Scope must be one of the following: %s; actual: "
                "%s" % (SCOPE_TYPES.values, scope)
            )

        LOG.info("Create workflow(s) [definition=%s]" % definition)

        db_wfs = workflows.create_workflows(definition, scope=scope)
        models_dicts = [db_wf.to_dict() for db_wf in db_wfs]

        workflow_list = [Workflow.from_dict(wf) for wf in models_dicts]

        return Workflows(workflows=workflow_list).to_string()

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(None, wtypes.text, status_code=204)
    def delete(self, identifier):
        """Delete a workflow."""
        LOG.info("Delete workflow [identifier=%s]" % identifier)

        with db_api.transaction():
            db_api.delete_workflow_definition(identifier)

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(Workflows, types.uuid, int, types.uniquelist,
                         types.list, types.uniquelist)
    def get_all(self, marker=None, limit=None, sort_keys='created_at',
                sort_dirs='asc', fields=''):
        """Return a list of workflows.

        :param marker: Optional. Pagination marker for large data sets.
        :param limit: Optional. Maximum number of resources to return in a
                      single result. Default value is None for backward
                      compatibility.
        :param sort_keys: Optional. Columns to sort results by.
                          Default: created_at.
        :param sort_dirs: Optional. Directions to sort corresponding to
                          sort_keys, "asc" or "desc" can be choosed.
                          Default: asc.
        :param fields: Optional. A specified list of fields of the resource to
                       be returned. 'id' will be included automatically in
                       fields if it's provided, since it will be used when
                       constructing 'next' link.

        Where project_id is the same as the requester or
        project_id is different but the scope is public.
        """
        LOG.info("Fetch workflows. marker=%s, limit=%s, sort_keys=%s, "
                 "sort_dirs=%s, fields=%s", marker, limit, sort_keys,
                 sort_dirs, fields)

        if fields and 'id' not in fields:
            fields.insert(0, 'id')

        rest_utils.validate_query_params(limit, sort_keys, sort_dirs)
        rest_utils.validate_fields(fields, Workflow.get_fields())

        marker_obj = None

        if marker:
            marker_obj = db_api.get_workflow_definition_by_id(marker)

        db_workflows = db_api.get_workflow_definitions(
            limit=limit,
            marker=marker_obj,
            sort_keys=sort_keys,
            sort_dirs=sort_dirs,
            fields=fields
        )

        workflows_list = []

        for data in db_workflows:
            workflow_dict = (dict(zip(fields, data)) if fields else
                             data.to_dict())
            workflows_list.append(Workflow.from_dict(workflow_dict))

        return Workflows.convert_with_links(
            workflows_list,
            limit,
            pecan.request.host_url,
            sort_keys=','.join(sort_keys),
            sort_dirs=','.join(sort_dirs),
            fields=','.join(fields) if fields else ''
        )
