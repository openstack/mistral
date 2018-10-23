=================================
Workflow service overview
=================================

Mistral is a workflow service that enables setting up and scheduling tasks and
task relations that have to be executed in a particular order, called workflows.
During execution, Mistral handles state management, correct execution order,
parallelism, synchronization and high availability.

Mistral can be used, for example, for Cloud Cron-style task scheduling,
Cloud Environment Deployment, handling long-running business processes, managing
BigData analysis and tasks, and live migration.

The Workflow service consists of the following components:

``Mistral API`` service
  Provides a REST API for operating and monitoring workflow executions.

``mistral-dashboard`` service
  Mistral Dashboard is a Horizon plugin.

``Mistral Engine`` service
  Controls workflow executions and handles their data flow, places finished
  tasks in a queue, transfers data from task to task, and deals with condition
  transitions, and so on.

``Mistral Executor`` service
  Executes task actions, picks up the tasks from the queue, runs actions, and
  sends results back to the engine.

``Mistral Notifier`` service

``python-mistralclient``
  Python client API and Command Line Interface.

  ``mistral-lib``
  A library to support writing custom Mistral actions.
