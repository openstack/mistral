.. -*- rst -*-

================================
 Cron Triggers (cron_triggers)
================================

Manage cron triggers.

A cron trigger is a scheduling mechanism that automatically starts
a workflow execution based on a cron expression pattern. Cron triggers
can be configured with a maximum number of remaining executions, after
which the trigger is automatically removed.

List Cron Triggers
==================

.. rest_method:: GET /v2/cron_triggers

Lists all cron triggers.

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
  - name: cron_trigger_filter_name
  - workflow_name: cron_trigger_filter_workflow_name
  - workflow_id: cron_trigger_filter_workflow_id
  - workflow_input: cron_trigger_filter_workflow_input
  - workflow_params: cron_trigger_filter_workflow_params
  - scope: cron_trigger_filter_scope
  - pattern: cron_trigger_filter_pattern
  - remaining_executions: cron_trigger_filter_remaining_executions
  - first_execution_time: cron_trigger_filter_first_execution_time
  - next_execution_time: cron_trigger_filter_next_execution_time
  - created_at: cron_trigger_filter_created_at
  - updated_at: cron_trigger_filter_updated_at
  - project_id: cron_trigger_filter_project_id
  - all_projects: all_projects

Response
--------

.. rest_parameters:: parameters.yaml

  - cron_triggers: cron_triggers
  - id: cron_trigger_id
  - name: cron_trigger_name
  - workflow_name: cron_trigger_workflow_name
  - workflow_id: cron_trigger_workflow_id
  - workflow_input: cron_trigger_workflow_input
  - workflow_params: cron_trigger_workflow_params
  - project_id: cron_trigger_project_id
  - scope: cron_trigger_scope
  - pattern: cron_trigger_pattern
  - remaining_executions: cron_trigger_remaining_executions
  - first_execution_time: cron_trigger_first_execution_time
  - next_execution_time: cron_trigger_next_execution_time
  - created_at: cron_trigger_created_at
  - updated_at: cron_trigger_updated_at

Create Cron Trigger
===================

.. rest_method:: POST /v2/cron_triggers

Creates a cron trigger.

Either ``workflow_name`` or ``workflow_id`` must be provided to identify
the workflow to trigger. At least one of ``pattern`` or
``first_execution_time`` must be specified.

Normal response codes: 201

Error response codes: badRequest(400), unauthorized(401), forbidden(403),
conflict(409)

Request
-------

.. rest_parameters:: parameters.yaml

  - name: cron_trigger_name_create
  - workflow_name: cron_trigger_workflow_name_create
  - workflow_id: cron_trigger_workflow_id_create
  - workflow_input: cron_trigger_workflow_input
  - workflow_params: cron_trigger_workflow_params
  - pattern: cron_trigger_pattern
  - first_execution_time: cron_trigger_first_execution_time
  - remaining_executions: cron_trigger_remaining_executions

Response
--------

.. rest_parameters:: parameters.yaml

  - id: cron_trigger_id
  - name: cron_trigger_name
  - workflow_name: cron_trigger_workflow_name
  - workflow_id: cron_trigger_workflow_id
  - workflow_input: cron_trigger_workflow_input
  - workflow_params: cron_trigger_workflow_params
  - project_id: cron_trigger_project_id
  - scope: cron_trigger_scope
  - pattern: cron_trigger_pattern
  - remaining_executions: cron_trigger_remaining_executions
  - first_execution_time: cron_trigger_first_execution_time
  - next_execution_time: cron_trigger_next_execution_time
  - created_at: cron_trigger_created_at
  - updated_at: cron_trigger_updated_at

Show Cron Trigger
=================

.. rest_method:: GET /v2/cron_triggers/{cron_trigger_identifier}

Shows details for a cron trigger.

Normal response codes: 200

Error response codes: unauthorized(401), forbidden(403), itemNotFound(404)

Request
-------

.. rest_parameters:: parameters.yaml

  - cron_trigger_identifier: cron_trigger_identifier
  - fields: fields

Response
--------

.. rest_parameters:: parameters.yaml

  - id: cron_trigger_id
  - name: cron_trigger_name
  - workflow_name: cron_trigger_workflow_name
  - workflow_id: cron_trigger_workflow_id
  - workflow_input: cron_trigger_workflow_input
  - workflow_params: cron_trigger_workflow_params
  - project_id: cron_trigger_project_id
  - scope: cron_trigger_scope
  - pattern: cron_trigger_pattern
  - remaining_executions: cron_trigger_remaining_executions
  - first_execution_time: cron_trigger_first_execution_time
  - next_execution_time: cron_trigger_next_execution_time
  - created_at: cron_trigger_created_at
  - updated_at: cron_trigger_updated_at

Delete Cron Trigger
===================

.. rest_method:: DELETE /v2/cron_triggers/{cron_trigger_identifier}

Deletes a cron trigger.

Normal response codes: 204

Error response codes: unauthorized(401), forbidden(403), itemNotFound(404)

Request
-------

.. rest_parameters:: parameters.yaml

  - cron_trigger_identifier: cron_trigger_identifier

Response
--------

There is no body content for the response of a successful DELETE action.
