Executions
==========

Executions are runtime objects and they reflect the information about the progress and state of concrete execution type. All executions are persisted in DB.

Workflow Execution
------------------

A particular execution of specific workflow. When user submits a workflow to run, Mistral creates an object in database for execution of this workflow. It contains all information about workflow itself, about execution progress, state, input and output data. Workflow execution contains at least one *task execution*.

A workflow execution can be in one of a number of predefined states reflecting its current status:

* **RUNNING** - workflow is currently being executed.
* **PAUSED** - workflow is paused.
* **SUCCESS** - workflow has finished successfully.
* **ERROR** - workflow has finished with an error.

Task Execution
--------------

Defines a workflow execution step. It has a state and result.

**Task state**

A task can be in one of a number of predefined states reflecting its current status:

* **IDLE** - task is not started yet; probably not all requirements are satisfied.
* **WAITING** - task execution object has been created but it is not ready to start because some preconditions are not met. **NOTE:** The task may never run just because some of the preconditions may never be met.
* **RUNNING_DELAYED** - task was in the running state before and the task execution has been delayed on precise amount of time.
* **RUNNING** - task is currently being executed.
* **SUCCESS** - task has finished successfully.
* **ERROR** - task has finished with an error.

All the actual task states belonging to current execution are persisted in DB.

Task result is an aggregation of all *action executions* belonging to current *task execution*. Usually one *task execution* has at least one *action execution*. But in case of task is executing nested workflow, this *task execution* won't have *action executions*. Instead, there will be at least one *workflow execution*.

Action Execution
----------------

Execution of specific action. To see details about actions, please refer to :ref:`actions-dsl`

Action execution has a state, input and output data.

Usually action execution belongs to task execution but Mistral also is able to run separate action executions.
