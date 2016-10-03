Mistral Client / CLI Guide
==========================

Mistralclient installation
--------------------------

To install ``python-mistralclient``, it is required to have ``pip``
(in most cases). Make sure that ``pip`` is installed. Then type::

    $ pip install python-mistralclient

Or, if it is needed to install ``python-mistralclient`` from master branch,
type::

    $ pip install git+https://github.com/openstack/python-mistralclient.git

After ``python-mistralclient`` is installed you will see command ``mistral``
in your environment.

Configure authentication against Keystone
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If Keystone is used for authentication in Mistral, then the environment should
have auth variables::

    $ export OS_AUTH_URL=http://<Keystone_host>:5000/v2.0
    $ export OS_USERNAME=admin
    $ export OS_TENANT_NAME=tenant
    $ export OS_PASSWORD=secret
    $ export OS_MISTRAL_URL=http://<Mistral host>:8989/v2  (optional, by default URL=http://localhost:8989/v2)

and in the case when you are authenticating against keystone over https::

    $ export OS_CACERT=<path_to_ca_cert>

.. note:: In client, we can use both Keystone auth versions - v2.0 and v3. But server supports only v3.

You can see the list of available commands by typing::

    $ mistral --help

To make sure Mistral client works, type::

    $ mistral workbook-list

Mistralclient commands
----------------------

Workbooks
^^^^^^^^^

**workbook-create**:
::

    usage: mistral workbook-create <definition>

Create new workbook.

positional arguments:
  definition - Workbook definition file.

**workbook-delete**:
::

    usage: mistral workbook-delete <name> [<name> ...]

Delete workbook.

positional arguments:
  name - Name of workbook(s).

**workbook-get**:
::

    usage: mistral workbook-get <name>

Show specific workbook.

positional arguments:
  name - Workbook name.

**workbook-get-definition**:
::

    usage: mistral workbook-get-definition <name>

Show workbook definition.

positional arguments:
  name - Workbook name.

**workbook-list**:
::

    usage: mistral workbook-list

List all workbooks.

**workbook-update**:
::

    usage: mistral workbook-update <definition>

Update workbook.

positional arguments:
  definition - Workbook definition file.

**workbook-validate**:
::

    usage: mistral workbook-validate <definition>

Validate workbook.

positional arguments:
  definition - Workbook definition file.

Workflows
^^^^^^^^^

**workflow-create**:
::

    usage: mistral workflow-create <definition> [--public]

Create new workflow.

positional arguments:
  definition - Workflow definition file.

optional arguments:
  --public - With this flag workflow will be marked as "public".

**workflow-delete**:
::

    usage: mistral workflow-delete <name> [<name> ...]

Delete workflow.

positional arguments:
  name - Name of workflow(s).

**workflow-get**:
::

    usage: mistral workflow-get <name>

Show specific workflow.

positional arguments:
  name - Workflow name.

**workflow-get-definition**:
::

    usage: mistral workflow-get-definition <name>

Show workflow definition.

positional arguments:
  name - Workflow name.

**workflow-list**:
::

    usage: mistral workflow-list

List all workflows.

**workflow-update**:
::

    usage: mistral workflow-update <definition>

Update workflow.

positional arguments:
  definition - Workflow definition.

**workflow-validate**:
::

    usage: mistral workflow-validate <definition>

Validate workflow.

positional arguments:
  definition - Workflow definition file.

Actions
^^^^^^^

**action-create**:
::

    usage: mistral action-create <definition> [--public]

Create new action.

positional arguments:
  definition - Action definition file.

optional arguments:
  --public - With this flag action will be marked as "public".

**action-delete**:
::

    usage: mistral action-delete action [action ...]

Delete action.

positional arguments:
  action - Name or ID of action(s).

**action-get**:
::

    usage: mistral action-get <action>

Show specific action.

positional arguments:
  action - Action (name or ID).

**action-get-definition**:
::

    usage: mistral action-get-definition <name>

Show action definition.

positional arguments:
  name - Action name.

**action-list**:
::

    usage: mistral action-list

List all actions.

**action-update**:
::

    usage: mistral action-update [--public] [--id ID] <definition>

Update action.

positional arguments:
  definition - Action definition file.

optional arguments:
  --id ID               Action ID.
  --public              With this flag, action will be marked as "public".

**action-validate**:
::

    usage: mistral action-validate <definition>

Validate action.

positional arguments:
  definition - Action definition file.

Workflow executions
^^^^^^^^^^^^^^^^^^^

**execution-create**:
::

    usage: mistral execution-create [-d DESCRIPTION]
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

    usage: mistral execution-delete <execution> [<execution> ...]

Delete execution.

positional arguments:
  execution - Id of execution identifier(s).

**execution-get**:
::

    usage: mistral execution-get <execution>

