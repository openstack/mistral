.. -*- rst -*-

============================
 Environments (environments)
============================

Manage environments.

An environment contains a set of variables that can be used in workflows.
Environments are useful for storing configuration values such as credentials,
endpoints, or any other data that workflows may need at runtime. Environment
variables can be accessed in workflows using the ``env()`` YAQL function.

List Environments
=================

.. rest_method:: GET /v2/environments

Lists all environments.

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
  - name: environment_filter_name
  - description: environment_filter_description
  - scope: environment_filter_scope
  - created_at: environment_filter_created_at
  - updated_at: environment_filter_updated_at

Response
--------

.. rest_parameters:: parameters.yaml

  - environments: environments
  - id: environment_id
  - name: environment_name
  - description: environment_description
  - variables: environment_variables
  - scope: environment_scope
  - project_id: environment_project_id
  - created_at: environment_created_at
  - updated_at: environment_updated_at

Create Environment
==================

.. rest_method:: POST /v2/environments

Creates an environment.

The ``name``, ``description``, ``variables``, and ``scope`` fields are the
only allowed fields in the request body.

Normal response codes: 201

Error response codes: badRequest(400), unauthorized(401), forbidden(403),
conflict(409)

Request
-------

.. rest_parameters:: parameters.yaml

  - name: environment_name_create
  - description: environment_description_create
  - variables: environment_variables_create
  - scope: environment_scope

Response
--------

.. rest_parameters:: parameters.yaml

  - id: environment_id
  - name: environment_name
  - description: environment_description
  - variables: environment_variables
  - scope: environment_scope
  - project_id: environment_project_id
  - created_at: environment_created_at
  - updated_at: environment_updated_at

Show Environment
================

.. rest_method:: GET /v2/environments/{environment_name}

Shows details for an environment.

Normal response codes: 200

Error response codes: unauthorized(401), forbidden(403), itemNotFound(404)

Request
-------

.. rest_parameters:: parameters.yaml

  - environment_name: environment_name_path
  - fields: fields

Response
--------

.. rest_parameters:: parameters.yaml

  - id: environment_id
  - name: environment_name
  - description: environment_description
  - variables: environment_variables
  - scope: environment_scope
  - project_id: environment_project_id
  - created_at: environment_created_at
  - updated_at: environment_updated_at

Update Environment
==================

.. rest_method:: PUT /v2/environments

Updates an environment.

The ``name`` field must be provided to identify the environment. Only
``description``, ``variables``, and ``scope`` can be updated.

Normal response codes: 200

Error response codes: badRequest(400), unauthorized(401), forbidden(403),
itemNotFound(404)

Request
-------

.. rest_parameters:: parameters.yaml

  - name: environment_name
  - description: environment_description
  - variables: environment_variables
  - scope: scope

Response
--------

.. rest_parameters:: parameters.yaml

  - id: environment_id
  - name: environment_name
  - description: environment_description
  - variables: environment_variables
  - scope: environment_scope
  - project_id: environment_project_id
  - created_at: environment_created_at
  - updated_at: environment_updated_at

Delete Environment
==================

.. rest_method:: DELETE /v2/environments/{environment_name}

Deletes an environment.

Normal response codes: 204

Error response codes: unauthorized(401), forbidden(403), itemNotFound(404)

Request
-------

.. rest_parameters:: parameters.yaml

  - environment_name: environment_name_path

Response
--------

There is no body content for the response of a successful DELETE action.
