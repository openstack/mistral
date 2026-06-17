.. -*- rst -*-

================================
 Event Triggers (event_triggers)
================================

Manage event triggers.

An event trigger is a mechanism that starts a workflow execution in response
to an external event received via a messaging system. Event triggers listen
on a specific exchange, topic, and event type.

List Event Triggers
===================

.. rest_method:: GET /v2/event_triggers

Lists all event triggers.

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
  - name: event_trigger_filter_name
  - exchange: event_trigger_filter_exchange
  - topic: event_trigger_filter_topic
  - event: event_trigger_filter_event
  - workflow_id: event_trigger_filter_workflow_id
  - scope: event_trigger_filter_scope
  - project_id: event_trigger_filter_project_id
  - created_at: event_trigger_filter_created_at
  - updated_at: event_trigger_filter_updated_at
  - all_projects: all_projects

Response
--------

.. rest_parameters:: parameters.yaml

  - event_triggers: event_triggers
  - id: event_trigger_id
  - name: event_trigger_name
  - workflow_id: event_trigger_workflow_id
  - workflow_input: event_trigger_workflow_input
  - workflow_params: event_trigger_workflow_params
  - exchange: event_trigger_exchange
  - topic: event_trigger_topic
  - event: event_trigger_event
  - scope: event_trigger_scope
  - project_id: event_trigger_project_id
  - created_at: event_trigger_created_at
  - updated_at: event_trigger_updated_at

Create Event Trigger
====================

.. rest_method:: POST /v2/event_triggers

Creates an event trigger.

The ``workflow_id``, ``exchange``, ``topic``, and ``event`` fields are
required. The ``name`` field is optional and defaults to an empty string.

Normal response codes: 201

Error response codes: badRequest(400), unauthorized(401), forbidden(403),
conflict(409)

Request
-------

.. rest_parameters:: parameters.yaml

  - name: event_trigger_name_create
  - workflow_id: event_trigger_workflow_id_create
  - workflow_input: event_trigger_workflow_input
  - workflow_params: event_trigger_workflow_params
  - exchange: event_trigger_exchange_create
  - topic: event_trigger_topic_create
  - event: event_trigger_event_create
  - scope: scope

Response
--------

.. rest_parameters:: parameters.yaml

  - id: event_trigger_id
  - name: event_trigger_name
  - workflow_id: event_trigger_workflow_id
  - workflow_input: event_trigger_workflow_input
  - workflow_params: event_trigger_workflow_params
  - exchange: event_trigger_exchange
  - topic: event_trigger_topic
  - event: event_trigger_event
  - scope: event_trigger_scope
  - project_id: event_trigger_project_id
  - created_at: event_trigger_created_at
  - updated_at: event_trigger_updated_at

Show Event Trigger
==================

.. rest_method:: GET /v2/event_triggers/{event_trigger_id}

Shows details for an event trigger.

Normal response codes: 200

Error response codes: unauthorized(401), forbidden(403), itemNotFound(404)

Request
-------

.. rest_parameters:: parameters.yaml

  - event_trigger_id: event_trigger_id_path
  - fields: fields

Response
--------

.. rest_parameters:: parameters.yaml

  - id: event_trigger_id
  - name: event_trigger_name
  - workflow_id: event_trigger_workflow_id
  - workflow_input: event_trigger_workflow_input
  - workflow_params: event_trigger_workflow_params
  - exchange: event_trigger_exchange
  - topic: event_trigger_topic
  - event: event_trigger_event
  - scope: event_trigger_scope
  - project_id: event_trigger_project_id
  - created_at: event_trigger_created_at
  - updated_at: event_trigger_updated_at

Update Event Trigger
====================

.. rest_method:: PUT /v2/event_triggers/{event_trigger_id}

Updates an event trigger.

The ``exchange``, ``topic``, and ``event`` fields cannot be updated.
To change them, delete the event trigger and create a new one.

Normal response codes: 200

Error response codes: badRequest(400), unauthorized(401), forbidden(403),
itemNotFound(404)

Request
-------

.. rest_parameters:: parameters.yaml

  - event_trigger_id: event_trigger_id_path
  - name: event_trigger_name
  - workflow_id: event_trigger_workflow_id
  - workflow_input: event_trigger_workflow_input
  - workflow_params: event_trigger_workflow_params
  - scope: scope

Response
--------

.. rest_parameters:: parameters.yaml

  - id: event_trigger_id
  - name: event_trigger_name
  - workflow_id: event_trigger_workflow_id
  - workflow_input: event_trigger_workflow_input
  - workflow_params: event_trigger_workflow_params
  - exchange: event_trigger_exchange
  - topic: event_trigger_topic
  - event: event_trigger_event
  - scope: event_trigger_scope
  - project_id: event_trigger_project_id
  - created_at: event_trigger_created_at
  - updated_at: event_trigger_updated_at

Delete Event Trigger
====================

.. rest_method:: DELETE /v2/event_triggers/{event_trigger_id}

Deletes an event trigger.

Normal response codes: 204

Error response codes: unauthorized(401), forbidden(403), itemNotFound(404)

Request
-------

.. rest_parameters:: parameters.yaml

  - event_trigger_id: event_trigger_id_path

Response
--------

There is no body content for the response of a successful DELETE action.
