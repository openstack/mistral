.. -*- rst -*-

==============
 Tasks (tasks)
==============

Manage task executions.

A task represents a particular step of a workflow execution. It is created
by the Mistral engine when a workflow is running and tracks the state and
result of an individual unit of work within the workflow.

List Tasks
==========

.. rest_method:: GET /v2/tasks

Lists all task executions.

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
  - name: task_filter_name
  - workflow_name: task_filter_workflow_name
  - workflow_id: task_filter_workflow_id
  - workflow_execution_id: task_filter_workflow_execution_id
  - tags: task_filter_tags
  - state: task_filter_state
  - state_info: task_filter_state_info
  - result: task_filter_result
  - published: task_filter_published
  - processed: task_filter_processed
  - created_at: task_filter_created_at
  - updated_at: task_filter_updated_at
  - reset: task_filter_reset
  - env: task_filter_env

Response
--------

.. rest_parameters:: parameters.yaml

  - tasks: tasks
  - id: task_id_body
  - name: task_name
  - type: task_type
  - workflow_name: task_workflow_name
  - workflow_namespace: task_workflow_namespace
  - workflow_id: task_workflow_id
  - workflow_execution_id: task_workflow_execution_id
  - tags: task_tags
  - state: task_state
  - state_info: task_state_info
  - project_id: task_project_id
  - runtime_context: task_runtime_context
  - result: task_result
  - published: task_published
  - published_global: task_published_global
  - processed: task_processed
  - created_at: task_created_at
  - updated_at: task_updated_at
  - started_at: task_started_at
  - finished_at: task_finished_at

Show Task
=========

.. rest_method:: GET /v2/tasks/{task_id}

Shows details for a task execution.

Normal response codes: 200

Error response codes: unauthorized(401), forbidden(403), itemNotFound(404)

Request
-------

.. rest_parameters:: parameters.yaml

  - task_id: task_id
  - fields: fields

Response
--------

.. rest_parameters:: parameters.yaml

  - id: task_id_body
  - name: task_name
  - type: task_type
  - workflow_name: task_workflow_name
  - workflow_namespace: task_workflow_namespace
  - workflow_id: task_workflow_id
  - workflow_execution_id: task_workflow_execution_id
  - tags: task_tags
  - state: task_state
  - state_info: task_state_info
  - project_id: task_project_id
  - runtime_context: task_runtime_context
  - result: task_result
  - published: task_published
  - published_global: task_published_global
  - processed: task_processed
  - created_at: task_created_at
  - updated_at: task_updated_at
  - started_at: task_started_at
  - finished_at: task_finished_at

Rerun Task
==========

.. rest_method:: PUT /v2/tasks/{task_id}

Reruns or skips a task execution.

This operation can be used to rerun a failed task or to skip a task
that is in ``ERROR`` state. To rerun a task, set ``state`` to ``RUNNING``
and ``reset`` to ``true``. To skip a task, set ``state`` to ``SKIPPED``.

Normal response codes: 200

Error response codes: badRequest(400), unauthorized(401), forbidden(403),
itemNotFound(404)

Request
-------

.. rest_parameters:: parameters.yaml

  - task_id: task_id
  - state: task_state_update
  - reset: task_reset
  - env: task_env

Response
--------

.. rest_parameters:: parameters.yaml

  - id: task_id_body
  - name: task_name
  - type: task_type
  - workflow_name: task_workflow_name
  - workflow_namespace: task_workflow_namespace
  - workflow_id: task_workflow_id
  - workflow_execution_id: task_workflow_execution_id
  - tags: task_tags
  - state: task_state
  - state_info: task_state_info
  - project_id: task_project_id
  - runtime_context: task_runtime_context
  - result: task_result
  - published: task_published
  - published_global: task_published_global
  - processed: task_processed
  - created_at: task_created_at
  - updated_at: task_updated_at
  - started_at: task_started_at
  - finished_at: task_finished_at
