Mistral Client Commands Guide
=============================

Workbooks
^^^^^^^^^

**workbook-create**:
::

    mistral workbook-create <definition>

Create new workbook.

positional arguments:
  definition - Workbook definition file.

**workbook-delete**:
::

    mistral workbook-delete <name> [<name> ...]

Delete workbook.

positional arguments:
  name - Name of workbook(s).

**workbook-get**:
::

    mistral workbook-get <name>

Show specific workbook.

positional arguments:
  name - Workbook name.

**workbook-get-definition**:
::

    mistral workbook-get-definition <workbook_identifier>

Show workbook definition.

positional arguments:
  workbook_identifier - Workbook name or ID.

**workbook-list**:
::

    mistral workbook-list

List all workbooks.

**workbook-update**:
::

    mistral workbook-update <definition>

Update workbook.

positional arguments:
  definition - Workbook definition file.

**workbook-validate**:
::

    mistral workbook-validate <definition>

Validate workbook.

positional arguments:
  definition - Workbook definition file.

Workflows
^^^^^^^^^

**workflow-create**:
::

    mistral workflow-create <definition> [--public]

Create new workflow.

positional arguments:
  definition - Workflow definition file.

optional arguments:
  --public - With this flag workflow will be marked as "public".

**workflow-delete**:
::

    mistral workflow-delete <name> [<name> ...]

Delete workflow.

positional arguments:
  name - Name of workflow(s).

**workflow-get**:
::

    mistral workflow-get <name>

Show specific workflow.

positional arguments:
  name - Workflow name.

**workflow-get-definition**:
::

    mistral workflow-get-definition <name>

Show workflow definition.

positional arguments:
  name - Workflow name.

**workflow-list**:
::

    mistral workflow-list

List all workflows.

**workflow-update**:
::

    mistral workflow-update <definition>

Update workflow.

positional arguments:
  definition - Workflow definition.

**workflow-validate**:
::

    mistral workflow-validate <definition>

Validate workflow.

positional arguments:
  definition - Workflow definition file.

Actions
^^^^^^^

**action-create**:
::

    mistral action-create <definition> [--public]

Create new action.

positional arguments:
  definition - Action definition file.

optional arguments:
  --public - With this flag action will be marked as "public".

**action-delete**:
::

    mistral action-delete action [action ...]

Delete action.

positional arguments:
  action - Name or ID of action(s).

**action-get**:
::

    mistral action-get <action>

Show specific action.

positional arguments:
  action - Action (name or ID).

**action-get-definition**:
::

    mistral action-get-definition <name>

Show action definition.

positional arguments:
  name - Action name.

**action-list**:
::

    mistral action-list

List all actions.

**action-update**:
::

    mistral action-update [--public] [--id ID] <definition>

Update action.

positional arguments:
  definition - Action definition file.

optional arguments:
  --id ID               Action ID.
  --public              With this flag, action will be marked as "public".

**action-validate**:
::

    mistral action-validate <definition>

Validate action.

positional arguments:
  definition - Action definition file.

Workflow executions
^^^^^^^^^^^^^^^^^^^

**execution-create**:
::

    mistral execution-create [-d DESCRIPTION]
                                    <workflow_identifier> [<workflow_input>] [<params>]

Create a new execution.

positional arguments:
  workflow_identifier - Workflow ID or name. Workflow name has been deprecated
                        since Mitaka.
  workflow_input - Workflow input.
  params - Workflow additional parameters.

optional arguments:
  -d DESCRIPTION, --description DESCRIPTION
                        Execution description

**execution-delete**:
::

    mistral execution-delete <execution> [<execution> ...]

Delete execution.

positional arguments:
  execution - Id of execution identifier(s).

**execution-get**:
::

    mistral execution-get <execution>

Show specific execution.

positional arguments:
  execution - Execution identifier.

**execution-get-input**:
::

    mistral execution-get-input <id>

