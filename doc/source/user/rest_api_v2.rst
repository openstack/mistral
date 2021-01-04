REST API V2
===========

This API describes the ways of interacting with Mistral service via
HTTP protocol using Representational State Transfer concept (ReST).

Basics
-------

Media types
^^^^^^^^^^^

Currently this API relies on JSON to represent states of REST resources.

Error states
^^^^^^^^^^^^

The common HTTP Response Status Codes
(https://github.com/for-GET/know-your-http-well/blob/master/status-codes.md)
are used.

Application root [/]
^^^^^^^^^^^^^^^^^^^^
Application Root provides links to all possible API methods for Mistral. URLs
for other resources described below are relative to Application Root.

API v2 root [/v2/]
^^^^^^^^^^^^^^^^^^
All API v2 URLs are relative to API v2 root.

Workbooks
---------

.. autotype:: mistral.api.controllers.v2.resources.Workbook
   :members:

`name` is immutable. tags is a list of values associated with a workbook that
a user can use to group workbooks by some criteria (deployment workbooks,
Big Data processing workbooks etc.). Note that name and tags get inferred from
workbook definition when Mistral service receives a POST request. So they
can't be changed in another way.

.. autotype:: mistral.api.controllers.v2.resources.Workbooks
   :members:

.. rest-controller:: mistral.api.controllers.v2.workbook:WorkbooksController
   :webprefix: /v2/workbooks


Workflows
---------

.. autotype:: mistral.api.controllers.v2.resources.Workflow
   :members:

`name` is immutable. tags is a list of values associated with a workflow that
a user can use to group workflows by some criteria. Note that name and tags get
inferred from workflow definition when Mistral service receives a POST request.
So they can't be changed in another way.

.. autotype:: mistral.api.controllers.v2.resources.Workflows
   :members:

.. rest-controller:: mistral.api.controllers.v2.workflow:WorkflowsController
   :webprefix: /v2/workflows

Actions
-------

.. autotype:: mistral.api.controllers.v2.resources.Action
   :members:

.. autotype:: mistral.api.controllers.v2.resources.Actions
   :members:

.. rest-controller:: mistral.api.controllers.v2.action:ActionsController
   :webprefix: /v2/actions


Executions
----------

.. autotype:: mistral.api.controllers.v2.resources.Execution
   :members:

.. autotype:: mistral.api.controllers.v2.resources.Executions
   :members:

.. rest-controller:: mistral.api.controllers.v2.execution:ExecutionsController
    :webprefix: /v2/executions


Tasks
-----

When a workflow starts Mistral creates an execution. It in turn consists of a
set of tasks. So Task is an instance of a task described in a Workflow that
belongs to a particular execution.


.. autotype:: mistral.api.controllers.v2.resources.Task
   :members:

.. autotype:: mistral.api.controllers.v2.resources.Tasks
   :members:

.. rest-controller:: mistral.api.controllers.v2.task:TasksController
    :webprefix: /v2/tasks

.. rest-controller:: mistral.api.controllers.v2.task:ExecutionTasksController
    :webprefix: /v2/executions


Action Executions
-----------------

When a Task starts Mistral creates a set of Action Executions. So Action
Execution is an instance of an action call described in a Workflow Task that
belongs to a particular execution.


.. autotype:: mistral.api.controllers.v2.resources.ActionExecution
   :members:

.. autotype:: mistral.api.controllers.v2.resources.ActionExecutions
   :members:

.. rest-controller:: mistral.api.controllers.v2.action_execution:ActionExecutionsController
    :webprefix: /v2/action_executions

.. rest-controller:: mistral.api.controllers.v2.action_execution:TasksActionExecutionController
    :webprefix: /v2/tasks

Cron Triggers
-------------

Cron trigger is an object that allows to run Mistral workflows according to
a time pattern (Unix crontab patterns format). Once a trigger is created it
will run a specified workflow according to its properties: pattern,
first_execution_time and remaining_executions.


.. autotype:: mistral.api.controllers.v2.resources.CronTrigger
   :members:

.. autotype:: mistral.api.controllers.v2.resources.CronTriggers
   :members:

.. rest-controller:: mistral.api.controllers.v2.cron_trigger:CronTriggersController
    :webprefix: /v2/cron_triggers


Environments
------------

Environment contains a set of variables which can be used in specific workflow.
Using an Environment it is possible to create and map action default values -
just provide '__actions' key in 'variables'. All these variables can be
accessed using the Workflow Language with the ``<% $.__env %>`` expression.

Example of usage:

.. code-block:: yaml

  workflow:
    tasks:
      task1:
        action: std.echo output=<% $.__env.my_echo_output %>

Example of creating action defaults

::

  ...ENV...
  "variables": {
    "__actions": {
      "std.echo": {
        "output": "my_output"
      }
    }
  },
  ...ENV...

Note: using CLI, Environment can be created via JSON or YAML file.

.. autotype:: mistral.api.controllers.v2.resources.Environment
   :members:

.. autotype:: mistral.api.controllers.v2.resources.Environments
   :members:

.. rest-controller:: mistral.api.controllers.v2.environment:EnvironmentController
   :webprefix: /v2/environments


Services
--------

Through service management API, system administrator or operator can retrieve
Mistral services information of the system, including service group and service
identifier. The internal implementation of this feature make use of tooz
library, which needs coordinator backend(the most commonly used at present is
Zookeeper) installed, please refer to tooz official documentation for more
detailed instruction.

There are three service groups according to Mistral architecture currently,
namely api_group, engine_group and executor_group. The service identifier
contains name of the host that the service is running on and the process
identifier of the service on that host.

.. autotype:: mistral.api.controllers.v2.resources.Service
   :members:

.. autotype:: mistral.api.controllers.v2.resources.Services
   :members:

.. rest-controller:: mistral.api.controllers.v2.service:ServicesController
   :webprefix: /v2/services

Validation
----------

Validation endpoints allow to check correctness of workbook, workflow and
ad-hoc action Workflow Language without having to upload them into Mistral.

**POST /v2/workbooks/validation**
  Validate workbook content (Workflow Language grammar and semantics).

**POST /v2/workflows/validation**
  Validate workflow content (Workflow Language grammar and semantics).

**POST /v2/actions/validation**
  Validate ad-hoc action content (Workflow Language grammar and semantics).

These endpoints expect workbook, workflow or ad-hoc action text
(Workflow Language) correspondingly in a request body.


Code Sources
------------

Code source is a type of entity that holds information about an executable
module. Mostly, it was designed to represent as a Python module and this is
its main use at the moment. However, it can also be used for other languages
in future.

Code sources are now used as part of the dynamic actions mechanism. The normal
flow is to first upload a code source, i.e. a regular Python file, and then
create one or more dynamic actions using **POST /v2/dynamic-actions** and
specifying the name of the action, its class name as it's declared in the
source code, and the reference to the source code itself.

.. autotype:: mistral.api.controllers.v2.resources.CodeSource
   :members:

.. autotype:: mistral.api.controllers.v2.resources.CodeSources
   :members:

.. rest-controller:: mistral.api.controllers.v2.code_source:CodeSourcesController
   :webprefix: /v2/code-sources


Dynamic Actions
---------------

Dynamic action is the type of action that can be created right through the API,
without having to reboot Mistral like in other cases.

Before adding a dynamic action, a client first needs to upload a code source
(i.e. a Python module) that contains the corresponding Python class that
implements the action, and then create the action using the method
**POST /v2/dynamic-actions** where the name of the action, its class name as
it's declared in the code source code, and the reference to the source code
itself must be specified.

.. autotype:: mistral.api.controllers.v2.resources.DynamicAction
   :members:

.. autotype:: mistral.api.controllers.v2.resources.DynamicActions
   :members:

.. rest-controller:: mistral.api.controllers.v2.dynamic_action:DynamicActionsController
   :webprefix: /v2/dynamic-actions
