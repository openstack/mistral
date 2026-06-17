.. -*- rst -*-

==============================
 Code Sources (code_sources)
==============================

Manage code sources.

A code source is a Python module uploaded to Mistral that contains action
classes. Code sources are used in conjunction with dynamic actions to define
custom actions without needing to install Python packages on the Mistral
server. The content of a code source is the raw Python source code.

List Code Sources
=================

.. rest_method:: GET /v2/code_sources

Lists all code sources.

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
  - name: code_source_filter_name
  - scope: code_source_filter_scope
  - tags: code_source_filter_tags
  - project_id: code_source_filter_project_id
  - created_at: code_source_filter_created_at
  - updated_at: code_source_filter_updated_at
  - all_projects: all_projects
  - namespace: namespace

Response
--------

.. rest_parameters:: parameters.yaml

  - code_sources: code_sources
  - id: code_source_id
  - name: code_source_name
  - namespace: code_source_namespace
  - content: code_source_content
  - version: code_source_version
  - scope: code_source_scope
  - actions: code_source_actions
  - project_id: code_source_project_id
  - created_at: code_source_created_at
  - updated_at: code_source_updated_at

Create Code Source
==================

.. rest_method:: POST /v2/code_sources

Creates a code source.

The request body should contain the raw Python source code as plain text.
The ``name`` parameter identifies the module name.

Normal response codes: 201

Error response codes: badRequest(400), unauthorized(401), forbidden(403),
conflict(409)

Request
-------

.. rest_parameters:: parameters.yaml

  - name: code_source_name_create
  - scope: scope
  - namespace: namespace

The request body should be the raw Python source code with content type
``text/plain``.

Response
--------

.. rest_parameters:: parameters.yaml

  - id: code_source_id
  - name: code_source_name
  - namespace: code_source_namespace
  - content: code_source_content
  - version: code_source_version
  - scope: code_source_scope
  - actions: code_source_actions
  - project_id: code_source_project_id
  - created_at: code_source_created_at
  - updated_at: code_source_updated_at

Show Code Source
================

.. rest_method:: GET /v2/code_sources/{code_source_identifier}

Shows details for a code source.

Normal response codes: 200

Error response codes: unauthorized(401), forbidden(403), itemNotFound(404)

Request
-------

.. rest_parameters:: parameters.yaml

  - code_source_identifier: code_source_identifier
  - namespace: namespace
  - fields: fields

Response
--------

.. rest_parameters:: parameters.yaml

  - id: code_source_id
  - name: code_source_name
  - namespace: code_source_namespace
  - content: code_source_content
  - version: code_source_version
  - scope: code_source_scope
  - actions: code_source_actions
  - project_id: code_source_project_id
  - created_at: code_source_created_at
  - updated_at: code_source_updated_at

Update Code Source
==================

.. rest_method:: PUT /v2/code_sources

Updates a code source.

The request body should contain the updated raw Python source code as
plain text.

Normal response codes: 200

Error response codes: badRequest(400), unauthorized(401), forbidden(403),
itemNotFound(404)

Request
-------

.. rest_parameters:: parameters.yaml

  - identifier: code_source_identifier_query
  - scope: scope
  - namespace: namespace

The request body should be the raw Python source code with content type
``text/plain``.

Response
--------

.. rest_parameters:: parameters.yaml

  - id: code_source_id
  - name: code_source_name
  - namespace: code_source_namespace
  - content: code_source_content
  - version: code_source_version
  - scope: code_source_scope
  - actions: code_source_actions
  - project_id: code_source_project_id
  - created_at: code_source_created_at
  - updated_at: code_source_updated_at

Delete Code Source
==================

.. rest_method:: DELETE /v2/code_sources/{code_source_identifier}

Deletes a code source.

Normal response codes: 204

Error response codes: unauthorized(401), forbidden(403), itemNotFound(404)

Request
-------

.. rest_parameters:: parameters.yaml

  - code_source_identifier: code_source_identifier
  - namespace: namespace

Response
--------

There is no body content for the response of a successful DELETE action.
