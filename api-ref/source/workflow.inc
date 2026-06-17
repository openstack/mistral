.. -*- rst -*-

======================
 Workflows (workflows)
======================

Manage workflow definitions.

A workflow is the main building block of Mistral. It represents a process
that can be described in a various number of ways and that can do some job
interesting to the end user. Each workflow consists of tasks (at least one)
describing what exact steps should be made during workflow execution.

List Workflows
==============

.. rest_method:: GET /v2/workflows

Lists all workflows.

Normal response codes: 200

Error response codes: unauthorized(401), forbidden(403)

Request
-------

.. rest_parameters:: parameters.yaml

  - marker: marker
  - limit: limit
  - sort_keys: sort_keys
  - sort_dirs: sort_dirs
  - fields: fields
  - name: workflow_filter_name
  - input: workflow_filter_input
  - definition: workflow_filter_definition
  - tags: workflow_filter_tags
  - scope: workflow_filter_scope
  - project_id: workflow_filter_project_id
  - created_at: workflow_filter_created_at
  - updated_at: workflow_filter_updated_at
  - all_projects: all_projects
  - namespace: namespace

Response
--------

.. rest_parameters:: parameters.yaml

  - workflows: workflows
  - id: workflow_id
  - name: workflow_name
  - namespace: workflow_namespace
  - input: workflow_input
  - interface: workflow_interface
  - definition: workflow_definition
  - checksum: workflow_checksum
  - tags: workflow_tags
  - scope: workflow_scope
  - project_id: workflow_project_id
  - created_at: workflow_created_at
  - updated_at: workflow_updated_at

Create Workflow
===============

.. rest_method:: POST /v2/workflows

Creates one or more workflows from a YAML definition.

The request body should contain a YAML workflow definition conforming
to the Mistral v2 DSL. Multiple workflows can be defined in a single
YAML definition.

Normal response codes: 201

Error response codes: badRequest(400), unauthorized(401), forbidden(403),
conflict(409)

Request
-------

.. rest_parameters:: parameters.yaml

  - namespace: namespace
  - scope: scope
  - skip_validation: skip_validation

The request body is a YAML workflow definition in ``text/plain`` format.

Response
--------

.. rest_parameters:: parameters.yaml

  - workflows: workflows
  - id: workflow_id
  - name: workflow_name
  - namespace: workflow_namespace
  - input: workflow_input
  - interface: workflow_interface
  - definition: workflow_definition
  - checksum: workflow_checksum
  - tags: workflow_tags
  - scope: workflow_scope
  - project_id: workflow_project_id
  - created_at: workflow_created_at
  - updated_at: workflow_updated_at

Show Workflow
=============

.. rest_method:: GET /v2/workflows/{workflow_identifier}

Shows details for a workflow.

Normal response codes: 200

Error response codes: unauthorized(401), forbidden(403), itemNotFound(404)

Request
-------

.. rest_parameters:: parameters.yaml

  - workflow_identifier: workflow_identifier
  - namespace: namespace
  - fields: fields

Response
--------

.. rest_parameters:: parameters.yaml

  - id: workflow_id
  - name: workflow_name
  - namespace: workflow_namespace
  - input: workflow_input
  - interface: workflow_interface
  - definition: workflow_definition
  - checksum: workflow_checksum
  - tags: workflow_tags
  - scope: workflow_scope
  - project_id: workflow_project_id
  - created_at: workflow_created_at
  - updated_at: workflow_updated_at

Update Workflow
===============

.. rest_method:: PUT /v2/workflows/{workflow_identifier}

Updates one or more workflows.

The request body should contain a YAML workflow definition conforming
to the Mistral v2 DSL. If a workflow identifier is provided in the URL,
only a single workflow can be updated at a time, and it must be identified
by UUID.

Normal response codes: 200

Error response codes: badRequest(400), unauthorized(401), forbidden(403),
itemNotFound(404)

Request
-------

.. rest_parameters:: parameters.yaml

  - workflow_identifier: workflow_identifier
  - namespace: namespace
  - scope: scope
  - skip_validation: skip_validation

The request body is a YAML workflow definition in ``text/plain`` format.

Response
--------

.. rest_parameters:: parameters.yaml

  - workflows: workflows
  - id: workflow_id
  - name: workflow_name
  - namespace: workflow_namespace
  - input: workflow_input
  - interface: workflow_interface
  - definition: workflow_definition
  - checksum: workflow_checksum
  - tags: workflow_tags
  - scope: workflow_scope
  - project_id: workflow_project_id
  - created_at: workflow_created_at
  - updated_at: workflow_updated_at

Delete Workflow
===============