Show specific execution.

positional arguments:
  execution - Execution identifier.

**execution-get-input**:
::

    usage: mistral execution-get-input <id>

Show execution input data.

positional arguments:
  id - Execution ID.

**execution-get-output**:
::

    usage: mistral execution-get-output [-h] id

Show execution output data.

positional arguments:
  id - Execution ID.

**execution-list**:
::

    usage: mistral execution-list [--marker [MARKER]] [--limit [LIMIT]]
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

    usage: mistral execution-update [-s {RUNNING,PAUSED,SUCCESS,ERROR,CANCELLED}]
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

    usage: mistral task-get <id>

Show specific task.

positional arguments:
  id - Task identifier.

**task-get-published**:
::

    usage: mistral task-get-published <id>

Show task published variables.

positional arguments:
  id - Task ID.

**task-get-result**:
::

    usage: mistral task-get-result <id>

Show task output data.

positional arguments:
  id - Task ID.

**task-list**:
::

    usage: mistral task-list [<workflow_execution>]

List all tasks.

positional arguments:
  workflow_execution - Workflow execution ID associated with list of Tasks.

**task-rerun**:
::

    usage: mistral task-rerun [--resume] [-e ENV] <id>

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

    usage: mistral action-execution-delete <action_execution> [<action_execution> ...]

Delete action execution.

positional arguments:
  action_execution - Action execution ID.

**action-execution-get**:
::

    usage: mistral action-execution-get <action_execution>

Show specific Action execution.

positional arguments:
  action_execution - Action execution ID.

**action-execution-get-input**:
::

    usage: mistral action-execution-get-input <id>

Show Action execution input data.

positional arguments:
  id - Action execution ID.

**action-execution-get-output**:
::

    usage: mistral action-execution-get-output <id>

Show Action execution output data.

positional arguments:
  id - Action execution ID.

**action-execution-list**:
::

    usage: mistral action-execution-list [<task-execution-id>]

List all Action executions.

positional arguments:
  task-execution-id - Task execution ID.

**action-execution-update**:
::

    usage: mistral action-execution-update [--state {IDLE,RUNNING,SUCCESS,ERROR}] [--output <OUTPUT>] <id>

Update specific Action execution.

positional arguments:
  id - Action execution ID.

optional arguments:
  --state {IDLE,RUNNING,SUCCESS,ERROR}
                        Action execution state
  --output OUTPUT - Action execution output

**run-action**:
::

    usage: mistral run-action <name> [<input>] [-t <TARGET>]

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

    usage: mistral cron-trigger-create [--params <PARAMS>] [--pattern <* * * * *>]
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

    usage: mistral cron-trigger-delete <name> [<name> ...]

Delete trigger.

positional arguments:
  name - Name of cron trigger(s).

**cron-trigger-get**:
::

    usage: mistral cron-trigger-get <name>

Show specific cron trigger.

positional arguments:
  name - Cron trigger name.

**cron-trigger-list**:
::

    usage: mistral cron-trigger-list

List all cron triggers.

Environments
^^^^^^^^^^^^

**environment-create**:
::

    usage: mistral environment-create <file>

Create new environment.

positional arguments:
  file - Environment configuration file in JSON or YAML.

**environment-delete**:
::

    usage: mistral environment-delete <environment> [<environment> ...]

Delete environment.

positional arguments:
  environment - Name of environment(s).

**environment-get**:
::

    usage: mistral environment-get <name>

Show specific environment.

positional arguments:
  name - Environment name.

**environment-list**:
::

    usage: mistral environment-list

List all environments.

**environment-update**:
::

    usage: mistral environment-update <file>

Update environment.

positional arguments:
  file - Environment configuration file in JSON or YAML.


Members
^^^^^^^

**member-create**:
::

    usage: mistral member-create <resource_id> <resource_type> <member_id>

Shares a resource to another tenant.

positional arguments:
  resource_id - Resource ID to be shared.
  resource_type - Resource type.
  member_id - Project ID to whom the resource is shared to.

**member-delete**:
::

    usage: mistral member-delete <resource> <resource_type> <member_id>

Delete a resource sharing relationship.

positional arguments:
  resource - Resource ID to be shared.
  resource_type - Resource type.
  member_id - Project ID to whom the resource is shared to.

**member-get**:
::

    usage: mistral member-get [-m MEMBER_ID]
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

    usage: mistral member-list <resource_id> <resource_type>

List all members.

positional arguments:
  resource_id - Resource id to be shared.
  resource_type - Resource type.

**member-update**:
::

    usage: mistral member-update [-m MEMBER_ID]
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

    usage: mistral service-list

List all services.

.. seealso::
   `Workflow service command-line client <http://docs.openstack.org/cli-reference/mistral.html>`_.
