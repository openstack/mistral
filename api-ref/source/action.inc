.. -*- rst -*-

==================
 Actions (actions)
==================

Manage action definitions.

An action defines a particular step that can be performed as part of a
workflow task. Mistral comes with a set of built-in system actions (e.g.,
HTTP requests, email sending) and also allows users to define custom
actions using the Mistral v2 DSL.

.. note::

   Action ``name`` and ``description`` are immutable. They are inferred from
   the action definition when the action is created.

List Actions
============

.. rest_method:: GET /v2/actions

Lists all actions.

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
  - name: action_filter_name
  - scope: action_filter_scope
  - tags: action_filter_tags
  - created_at: action_filter_created_at
  - updated_at: action_filter_updated_at
  - description: action_filter_description
  - definition: action_filter_definition
  - is_system: action_filter_is_system
  - input: action_filter_input
  - namespace: namespace

Response
--------

.. rest_parameters:: parameters.yaml

  - actions: actions
  - id: action_id
  - name: action_name
  - is_system: action_is_system
  - input: action_input
  - description: action_description
  - tags: action_tags
  - definition: action_definition
  - scope: action_scope
  - project_id: action_project_id
  - created_at: action_created_at
  - updated_at: action_updated_at
  - namespace: action_namespace

Create Action
=============

.. rest_method:: POST /v2/actions

Creates one or more actions from a YAML definition.

The request body should contain a YAML action definition conforming
to the Mistral v2 DSL. Multiple actions can be defined in a single
YAML definition.

Normal response codes: 201

Error response codes: badRequest(400), unauthorized(401), forbidden(403),
conflict(409)

Request
-------

.. rest_parameters:: parameters.yaml

  - namespace: namespace
  - scope: scope

The request body is a YAML action definition in ``text/plain`` format.

Response
--------

.. rest_parameters:: parameters.yaml

  - actions: actions
  - id: action_id
  - name: action_name
  - is_system: action_is_system
  - input: action_input
  - description: action_description
  - tags: action_tags
  - definition: action_definition
  - scope: action_scope
  - project_id: action_project_id
  - created_at: action_created_at
  - updated_at: action_updated_at
  - namespace: action_namespace

Show Action
===========

.. rest_method:: GET /v2/actions/{action_identifier}

Shows details for an action.

Normal response codes: 200

Error response codes: unauthorized(401), forbidden(403), itemNotFound(404)

Request
-------

.. rest_parameters:: parameters.yaml

  - action_identifier: action_identifier
  - namespace: namespace

Response
--------

.. rest_parameters:: parameters.yaml

  - id: action_id
  - name: action_name
  - is_system: action_is_system
  - input: action_input
  - description: action_description
  - tags: action_tags
  - definition: action_definition
  - scope: action_scope
  - project_id: action_project_id
  - created_at: action_created_at
  - updated_at: action_updated_at
  - namespace: action_namespace

Update Action
=============

.. rest_method:: PUT /v2/actions/{action_identifier}

Updates one or more actions.

The request body should contain a YAML action definition conforming
to the Mistral v2 DSL.

Normal response codes: 200

Error response codes: badRequest(400), unauthorized(401), forbidden(403),
itemNotFound(404)

Request
-------

.. rest_parameters:: parameters.yaml

  - action_identifier: action_identifier
  - namespace: namespace
  - scope: scope

The request body is a YAML action definition in ``text/plain`` format.

Response
--------

.. rest_parameters:: parameters.yaml

  - actions: actions
  - id: action_id
  - name: action_name
  - is_system: action_is_system
  - input: action_input
  - description: action_description
  - tags: action_tags
  - definition: action_definition
  - scope: action_scope
  - project_id: action_project_id
  - created_at: action_created_at
  - updated_at: action_updated_at
  - namespace: action_namespace

Delete Action
=============

.. rest_method:: DELETE /v2/actions/{action_identifier}

Deletes an action.

Normal response codes: 204

Error response codes: unauthorized(401), forbidden(403), itemNotFound(404)

Request
-------

.. rest_parameters:: parameters.yaml

  - action_identifier: action_identifier
  - namespace: namespace

Response
--------

There is no body content for the response of a successful DELETE action.
