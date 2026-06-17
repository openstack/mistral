.. -*- rst -*-

==================================
 Dynamic Actions (dynamic_actions)
==================================

Manage dynamic actions.

A dynamic action is an action defined by referencing a Python class within a
code source. Unlike ad-hoc actions (which wrap existing actions with
predefined input), dynamic actions point to a class in an uploaded code source
module. This allows users to create fully custom actions without installing
Python packages on the Mistral server.

List Dynamic Actions
====================

.. rest_method:: GET /v2/dynamic_actions

Lists all dynamic actions.

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
  - name: dynamic_action_filter_name
  - scope: dynamic_action_filter_scope
  - tags: dynamic_action_filter_tags
  - project_id: dynamic_action_filter_project_id
  - created_at: dynamic_action_filter_created_at
  - updated_at: dynamic_action_filter_updated_at
  - all_projects: all_projects
  - namespace: namespace

Response
--------

.. rest_parameters:: parameters.yaml

  - dynamic_actions: dynamic_actions
  - id: dynamic_action_id
  - name: dynamic_action_name
  - namespace: dynamic_action_namespace
  - class_name: dynamic_action_class_name
  - code_source_id: dynamic_action_code_source_id
  - code_source_name: dynamic_action_code_source_name
  - scope: dynamic_action_scope
  - project_id: dynamic_action_project_id
  - created_at: dynamic_action_created_at
  - updated_at: dynamic_action_updated_at

Create Dynamic Action
=====================

.. rest_method:: POST /v2/dynamic_actions

Creates a dynamic action.

Either ``code_source_id`` or ``code_source_name`` must be provided to
identify the code source containing the action class.

Normal response codes: 201

Error response codes: badRequest(400), unauthorized(401), forbidden(403),
conflict(409)

Request
-------

.. rest_parameters:: parameters.yaml

  - name: dynamic_action_name_create
  - class_name: dynamic_action_class_name_create
  - code_source_id: dynamic_action_code_source_id_create
  - code_source_name: dynamic_action_code_source_name_create
  - namespace: namespace

Response
--------

.. rest_parameters:: parameters.yaml

  - id: dynamic_action_id
  - name: dynamic_action_name
  - namespace: dynamic_action_namespace
  - class_name: dynamic_action_class_name
  - code_source_id: dynamic_action_code_source_id
  - code_source_name: dynamic_action_code_source_name
  - scope: dynamic_action_scope
  - project_id: dynamic_action_project_id
  - created_at: dynamic_action_created_at
  - updated_at: dynamic_action_updated_at

Show Dynamic Action
===================

.. rest_method:: GET /v2/dynamic_actions/{dynamic_action_identifier}

Shows details for a dynamic action.

Normal response codes: 200

Error response codes: unauthorized(401), forbidden(403), itemNotFound(404)

Request
-------

.. rest_parameters:: parameters.yaml

  - dynamic_action_identifier: dynamic_action_identifier
  - namespace: namespace
  - fields: fields

Response
--------

.. rest_parameters:: parameters.yaml

  - id: dynamic_action_id
  - name: dynamic_action_name
  - namespace: dynamic_action_namespace
  - class_name: dynamic_action_class_name
  - code_source_id: dynamic_action_code_source_id
  - code_source_name: dynamic_action_code_source_name
  - scope: dynamic_action_scope
  - project_id: dynamic_action_project_id
  - created_at: dynamic_action_created_at
  - updated_at: dynamic_action_updated_at

Update Dynamic Action
=====================

.. rest_method:: PUT /v2/dynamic_actions

Updates a dynamic action.

Either ``name`` or ``id`` must be provided to identify the dynamic action.

Normal response codes: 200

Error response codes: badRequest(400), unauthorized(401), forbidden(403),
itemNotFound(404)

Request
-------

.. rest_parameters:: parameters.yaml

  - name: dynamic_action_name
  - id: dynamic_action_id
  - class_name: dynamic_action_class_name
  - code_source_id: dynamic_action_code_source_id
  - code_source_name: dynamic_action_code_source_name
  - scope: scope
  - namespace: namespace

Response
--------

.. rest_parameters:: parameters.yaml

  - id: dynamic_action_id
  - name: dynamic_action_name
  - namespace: dynamic_action_namespace
  - class_name: dynamic_action_class_name
  - code_source_id: dynamic_action_code_source_id
  - code_source_name: dynamic_action_code_source_name
  - scope: dynamic_action_scope
  - project_id: dynamic_action_project_id
  - created_at: dynamic_action_created_at
  - updated_at: dynamic_action_updated_at

Delete Dynamic Action
=====================

.. rest_method:: DELETE /v2/dynamic_actions/{dynamic_action_identifier}

Deletes a dynamic action.

Normal response codes: 204

Error response codes: unauthorized(401), forbidden(403), itemNotFound(404)

Request
-------

.. rest_parameters:: parameters.yaml

  - dynamic_action_identifier: dynamic_action_identifier
  - namespace: namespace

Response
--------

There is no body content for the response of a successful DELETE action.