Show execution input data.

positional arguments:
  id - Execution ID.

**execution-get-output**:
::

    mistral execution-get-output [-h] id

Show execution output data.

positional arguments:
  id - Execution ID.

**execution-list**:
::

    mistral execution-list [--marker [MARKER]] [--limit [LIMIT]]
                                  [--sort_keys [SORT_KEYS]]
                                  [--sort_dirs [SORT_DIRS]]

List all executions.

optional arguments:
  --marker [MARKER]     The last execution uuid of the previous page, displays
                        list of executions after "marker".
  --limit [LIMIT]       Maximum number of executions to return in a single
                        result.
  --sort_keys [SORT_KEYS]
                        Comma-separated list of sort keys to sort results by.
                        Default: created_at. Example: mistral execution-list
                        --sort_keys=id,description
  --sort_dirs [SORT_DIRS]
                        Comma-separated list of sort directions. Default: asc.
                        Example: mistral execution-list
                        --sort_keys=id,description --sort_dirs=asc,desc

**execution-update**:
::

    mistral execution-update [-s {RUNNING,PAUSED,SUCCESS,ERROR,CANCELLED}]
                                    [-e ENV] [-d DESCRIPTION] <id>

Update execution.

positional arguments:
  id - Execution identifier.

optional arguments:
  -s {RUNNING,PAUSED,SUCCESS,ERROR,CANCELLED}, --state {RUNNING,PAUSED,SUCCESS,ERROR,CANCELLED}
                        Execution state
  -e ENV, --env ENV     Environment variables
  -d DESCRIPTION, --description DESCRIPTION
                        Execution description

Task executions
^^^^^^^^^^^^^^^

**task-get**:
::

    mistral task-get <id>

Show specific task.

positional arguments:
  id - Task identifier.

**task-get-published**:
::

    mistral task-get-published <id>

Show task published variables.

positional arguments:
  id - Task ID.

**task-get-result**:
::

    mistral task-get-result <id>

Show task output data.

positional arguments:
  id - Task ID.

**task-list**:
::

    mistral task-list [<workflow_execution>]

List all tasks.

positional arguments:
  workflow_execution - Workflow execution ID associated with list of Tasks.

**task-rerun**:
::

    mistral task-rerun [--resume] [-e ENV] <id>

Rerun an existing task.

positional arguments:
  id - Task identifier.

optional arguments:
  --resume              rerun only failed or unstarted action executions for
                        with-items task.
  -e ENV, --env ENV     Environment variables.

Action executions
^^^^^^^^^^^^^^^^^

**action-execution-delete**:
::

    mistral action-execution-delete <action_execution> [<action_execution> ...]

Delete action execution.

positional arguments:
  action_execution - Action execution ID.

**action-execution-get**:
::

    mistral action-execution-get <action_execution>

Show specific Action execution.

positional arguments:
  action_execution - Action execution ID.

**action-execution-get-input**:
::

    mistral action-execution-get-input <id>

Show Action execution input data.

positional arguments:
  id - Action execution ID.

**action-execution-get-output**:
::

    mistral action-execution-get-output <id>

Show Action execution output data.

positional arguments:
  id - Action execution ID.

**action-execution-list**:
::

    mistral action-execution-list [<task-execution-id>]

List all Action executions.

positional arguments:
  task-execution-id - Task execution ID.

**action-execution-update**:
::

    mistral action-execution-update [--state {IDLE,RUNNING,SUCCESS,ERROR}] [--output <OUTPUT>] <id>

Update specific Action execution.

positional arguments:
  id - Action execution ID.

optional arguments:
  --state {IDLE,RUNNING,SUCCESS,ERROR}
                        Action execution state
  --output OUTPUT - Action execution output

**run-action**:
::

    mistral run-action <name> [<input>] [-t <TARGET>]

Create new Action execution or just run specific action.

