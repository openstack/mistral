.. -*- rst -*-

========================
 Executions (executions)
========================

Manage workflow executions.

An execution represents one run of a workflow. When a workflow is executed,
Mistral creates an execution object that tracks the state, input, output,
and other runtime information about the running workflow.

List Executions
===============

.. rest_method:: GET /v2/executions

Lists all workflow executions.

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
  - workflow_name: execution_filter_workflow_name
  - workflow_id: execution_filter_workflow_id
  - description: execution_filter_description
  - tags: execution_filter_tags
  - params: execution_filter_params
  - task_execution_id: execution_filter_task_execution_id
  - root_execution_id: execution_filter_root_execution_id
  - state: execution_filter_state
  - state_info: execution_filter_state_info
  - input: execution_filter_input
  - output: execution_filter_output
  - created_at: execution_filter_created_at
  - updated_at: execution_filter_updated_at
  - include_output: execution_filter_include_output
  - project_id: execution_filter_project_id
  - all_projects: all_projects
  - nulls: execution_filter_nulls

Response
--------

.. rest_parameters:: parameters.yaml

  - executions: executions
  - id: execution_id_body
  - workflow_id: execution_workflow_id
  - workflow_name: execution_workflow_name
  - workflow_namespace: execution_workflow_namespace
  - description: execution_description
  - tags: execution_tags
  - params: execution_params
  - task_execution_id: execution_task_execution_id
  - root_execution_id: execution_root_execution_id
  - state: execution_state
  - state_info: execution_state_info
  - input: execution_input
  - output: execution_output
  - created_at: execution_created_at
  - updated_at: execution_updated_at
  - project_id: execution_project_id

Create Execution
================

.. rest_method:: POST /v2/executions

Creates and starts a new workflow execution.

Either ``workflow_id`` or ``workflow_name`` must be provided to identify
the workflow to execute. Alternatively, ``source_execution_id`` can be
used to replicate an existing execution.

Normal response codes: 201

Error response codes: badRequest(400), unauthorized(401), forbidden(403),
itemNotFound(404)

Request
-------

.. rest_parameters:: parameters.yaml

  - workflow_id: execution_workflow_id_create
  - workflow_name: execution_workflow_name_create
  - workflow_namespace: execution_workflow_namespace
  - description: execution_description
  - input: execution_input
  - params: execution_params
  - source_execution_id: execution_source_execution_id

Response
--------

.. rest_parameters:: parameters.yaml

  - id: execution_id_body
  - workflow_id: execution_workflow_id
  - workflow_name: execution_workflow_name
  - workflow_namespace: execution_workflow_namespace
  - description: execution_description
  - tags: execution_tags
  - params: execution_params
  - task_execution_id: execution_task_execution_id
  - root_execution_id: execution_root_execution_id
  - state: execution_state
  - state_info: execution_state_info
  - input: execution_input
  - output: execution_output
  - created_at: execution_created_at
  - updated_at: execution_updated_at
  - project_id: execution_project_id

Show Execution
==============

.. rest_method:: GET /v2/executions/{execution_id}

Shows details for an execution.

Normal response codes: 200

Error response codes: unauthorized(401), forbidden(403), itemNotFound(404)

Request
-------

.. rest_parameters:: parameters.yaml

  - execution_id: execution_id
  - fields: fields

Response
--------

.. rest_parameters:: parameters.yaml

  - id: execution_id_body
  - workflow_id: execution_workflow_id
  - workflow_name: execution_workflow_name
  - workflow_namespace: execution_workflow_namespace
  - description: execution_description
  - tags: execution_tags
  - params: execution_params
  - task_execution_id: execution_task_execution_id
  - root_execution_id: execution_root_execution_id
  - source_execution_id: execution_source_execution_id
  - state: execution_state
  - state_info: execution_state_info
  - input: execution_input
  - output: execution_output
  - created_at: execution_created_at
  - updated_at: execution_updated_at
  - project_id: execution_project_id
  - published_global: execution_published_global

Update Execution
================

.. rest_method:: PUT /v2/executions/{execution_id}

Updates an execution.

This can be used to pause, resume, or cancel an execution, update
its description, or modify its environment variables.

Normal response codes: 200

Error response codes: badRequest(400), unauthorized(401), forbidden(403),
itemNotFound(404)

Request
-------

.. rest_parameters:: parameters.yaml

  - execution_id: execution_id
  - state: execution_state_update
  - description: execution_description_update
  - params: execution_params_update

Response
--------

.. rest_parameters:: parameters.yaml

  - id: execution_id_body
  - workflow_id: execution_workflow_id
  - workflow_name: execution_workflow_name
  - workflow_namespace: execution_workflow_namespace
  - description: execution_description
  - tags: execution_tags
  - params: execution_params
  - task_execution_id: execution_task_execution_id
  - root_execution_id: execution_root_execution_id
  - state: execution_state
  - state_info: execution_state_info
  - input: execution_input
  - output: execution_output
  - created_at: execution_created_at
  - updated_at: execution_updated_at
  - project_id: execution_project_id

Delete Execution
================

.. rest_method:: DELETE /v2/executions/{execution_id}

Deletes an execution.

Normal response codes: 204

Error response codes: unauthorized(401), forbidden(403), itemNotFound(404)

Request
-------

.. rest_parameters:: parameters.yaml

  - execution_id: execution_id
  - force: execution_force_delete

Response
--------

There is no body content for the response of a successful DELETE action.

List Sub-Executions of a Workflow Execution
===========================================

.. rest_method:: GET /v2/executions/{execution_id}/executions

Lists all sub-executions of a workflow execution.

Sub-executions provide a way to navigate the execution tree of nested
workflows. This is useful for debugging and monitoring complex workflows
that invoke sub-workflows.

Normal response codes: 200

Error response codes: unauthorized(401), forbidden(403), itemNotFound(404)

Request
-------

.. rest_parameters:: parameters.yaml

  - execution_id: execution_id
  - errors_only: sub_execution_errors_only
  - max_depth: sub_execution_max_depth
  - include_output: sub_execution_include_output

Response
--------

.. rest_parameters:: parameters.yaml

  - executions: executions

Get Execution Report
====================

.. rest_method:: GET /v2/executions/{execution_id}/report

Generates a report for a workflow execution.

An execution report provides a detailed tree view of a workflow execution
including all nested task and action executions, along with statistics
such as counts of running, successful, errored, idle, and paused tasks.
The report can optionally include time estimates based on previous
executions of the same workflow.

Normal response codes: 200

Error response codes: unauthorized(401), forbidden(403), itemNotFound(404)

Request
-------

.. rest_parameters:: parameters.yaml

  - execution_id: execution_id
  - errors_only: execution_report_errors_only
  - max_depth: execution_report_max_depth
  - statistics_only: execution_report_statistics_only

Response
--------

.. rest_parameters:: parameters.yaml

  - statistics: execution_report_statistics
  - root_workflow_execution: execution_report_root_workflow_execution
