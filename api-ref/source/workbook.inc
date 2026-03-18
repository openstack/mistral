.. -*- rst -*-

======================
 Workbooks (workbooks)
======================

Manage workbook definitions.

A workbook is a container for workflows, actions, and triggers that are
logically related. It provides a convenient way to package related
definitions together using a single YAML definition file.

List Workbooks
==============

.. rest_method:: GET /v2/workbooks

Lists all workbooks.

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
  - name: workbook_filter_name
  - definition: workbook_filter_definition
  - tags: workbook_filter_tags
  - scope: workbook_filter_scope
  - created_at: workbook_filter_created_at
  - updated_at: workbook_filter_updated_at
  - namespace: namespace

Response
--------

.. rest_parameters:: parameters.yaml

  - workbooks: workbooks
  - id: workbook_id
  - name: workbook_name_body
  - namespace: workbook_namespace
  - definition: workbook_definition
  - tags: workbook_tags
  - scope: workbook_scope
  - project_id: workbook_project_id
  - created_at: workbook_created_at
  - updated_at: workbook_updated_at

Create Workbook
===============

.. rest_method:: POST /v2/workbooks

Creates a workbook from a YAML definition.

The request body should contain a YAML workbook definition conforming
to the Mistral v2 DSL.

Normal response codes: 201

Error response codes: badRequest(400), unauthorized(401), forbidden(403),
conflict(409)

Request
-------

.. rest_parameters:: parameters.yaml

  - namespace: namespace
  - scope: scope
  - skip_validation: skip_validation

The request body is a YAML workbook definition in ``text/plain`` format.

Response
--------

.. rest_parameters:: parameters.yaml

  - id: workbook_id
  - name: workbook_name_body
  - namespace: workbook_namespace
  - definition: workbook_definition
  - tags: workbook_tags
  - scope: workbook_scope
  - project_id: workbook_project_id
  - created_at: workbook_created_at
  - updated_at: workbook_updated_at

Show Workbook
=============

.. rest_method:: GET /v2/workbooks/{workbook_name}

Shows details for a workbook.

Normal response codes: 200

Error response codes: unauthorized(401), forbidden(403), itemNotFound(404)

Request
-------

.. rest_parameters:: parameters.yaml

  - workbook_name: workbook_name
  - namespace: namespace
  - fields: fields

Response
--------

.. rest_parameters:: parameters.yaml

  - id: workbook_id
  - name: workbook_name_body
  - namespace: workbook_namespace
  - definition: workbook_definition
  - tags: workbook_tags
  - scope: workbook_scope
  - project_id: workbook_project_id
  - created_at: workbook_created_at
  - updated_at: workbook_updated_at

Update Workbook
===============

.. rest_method:: PUT /v2/workbooks

Updates a workbook.

The request body should contain a YAML workbook definition conforming
to the Mistral v2 DSL. The workbook is identified by name within
the definition.

Normal response codes: 200

Error response codes: badRequest(400), unauthorized(401), forbidden(403),
itemNotFound(404)

Request
-------

.. rest_parameters:: parameters.yaml

  - namespace: namespace
  - scope: scope
  - skip_validation: skip_validation

The request body is a YAML workbook definition in ``text/plain`` format.

Response
--------

.. rest_parameters:: parameters.yaml

  - id: workbook_id
  - name: workbook_name_body
  - namespace: workbook_namespace
  - definition: workbook_definition
  - tags: workbook_tags
  - scope: workbook_scope
  - project_id: workbook_project_id
  - created_at: workbook_created_at
  - updated_at: workbook_updated_at

Delete Workbook
===============

.. rest_method:: DELETE /v2/workbooks/{workbook_name}

Deletes a workbook.

Normal response codes: 204

Error response codes: unauthorized(401), forbidden(403), itemNotFound(404)

Request
-------

.. rest_parameters:: parameters.yaml

  - workbook_name: workbook_name
  - namespace: namespace

Response
--------

There is no body content for the response of a successful DELETE action.
