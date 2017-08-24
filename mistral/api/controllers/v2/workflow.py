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

from mistral.api import access_control as acl
from mistral.api.controllers.v2 import member
from mistral.api.controllers.v2 import resources
from mistral.api.controllers.v2 import types
from mistral.api.controllers.v2 import validation
from mistral.api.hooks import content_type as ct_hook
from mistral import context
from mistral.db.v2 import api as db_api
from mistral import exceptions as exc
from mistral.lang import parser as spec_parser
from mistral.services import workflows
from mistral.utils import filter_utils
from mistral.utils import rest_utils


LOG = logging.getLogger(__name__)


class WorkflowsController(rest.RestController, hooks.HookController):
    # TODO(nmakhotkin): Have a discussion with pecan/WSME folks in order
    # to have requests and response of different content types. Then
    # delete ContentTypeHook.
    __hooks__ = [ct_hook.ContentTypeHook("application/json", ['POST', 'PUT'])]

    validate = validation.SpecValidationController(
        spec_parser.get_workflow_list_spec_from_yaml)

    @pecan.expose()
    def _lookup(self, identifier, sub_resource, *remainder):
        LOG.debug(
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
    @wsme_pecan.wsexpose(resources.Workflow, wtypes.text, wtypes.text)
    def get(self, identifier, namespace=''):
        """Return the named workflow.

        :param identifier: Name or UUID of the workflow to retrieve.
        :param namespace: Optional. Namespace of the workflow to retrieve.
        """
        acl.enforce('workflows:get', context.ctx())

        LOG.debug("Fetch workflow [identifier=%s]", identifier)

        # Use retries to prevent possible failures.
        r = rest_utils.create_db_retry_object()
        db_model = r.call(
            db_api.get_workflow_definition,
            identifier,
            namespace=namespace
        )

        return resources.Workflow.from_db_model(db_model)

    @rest_utils.wrap_pecan_controller_exception
    @pecan.expose(content_type="text/plain")
    def put(self, identifier=None, namespace=''):
        """Update one or more workflows.

        :param identifier: Optional. If provided, it's UUID of a workflow.
            Only one workflow can be updated with identifier param.
        :param namespace: Optional. If provided int's the namespace of the
                          workflow/workflows. currently namespace cannot be
                          changed.

        The text is allowed to have definitions of multiple workflows. In this
        case they all will be updated.
        """
        acl.enforce('workflows:update', context.ctx())

        definition = pecan.request.text
        scope = pecan.request.GET.get('scope', 'private')

        if scope not in resources.SCOPE_TYPES.values:
            raise exc.InvalidModelException(
                "Scope must be one of the following: %s; actual: "
                "%s" % (resources.SCOPE_TYPES.values, scope)
            )

        LOG.debug("Update workflow(s) [definition=%s]", definition)

        db_wfs = workflows.update_workflows(
            definition,
            scope=scope,
            identifier=identifier,
            namespace=namespace
        )

        workflow_list = [
            resources.Workflow.from_db_model(db_wf) for db_wf in db_wfs
        ]

        return (workflow_list[0].to_json() if identifier
                else resources.Workflows(workflows=workflow_list).to_json())

    @rest_utils.wrap_pecan_controller_exception
    @pecan.expose(content_type="text/plain")
    def post(self, namespace=''):
        """Create a new workflow.

        NOTE: The text is allowed to have definitions
            of multiple workflows. In this case they all will be created.

        :param namespace: Optional. The namespace to create the workflow
            in. Workflows with the same name can be added to a given
            project if are in two different namespaces.
        """
        acl.enforce('workflows:create', context.ctx())

        definition = pecan.request.text
        scope = pecan.request.GET.get('scope', 'private')
        pecan.response.status = 201

        if scope not in resources.SCOPE_TYPES.values:
            raise exc.InvalidModelException(
                "Scope must be one of the following: %s; actual: "
                "%s" % (resources.SCOPE_TYPES.values, scope)
            )

        LOG.debug("Create workflow(s) [definition=%s]", definition)

        db_wfs = workflows.create_workflows(
            definition,
            scope=scope,
            namespace=namespace
        )

        workflow_list = [
            resources.Workflow.from_db_model(db_wf) for db_wf in db_wfs
        ]

        return resources.Workflows(workflows=workflow_list).to_json()

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(None, wtypes.text, wtypes.text, status_code=204)
    def delete(self, identifier, namespace=''):
        """Delete a workflow.

        :param identifier: Name or ID of workflow to delete.
        :param namespace: Optional. Namespace of the workflow to delete.
        """
        acl.enforce('workflows:delete', context.ctx())

        LOG.debug("Delete workflow [identifier=%s, namespace=%s]",
                  identifier, namespace)

        with db_api.transaction():
            db_api.delete_workflow_definition(identifier, namespace)

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(resources.Workflows, types.uuid, int,
                         types.uniquelist, types.list, types.uniquelist,
                         wtypes.text, wtypes.text, wtypes.text, wtypes.text,
                         resources.SCOPE_TYPES, types.uuid, wtypes.text,
                         wtypes.text, bool, wtypes.text)
    def get_all(self, marker=None, limit=None, sort_keys='created_at',
                sort_dirs='asc', fields='', name=None, input=None,
                definition=None, tags=None, scope=None,
                project_id=None, created_at=None, updated_at=None,
                all_projects=False, namespace=None):
        """Return a list of workflows.

        :param marker: Optional. Pagination marker for large data sets.
        :param limit: Optional. Maximum number of resources to return in a
                      single result. Default value is None for backward
                      compatibility.
        :param sort_keys: Optional. Columns to sort results by.
                          Default: created_at.
        :param sort_dirs: Optional. Directions to sort corresponding to
                          sort_keys, "asc" or "desc" can be chosen.
                          Default: asc.
        :param fields: Optional. A specified list of fields of the resource to
                       be returned. 'id' will be included automatically in
                       fields if it's provided, since it will be used when
                       constructing 'next' link.
        :param name: Optional. Keep only resources with a specific name.
        :param namespace: Optional. Keep only resources with a specific
                          namespace
        :param input: Optional. Keep only resources with a specific input.
        :param definition: Optional. Keep only resources with a specific
                           definition.
        :param tags: Optional. Keep only resources containing specific tags.
        :param scope: Optional. Keep only resources with a specific scope.
        :param project_id: Optional. The same as the requester project_id
                           or different if the scope is public.
        :param created_at: Optional. Keep only resources created at a specific
                           time and date.
        :param updated_at: Optional. Keep only resources with specific latest
                           update time and date.
        :param all_projects: Optional. Get resources of all projects.
        """
        acl.enforce('workflows:list', context.ctx())

        if all_projects:
            acl.enforce('workflows:list:all_projects', context.ctx())

        filters = filter_utils.create_filters_from_request_params(
            created_at=created_at,
            name=name,
            scope=scope,
            tags=tags,
            updated_at=updated_at,
            input=input,
            definition=definition,
            project_id=project_id,
            namespace=namespace
        )

        LOG.debug("Fetch workflows. marker=%s, limit=%s, sort_keys=%s, "
                  "sort_dirs=%s, fields=%s, filters=%s, all_projects=%s",
                  marker, limit, sort_keys, sort_dirs, fields, filters,
                  all_projects)

        return rest_utils.get_all(
            resources.Workflows,
            resources.Workflow,
            db_api.get_workflow_definitions,
            db_api.get_workflow_definition_by_id,
            marker=marker,
            limit=limit,
            sort_keys=sort_keys,
            sort_dirs=sort_dirs,
            fields=fields,
            all_projects=all_projects,
            **filters
        )
