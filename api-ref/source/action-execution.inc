.. -*- rst -*-

========================================
 Action Executions (action_executions)
========================================

Manage action executions.

An action execution represents a single invocation of an action. Action
executions are typically created automatically as part of a workflow task,
but can also be created directly via the API to run an action outside of
a workflow context.

List Action Executions
======================

.. rest_method:: GET /v2/action_executions

Lists all action executions.

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
  - name: action_execution_filter_name
  - workflow_name: action_execution_filter_workflow_name
  - task_name: action_execution_filter_task_name
  - task_execution_id: action_execution_filter_task_execution_id
  - state: action_execution_filter_state
  - state_info: action_execution_filter_state_info
  - accepted: action_execution_filter_accepted
  - description: action_execution_filter_description
  - tags: action_execution_filter_tags
  - created_at: action_execution_filter_created_at
  - updated_at: action_execution_filter_updated_at
  - include_output: action_execution_include_output

Response
--------

.. rest_parameters:: parameters.yaml

  - action_executions: action_executions
  - id: action_execution_id
  - name: action_execution_name
  - workflow_name: action_execution_workflow_name
  - workflow_namespace: action_execution_workflow_namespace
  - task_name: action_execution_task_name
  - task_execution_id: action_execution_task_execution_id
  - state: action_execution_state
  - state_info: action_execution_state_info
  - tags: action_execution_tags
  - description: action_execution_description
  - project_id: action_execution_project_id
  - accepted: action_execution_accepted
  - input: action_execution_input
  - output: action_execution_output
  - created_at: action_execution_created_at
  - updated_at: action_execution_updated_at

Create Action Execution
=======================

.. rest_method:: POST /v2/action_executions

Creates an action execution.

Runs an action directly outside of a workflow context. At minimum, the
``name`` field must be provided.

Normal response codes: 201

Error response codes: badRequest(400), unauthorized(401), forbidden(403)

Request
-------

.. rest_parameters:: parameters.yaml

  - name: action_execution_name_create
  - description: action_execution_description_create
  - input: action_execution_input_create
  - params: action_execution_params_create
  - workflow_namespace: action_execution_workflow_namespace

Response
--------

.. rest_parameters:: parameters.yaml

  - id: action_execution_id
  - name: action_execution_name
  - workflow_name: action_execution_workflow_name
  - workflow_namespace: action_execution_workflow_namespace
  - task_name: action_execution_task_name
  - task_execution_id: action_execution_task_execution_id
  - state: action_execution_state
  - state_info: action_execution_state_info
  - tags: action_execution_tags
  - description: action_execution_description
  - project_id: action_execution_project_id
  - accepted: action_execution_accepted
  - input: action_execution_input
  - output: action_execution_output
  - created_at: action_execution_created_at
  - updated_at: action_execution_updated_at

Show Action Execution
=====================

.. rest_method:: GET /v2/action_executions/{action_execution_id}

Shows details for an action execution.

Normal response codes: 200

Error response codes: unauthorized(401), forbidden(403), itemNotFound(404)

Request
-------

.. rest_parameters:: parameters.yaml

  - action_execution_id: action_execution_id_path
  - fields: fields

Response
--------

.. rest_parameters:: parameters.yaml

  - id: action_execution_id
  - name: action_execution_name
  - workflow_name: action_execution_workflow_name
  - workflow_namespace: action_execution_workflow_namespace
  - task_name: action_execution_task_name
  - task_execution_id: action_execution_task_execution_id
  - state: action_execution_state
  - state_info: action_execution_state_info
  - tags: action_execution_tags
  - description: action_execution_description
  - project_id: action_execution_project_id
  - accepted: action_execution_accepted
  - input: action_execution_input
  - output: action_execution_output
  - created_at: action_execution_created_at
  - updated_at: action_execution_updated_at

Update Action Execution
=======================

.. rest_method:: PUT /v2/action_executions/{action_execution_id}

Updates an action execution.

Used to report the result of an action back to Mistral. The ``state``
field must be one of ``SUCCESS``, ``ERROR``, ``CANCELLED``, ``PAUSED``,
or ``RUNNING``.

Normal response codes: 200

Error response codes: badRequest(400), unauthorized(401), forbidden(403),
itemNotFound(404)

Request
-------

.. rest_parameters:: parameters.yaml

  - action_execution_id: action_execution_id_path
  - state: action_execution_state_update
  - output: action_execution_output_update

Response
--------

.. rest_parameters:: parameters.yaml

  - id: action_execution_id
  - name: action_execution_name
  - workflow_name: action_execution_workflow_name
  - workflow_namespace: action_execution_workflow_namespace
  - task_name: action_execution_task_name
  - task_execution_id: action_execution_task_execution_id
  - state: action_execution_state
  - state_info: action_execution_state_info
  - tags: action_execution_tags
  - description: action_execution_description
  - project_id: action_execution_project_id
  - accepted: action_execution_accepted
  - input: action_execution_input
  - output: action_execution_output
  - created_at: action_execution_created_at
  - updated_at: action_execution_updated_at

Delete Action Execution
=======================

.. rest_method:: DELETE /v2/action_executions/{action_execution_id}

Deletes an action execution.

Normal response codes: 204

Error response codes: unauthorized(401), forbidden(403), itemNotFound(404)

Request
-------

.. rest_parameters:: parameters.yaml

  - action_execution_id: action_execution_id_path

Response
--------

There is no body content for the response of a successful DELETE action.