positional arguments:
  name - Action name to execute.
  input - Action input.

optional arguments:
  -s, --save-result - Save the result into DB.
  -t TARGET, --target TARGET
                        Action will be executed on <target> executor.

Cron-triggers
^^^^^^^^^^^^^

**cron-trigger-create**:
::

    mistral cron-trigger-create [--params <PARAMS>] [--pattern <* * * * *>]
                                       [--first-time <YYYY-MM-DD HH:MM>]
                                       [--count <integer>]
                                       <name> <workflow_identifier> [<workflow_input>]

Create new trigger.

positional arguments:
  name - Cron trigger name.
  workflow_identifier - Workflow name or ID.
  workflow_input - Workflow input.

optional arguments:
  --params PARAMS - Workflow params.
  --pattern <* * * * *>
                        Cron trigger pattern.
  --first-time <YYYY-MM-DD HH:MM>
                        Date and time of the first execution.
  --count <integer>     Number of wanted executions.

**cron-trigger-delete**:
::

    mistral cron-trigger-delete <name> [<name> ...]

Delete trigger.

positional arguments:
  name - Name of cron trigger(s).

**cron-trigger-get**:
::

    mistral cron-trigger-get <name>

Show specific cron trigger.

positional arguments:
  name - Cron trigger name.

**cron-trigger-list**:
::

    mistral cron-trigger-list

List all cron triggers.

Environments
^^^^^^^^^^^^

**environment-create**:
::

    mistral environment-create <file>

Create new environment.

positional arguments:
  file - Environment configuration file in JSON or YAML.

**environment-delete**:
::

    mistral environment-delete <environment> [<environment> ...]

Delete environment.

positional arguments:
  environment - Name of environment(s).

**environment-get**:
::

    mistral environment-get <name>

Show specific environment.

positional arguments:
  name - Environment name.

**environment-list**:
::

    mistral environment-list

List all environments.

**environment-update**:
::

    mistral environment-update <file>

Update environment.

positional arguments:
  file - Environment configuration file in JSON or YAML.


Members
^^^^^^^

**member-create**:
::

    mistral member-create <resource_id> <resource_type> <member_id>

Shares a resource to another tenant.

positional arguments:
  resource_id - Resource ID to be shared.
  resource_type - Resource type.
  member_id - Project ID to whom the resource is shared to.

**member-delete**:
::

    mistral member-delete <resource> <resource_type> <member_id>

Delete a resource sharing relationship.

positional arguments:
  resource - Resource ID to be shared.
  resource_type - Resource type.
  member_id - Project ID to whom the resource is shared to.

**member-get**:
::

    mistral member-get [-m MEMBER_ID]
                              <resource> <resource_type>

Show specific member information.

positional arguments:
  resource - Resource ID to be shared.
  resource_type - Resource type.

optional arguments:
  -m MEMBER_ID, --member-id MEMBER_ID
                        Project ID to whom the resource is shared to. No need
                        to provide this param if you are the resource member.

**member-list**:
::

    mistral member-list <resource_id> <resource_type>

List all members.

positional arguments:
  resource_id - Resource id to be shared.
  resource_type - Resource type.

**member-update**:
::

    mistral member-update [-m MEMBER_ID]
                                 [-s {pending,accepted,rejected}]
                                 <resource_id> <resource_type>

Update resource sharing status.

positional arguments:
  resource_id - Resource ID to be shared.
  resource_type - Resource type.

optional arguments:
  -m MEMBER_ID, --member-id MEMBER_ID
                        Project ID to whom the resource is shared to. No need
                        to provide this param if you are the resource member.
  -s {pending,accepted,rejected}, --status {pending,accepted,rejected}
                        status of the sharing.

Services API
^^^^^^^^^^^^

**service-list**:
::

    mistral service-list

List all services.

.. seealso::
   `Workflow service command-line client <http://docs.openstack.org/cli-reference/mistral.html>`_.