.. rest_method:: DELETE /v2/workflows/{workflow_identifier}

Deletes a workflow.

Normal response codes: 204

Error response codes: unauthorized(401), forbidden(403), itemNotFound(404)

Request
-------

.. rest_parameters:: parameters.yaml

  - workflow_identifier: workflow_identifier
  - namespace: namespace

Response
--------

There is no body content for the response of a successful DELETE action.

Validate Workflow Definition
============================

.. rest_method:: POST /v2/workflows/validate

Validates a workflow definition without creating or updating any resources.
This is useful for checking definitions for syntax errors before deploying
them.

The request body should contain the workflow definition in Mistral v2 DSL
format as plain text.

Normal response codes: 200

Error response codes: unauthorized(401), forbidden(403)

Request
-------

The request body should be the workflow definition with content type
``text/plain``.

Response
--------

.. rest_parameters:: parameters.yaml

  - valid: validation_valid
  - error: validation_error

List Workflow Members
=====================

.. rest_method:: GET /v2/workflows/{workflow_identifier}/members

Lists all members with whom the workflow has been shared.

Members represent a sharing relationship between a resource owner and
another project. Currently, only private workflows can be shared. When a
resource is shared with a project, the member starts in ``pending`` status
and must accept the share before gaining access.

This feature requires authentication to be enabled.

Normal response codes: 200

Error response codes: unauthorized(401), forbidden(403), itemNotFound(404)

Request
-------

.. rest_parameters:: parameters.yaml

  - workflow_identifier: workflow_identifier

Response
--------

.. rest_parameters:: parameters.yaml

  - members: members
  - id: member_id_body
  - resource_id: member_resource_id
  - resource_type: member_resource_type
  - project_id: member_project_id
  - member_id: member_member_id
  - status: member_status
  - created_at: member_created_at
  - updated_at: member_updated_at

Share Workflow
==============

.. rest_method:: POST /v2/workflows/{workflow_identifier}/members

Shares a private workflow with another project.

Only private workflows can be shared. The new member starts in ``pending``
status.

Normal response codes: 201

Error response codes: badRequest(400), unauthorized(401), forbidden(403),
itemNotFound(404)

Request
-------

.. rest_parameters:: parameters.yaml

  - workflow_identifier: workflow_identifier
  - member_id: member_member_id_create

Response
--------

.. rest_parameters:: parameters.yaml

  - id: member_id_body
  - resource_id: member_resource_id
  - resource_type: member_resource_type
  - project_id: member_project_id
  - member_id: member_member_id
  - status: member_status
  - created_at: member_created_at
  - updated_at: member_updated_at

Show Workflow Member
====================

.. rest_method:: GET /v2/workflows/{workflow_identifier}/members/{member_id}

Shows details for a workflow member.

Normal response codes: 200

Error response codes: unauthorized(401), forbidden(403), itemNotFound(404)

Request
-------

.. rest_parameters:: parameters.yaml

  - workflow_identifier: workflow_identifier
  - member_id: member_id_path

Response
--------

.. rest_parameters:: parameters.yaml

  - id: member_id_body
  - resource_id: member_resource_id
  - resource_type: member_resource_type
  - project_id: member_project_id
  - member_id: member_member_id
  - status: member_status
  - created_at: member_created_at
  - updated_at: member_updated_at

Update Workflow Member
======================

.. rest_method:: PUT /v2/workflows/{workflow_identifier}/members/{member_id}

Updates the status of a workflow member.

Used by the member project to accept or reject the share. The ``status``
field must be one of ``pending``, ``accepted``, or ``rejected``.

Normal response codes: 200

Error response codes: badRequest(400), unauthorized(401), forbidden(403),
itemNotFound(404)

Request
-------

.. rest_parameters:: parameters.yaml

  - workflow_identifier: workflow_identifier
  - member_id: member_id_path
  - status: member_status_update

Response
--------

.. rest_parameters:: parameters.yaml

  - id: member_id_body
  - resource_id: member_resource_id
  - resource_type: member_resource_type
  - project_id: member_project_id
  - member_id: member_member_id
  - status: member_status
  - created_at: member_created_at
  - updated_at: member_updated_at

Delete Workflow Member
======================

.. rest_method:: DELETE /v2/workflows/{workflow_identifier}/members/{member_id}

Removes a member from the workflow's share list.

Normal response codes: 204

Error response codes: unauthorized(401), forbidden(403), itemNotFound(404)

Request
-------

.. rest_parameters:: parameters.yaml

  - workflow_identifier: workflow_identifier
  - member_id: member_id_path

Response
--------

There is no body content for the response of a successful DELETE action.
