Mistral Workflow Language v2 specification
==========================================

Introduction
------------

This document fully describes Mistral Workflow Language version 2 of Mistral
Workflow Service. Since version 1 issued in May 2014 Mistral team completely
reworked the language pursuing the goal in mind to make it easier to understand
while more consistent and flexible.

Unlike Mistral Workflow Language v1, v2 assumes that all entities that Mistral
works with like workflows and actions are completely independent in terms of
how they're referenced and accessed through API (and also Python Client API and
CLI). Workbook, the entity that can combine workflows and actions still exists
in the language but only for namespacing and convenience purposes. See
`Workbooks section <#workbooks>`__ for more details.

**NOTE**: Mistral Workflow Language and API of version 1 has not been supported
since April 2015 and version 2 is now the only way to interact with Mistral
service.

Mistral Workflow Language consists of the following main object(entity) types
that will be described in details below:

-  `Workflows <#workflows>`__
-  `Actions <#actions>`__

Prerequisites
-------------

Mistral Workflow Language supports
`YAQL <https://pypi.org/project/yaql>`__ and
`Jinja2 <http://jinja.pocoo.org/docs/dev/>`__ expression languages to reference
workflow context variables and thereby implements passing data between workflow
tasks. It's also referred to as Data Flow mechanism. YAQL is a simple but
powerful query language that allows to extract needed information from JSON
structured data. Although Jinja2 is primarily a templating technology, Mistral
also uses it for evaluating expressions so users have a choice between YAQL and
Jinja2. It's also possible to combine both expression languages within one
workflow definition. The only limitation is that it's impossible to use both
types of expressions within one line. As long as there are YAQL and Jinja2
expressions on different lines of the workflow definition text, it is valid.
It is allowed to use YAQL/Jinja2 in the following sections of
Mistral Workflow Language:

-  Workflow `'output' attribute <#common-workflow-attributes>`__
-  Workflow `'task-defaults' attribute <#common-workflow-attributes>`__
-  `Direct workflow <#direct-workflow>`__ transitions
-  Task `'publish' attribute <#common-task-attributes>`__
-  Task `'input' attribute <#common-task-attributes>`__
-  Task `'with-items' attribute <#common-task-attributes>`__
-  Task `'target' attribute <#common-task-attributes>`__
-  Any attribute of `task policies <#policies>`__
-  Action `'base-input' attribute <#attributes>`__
-  Action `'output' attribute <#attributes>`__

Mistral Workflow Language is fully based on YAML and knowledge of YAML is a
plus for better understanding of the material in this specification. It also
takes advantage of supported query languages to define expressions in workflow
and action definitions.

-  Yet Another Markup Language (YAML): http://yaml.org
-  Yet Another Query Language (YAQL): https://pypi.org/project/yaql/1.0.0
-  Jinja 2: http://jinja.pocoo.org/docs/dev/

Workflows
---------

Workflow is the main building block of Mistral Workflow Language, the reason
why the project exists. Workflow represents a process that can be described in
a various number of ways and that can do some job interesting to the end user.
Each workflow consists of tasks (at least one) describing what exact steps
should be made during workflow execution.

YAML example
^^^^^^^^^^^^

.. code-block:: mistral

    ---
    version: '2.0'

    create_vm:
      description: Simple workflow example
      type: direct

      input:
        - vm_name
        - image_ref
        - flavor_ref
      output:
        vm_id: <% $.vm_id %>

      tasks:
        create_server:
          action: nova.servers_create name=<% $.vm_name %> image=<% $.image_ref %> flavor=<% $.flavor_ref %>
          publish:
            vm_id: <% task(create_server).result.id %>
          on-success:
            - wait_for_instance

        wait_for_instance:
          action: nova.servers_find id=<% $.vm_id %> status='ACTIVE'
          retry:
            delay: 5
            count: 15

This example workflow simply sends a command to OpenStack Compute
service Nova to start creating a virtual machine and wait till it's
created using special "retry" policy.

Workflow types
^^^^^^^^^^^^^^

Mistral Workflow Language v2 introduces different workflow types and the
structure of each workflow type varies according to its semantics. Basically,
workflow type encapsulates workflow processing logic, a set of meta rules
defining how all workflows of this type should work. Currently, Mistral
provides two workflow types:

-  `Direct workflow <#direct-workflow>`__
-  `Reverse workflow <#reverse-workflow>`__

See corresponding sections for details.

Common workflow attributes
^^^^^^^^^^^^^^^^^^^^^^^^^^

-  **type** - Workflow type. Either 'direct' or 'reverse'. *Optional*. 'direct'
   by default.
-  **description** - Arbitrary text containing workflow description. *Optional*.
-  **input** - List defining required input parameter names and
   optionally their default values in a form "my_param: 123". *Optional*.
-  **output** - Any data structure arbitrarily containing YAQL/Jinja2
   expressions that defines workflow output. May be nested. *Optional*.
-  **output-on-error** - Any data structure arbitrarily containing YAQL/Jinja2
   expressions that defines output of a workflow to be returned if it goes into
   error state. May be nested. *Optional*.
-  **task-defaults** - Default settings for some of task attributes
   defined at workflow level. *Optional*. Corresponding attribute
   defined for a specific task always takes precedence. Specific task
   attributes that could be defined in **task-defaults** are the
   following:

   -  **on-error** - List of tasks which will run after the task has
      completed with an error. For `direct
      workflow <#direct-workflow>`__ only. *Optional*.
   -  **on-success** - List of tasks which will run after the task has
      completed successfully. For `direct workflow <#direct-workflow>`__
      only. *Optional*.
   -  **on-complete** - List of tasks which will run after the task has
      completed regardless of whether it is successful or not. For
      `direct workflow <#direct-workflow>`__ only. *Optional*.
   -  **requires** - List of tasks that a task depends on. For `reverse
      workflow <#Reverse_Workflow>`__ only. *Optional*.
   -  **pause-before** - Configures pause-before policy. *Optional*.
   -  **wait-before** - Configures wait-before policy. *Optional*.
   -  **wait-after** - Configures wait-after policy. *Optional*.
   -  **timeout** - Configures timeout policy. *Optional*.
   -  **retry** - Configures retry policy. *Optional*.
   -  **concurrency** - Configures concurrency policy. *Optional*.
   -  **safe-rerun** - Configures safe-rerun policy. *Optional*.

-  **tasks** - Dictionary containing workflow tasks. See below for more
   details. *Required*.

Tasks
^^^^^

Task is what a workflow consists of. It defines a specific computational
step in the workflow. When the workflow engine processes entities described
in the workflow text written in YAML it schedules tasks for execution.
Scheduling a task means that it's now eligible for execution and will be run
some time later. When exactly it will run depends on the system load and
configuration. Each task can optionally take input data and produce output.
In Mistral Workflow Language v2, task can be associated with an action or a
workflow. In the example below there are two tasks of different types:

.. code-block:: mistral

    action_based_task:
      action: std.http url='openstack.org'

    workflow_based_task:
      workflow: backup_vm_workflow vm_id=<% $.vm_id %>

Actions will be explained below in an individual paragraph but looking
ahead it's worth saying that Mistral provides a lot of actions out of
the box (including actions for most of the core OpenStack services) and
it's also easy to plug new actions into Mistral.

Common task attributes
''''''''''''''''''''''

All Mistral tasks, regardless of workflow type, have the following common
attributes:

-  **name** - Task name must not equal *noop*, *fail*, *succeed* or *pause*
   . The max length is 255 symbols. For tasks with *join* control flow this
   restriction is 208 symbols.
-  **description** - Arbitrary text containing task description.
   *Optional*.
-  **action** - Name of the action associated with the task. Can be a static
   value or an expression (for example,  "{{ _.action_name }}").
   *Mutually exclusive with* **workflow**. If neither action nor workflow are
   provided then the action 'std.noop' will be used that does nothing.
-  **workflow** - Name of the workflow associated with the task. Can be a static
   value or an expression (for example,  "{{ _.subworkflow_name }}").
   *Mutually exclusive with* **action**.
-  **input** - Actual input parameter values of the task's action or workflow.
   *Optional*. Value of each parameter is a JSON-compliant type such as number,
   string etc, dictionary or list. It can also be a YAQL/Jinja2 expression to
   retrieve value from task context or any of the mentioned types
   containing inline expressions (for example, string "<%
   $.movie_name %> is a cool movie!") Can be an expression that evaluates to
   a JSON object.
-  **publish** - Dictionary of variables to publish to the workflow
   context. Any JSON-compatible data structure optionally containing
   expression to select precisely what needs to be published.
   Published variables will be accessible for downstream tasks via using
   expressions. *Optional*.
-  **publish-on-error** - Same as **publish** but evaluated in case of
   task execution failures. *Optional*
-  **with-items** - If configured, it allows to run action or workflow
   associated with a task multiple times on a provided list of items.
   See `Processing collections using
   'with-items' <#processing-collections>`__ for details. *Optional*.
-  **keep-result** - Boolean value allowing to not store action results
   after task completion (e.g. if they are large and not needed
   afterwards). *Optional*. By default is 'true'.
-  **target** - String parameter. It defines an executor to which task
   action should be sent to. Target here physically means a name of
   executors group but task will be run only on one of them. *Optional*.
-  **pause-before** - Configures pause-before policy. *Optional*.
-  **wait-before** - Configures wait-before policy. *Optional*.
-  **wait-after** - Configures wait-after policy. *Optional*.
-  **timeout** - Configures timeout policy. *Optional*.
-  **retry** - Configures retry policy. *Optional*.
-  **concurrency** - Configures concurrency policy. *Optional*.
-  **safe-rerun** - Boolean value allowing to rerun task if executor dies
   during action execution. If set to 'true' task may be run twice.
   *Optional*. By default set to 'false'.

workflow
''''''''
If a task has the attribute 'workflow' it synchronously starts a sub-workflow
with the given name.

Example of a static sub-workflow name:

.. code-block:: mistral

    my_task:
      workflow: name_of_my_workflow

Example of a dynamic sub-workflow name:

.. code-block:: mistral

  ---
  version: '2.0'

  framework:
    input:
      - magic_workflow_name: show_weather

    tasks:
      weather_data:
        action: std.echo
        input:
          output:
            location: wherever
            temperature: "22C"
        publish:
          weather_data: <% task().result %>
        on-success:
          - do_magic

      do_magic:
        # Reference workflow by parameter.
        workflow: <% $.magic_workflow_name %>
        # Expand dictionary to input parameters.
        input: <% $.weather_data %>

  show_weather:
    input:
      - location
      - temperature

    tasks:
      write_data:
        action: std.echo
        input:
          output: "<% $.location %>: <% $.temperature %>"

In this example, we defined two workflows in one YAML snippet and the workflow
'framework' may call the workflow 'show_weather' if 'framework' receives the
corresponding workflow name through the input parameter 'magic_workflow_name'.
In this case it is set by default so a user doesn't need to pass anything
explicitly.

Note: Typical use for the dynamic sub-workflow selection is when parts of a
workflow can be customized. E.g. collect some weather data and then execute
some custom workflow on it.


Policies
''''''''

Any Mistral task regardless of its workflow type can optionally have
configured policies.

YAML example

.. code-block:: mistral

    my_task:
      action: my_action
      pause-before: true
      wait-before: 2
      wait-after: 4
      timeout: 30
      retry:
        count: 10
        delay: 20
        break-on: <% $.my_var = true %>
        continue-on: <% $.my_var = false %>

**pause-before**

Defines whether Mistral Engine should put the workflow on hold or not
before starting a task.


**wait-before**

Defines a delay in seconds that Mistral Engine should wait before
starting a task.


**wait-after**

Defines a delay in seconds that Mistral Engine should wait after a task
has completed before starting next tasks defined in *on-success*,
*on-error* or *on-complete*.


**timeout**

Defines a period of time in seconds after which a task will be failed
automatically by engine if it hasn't completed.


**concurrency**

Defines a max number of actions running simultaneously in a task. *Applicable*
only for tasks that have *with-items*. If *concurrency* task property is not
set then actions (or workflows in case of nested workflows) of the task will
be scheduled for execution all at once.


**retry**

Defines a pattern how task should be repeated in case of an error.

-  **count** - Defines a maximum number of times that a task can be
   repeated.
-  **delay** - Defines a delay in seconds between subsequent task
   iterations.
-  **break-on** - Defines an expression that will break iteration
   loop if it evaluates to 'true'. If it fires then the task is
   considered error.
-  **continue-on** - Defines an expression that will continue iteration
   loop if it evaluates to 'true'. If it fires then the task is
   considered successful. If it evaluates to 'false' then policy will break the
   iteration.

Retry policy can also be configured on a single line as:

.. code-block:: mistral

    task1:
      action: my_action
      retry: count=10 delay=5 break-on=<% $.foo = 'bar' %>

All parameter values for any policy can be defined as YAQL/Jinja2 expressions.

**NOTE:** It would be rare to use both break-on and continue-on in the same
retry block. *break-on* should be used when one expects the action to be in an
ERROR state for some amount of tries, but may eventually go to a SUCCESS state,
thereby stopping the loop. But if *break-on* is *'true'* then the retries will
stop and the task will be in ERROR. *continue-on* should be used if the action
will usually return *SUCCESS*, but the action has other results that can be
used to signal whether to continue the loop or not.

Input syntax
''''''''''''

When describing a workflow task it's possible to specify its input
parameters in two ways:

Full syntax:

.. code-block:: mistral

    my_task:
      action: std.http
      input:
        url: http://mywebsite.org
        method: GET

Simplified syntax:

.. code-block:: mistral

    my_task:
      action: std.http url="http://mywebsite.org" method="GET"

Syntax with dynamic input parameter map:

.. code-block:: mistral

    ---
    version: '2.0'

    example_workflow:
      input:
        - http_request_parameters:
            url: http://mywebsite.org
            method: GET

      tasks:
        setup_task:
          action: std.http
          input: <% $.http_request_parameters %>


The same rules apply to tasks associated with workflows.

Full syntax:

.. code-block:: mistral

    my_task:
      workflow: some_nested_workflow
      input:
        param1: val1
        param2: val2

Simplified syntax:

.. code-block:: mistral

    my_task:
      workflow: some_nested_workflow param1='val1' param2='val2'

Syntax with dynamic input parameter map:

.. code-block:: mistral

    ---
    version: '2.0'

    example_workflow:
      input:
        - nested_params: {"param1": "val1", "param2": "val2"}

      tasks:
        setup_task:
          workflow: some_nested_workflow
          input: <% $.nested_params %>

**NOTE**: It's also possible to merge these two approaches and specify a part
of parameters using simplified key-value pairs syntax and using keyword *input*.
In this case all the parameters will be effectively merged. If the same
parameter is specified in both ways then the one under *input* keyword takes
precedence.

Direct workflow
^^^^^^^^^^^^^^^

Direct workflow consists of tasks combined in a graph where every next task
starts after another one depending on produced result. So direct workflow has a
notion of transition. Direct workflow is considered to be completed if there
aren't any transitions left that could be used to jump to next tasks.

.. image:: /img/Mistral_direct_workflow.png

Figure 1. Mistral Direct Workflow.

YAML example
''''''''''''

.. code-block:: mistral

    ---
    version: '2.0'

    create_vm_and_send_email:
      type: direct

      input:
        - vm_name
        - image_id
        - flavor_id

      output:
        result: <% $.vm_id %>

      tasks:
        create_vm:
          action: nova.servers_create name=<% $.vm_name %> image=<% $.image_id %> flavor=<% $.flavor_id %>
          publish:
            vm_id: <% task(create_vm).result.id %>
          on-error:
            - send_error_email
          on-success:
            - send_success_email

        send_error_email:
          action: send_email to_addrs=['admin@mysite.org'] body='Failed to create a VM'
          on-complete:
            - fail

        send_success_email:
          action: send_email to_addrs=['admin@mysite.org'] body='Vm is successfully created and its id <% $.vm_id %>'

Direct workflow task attributes
'''''''''''''''''''''''''''''''

-  **on-success** - List of tasks which will run after the task has
   completed successfully. *Optional*.
-  **on-error** - List of tasks which will run after the task has
   completed with an error. *Optional*.
-  **on-complete** - List of tasks which will run after the task has
   completed regardless of whether it is successful or not. *Optional*.

Note: All of the above clauses cannot contain task names evaluated as
YAQL/Jinja expressions. They have to be static values. However, task
transitions can be conditional, based on expressions. See
`Transitions with expressions <#transitions-with-expressions>`__ for more
details.

It is important to understand the semantics of **on-success**, **on-error**
and **on-complete** around handling action errors.

In case if task action returned an error **on-success** and **on-complete**
won't prevent from failing the entire workflow execution. Only **on-error**
will. The closest analogy is *try-catch-finally* blocks in regular
programming languages. **on-error** is similar to *catch* and it serves
as an exception handler for possible errors expected by design. Whereas
**on-complete** is like *finally* that will run in any case but it won't
stop the exception from bubbling up to an upper layer. So **on-complete**
should only be understood as a language construction that allows to
define some clean up actions.

Having that said, it's important to know the order in which these clauses
are processed by Mistral.

.. code-block:: mistral

    taskA:
     action: my_action
     on-success:
       - taskB
       - taskC
     on-complete:
       - taskD
       - taskE

In this example, if the task action ('my_action') completes successfully then
Mistral will first process the 'on-success' clause and schedule tasks 'taskB'
and 'taskC' and then process the 'on-complete' clause and schedule 'taskC' and
'taskE'. In most cases, this processing order is not so important but there are
situations when it matters, especially when both 'on-success' and 'on-complete'
lists have `engine commands <#engine-commands>`__ that are explained later in
this document.

If 'on-success' and 'on-error' are both defined in the task definition, they
never clash because they are mutually exclusive which means that only one of
them can be processed depending on whether the task action failed or succeeded.


Transitions with expressions
''''''''''''''''''''''''''''

Task transitions can be determined by success/error/completeness of the
previous tasks and also by additional guard expressions that can access any
data produced by upstream tasks and as workflow input. So in the example above
task 'create_vm' could also have a YAQL expression on transition to task
'send_success_email' as follows:

.. code-block:: mistral

    create_vm:
     ...
     on-success:
       - send_success_email: <% $.vm_id != null %>

And this would tell Mistral to run 'send_success_email' task only if 'vm_id'
variable published by task 'create_vm' is not empty. Expressions can also be
applied to 'on-error' and 'on-complete'.

Engine Commands
'''''''''''''''

Mistral has a number of engine commands that can be called within direct
workflows. These commands are used to change the workflow state.

-  **succeed** - will end the current workflow and set its state to SUCCESS.
-  **pause** - will end the current workflow and set its state to PAUSED.
-  **fail** - will end the current workflow and set its state to ERROR.

Each of the engine commands accepts a ``msg`` input. This is optional, but if
provided, it will be stored in the state info on the workflow execution.

Workflows that have been ended with ``succeed`` or ``fail`` may not be resumed
later, but workflows that have been ended with ``pause`` may be.

YAML example
''''''''''''

.. code-block:: mistral

    ---
    version: '2.0'

    send_error_mail:
      tasks:
        create_server:
          action: nova.servers_create name=<% $.vm_name %>
          publish:
            vm_id: <% task().result.id %>
          on-complete:
            - fail: <% not $.vm_id %>

In this example we have a short workflow with one task that creates a server
in Nova. The task publishes the ID of the virtual machine, but if this value
is empty then it will fail the workflow.

.. code-block:: mistral

    on-complete:
      - taskA
      - fail
      - taskB

When the engine commands are used with task names in a single list, they are
processed one at a time until the workflow reaches a terminal state. In the
above example, the ``on-complete`` has three steps to complete - these are
executed in order until the workflow reaches a terminal state. So in this case
``taskA`` is scheduled first, then the ``fail`` engine command sets the
workflow state to ERROR and ``taskB`` is never scheduled. ``taskB`` would not be
scheduled if ``succeed`` was used in this example either.

The ``pause`` command pauses the workflow. This means that the workflow can
continue when its state is set to RUNNING by using the update Rest API call.

YAML example:

.. code-block:: mistral

    on-complete:
      - taskA
      - pause
      - taskB

In this case when Mistral processes the 'on-complete' clause it will schedule
``taskA`` and then set the workflow state to PAUSED, and stop scheduling new
tasks. However, if the workflow is later resumed manually then Mistral will
schedule ``taskB`` because in the 'on-complete' list it goes right after the
``pause`` command.

Given the order in which Mistral processes 'on-success' (or 'on-error') and
'on-complete' clauses it's important to understand what will happen if both
clauses have engine commands listed in them.

.. code-block:: mistral

    taskA:
     action: my_action
     on-error:
       - taskB
       - fail
       - taskC
     on-complete:
       - taskD
       - pause
       - taskE

As was explained above, 'on-complete' is always processed after 'on-success'
(or 'on-error') because it plays the similar role as 'finally' in most general
purpose programming languages. Let's consider two scenarios that can happen
in the example above when 'taskA' runs, i.e. its action 'my_action' runs.

-  If 'my_action' fails then Mistral will schedule 'taskB' because it's
   listed in the 'on-error' clause which is processed before the
   'on-complete' and then will set the state of the workflow to ERROR.
   This will prevent from scheduling other new tasks so neither 'taskC' nor
   'taskD' and 'taskE' will be ever be scheduled. In other words, the whole
   'on-complete' clause will never be processed because the 'fail' command in
   the 'on-success' sets the workflow state to ERROR.
-  If 'my_action' succeeds then the 'on-error' clause will be ignored and since
   'on-success' is not defined then Mistral will process the 'on-complete'
   clause. And while doing that, it will schedule 'taskD' first and then pause
   the workflow because of the 'pause' command. 'taskE' will be scheduled if
   this workflow is resumed manually at some later time through the API.

This illustrates that, while designing a workflow, it's important to know
precisely how Mistral processes 'on-success', 'on-error' and 'on-complete'
and engine commands.

Engine commands and tasks
'''''''''''''''''''''''''

The **on-*** clauses in direct workflows can refer both to tasks and engine
commands, as demonstrated earlier. It is possible to use the engine commands
as names for tasks. For example, one can create a task named `noop` or `fail`.
These tasks will override the engine commands, that is, the action defined
in these tasks will be executed instead of the engine commands. This is a
method to succinctly extend the default behavior of the Mistral engine or
provide side-effect free workflow examples.

The order in which task names are resolved is the following:

1. the task with the given name is searched
2. the engine command with the given name is selected

The first option that matches is executed.

Fork
''''

There are situations when we need to be able to run more than one task after
some task has completed.

.. code-block:: mistral

    create_vm:
      ...
      on-success:
        - register_vm_in_load_balancer
        - register_vm_in_dns

In this case Mistral will run both "register_xxx" tasks simultaneously and this
will lead to multiple independent workflow routes being processed in parallel.

Join
''''

Join flow control allows to synchronize multiple parallel workflow branches and
aggregate their data.

Full Join (join: all)

.. code-block:: mistral

    register_vm_in_load_balancer:
      ...
      on-success:
        - wait_for_all_registrations

    register_vm_in_dns:
      ...
      on-success:
        - wait_for_all_registrations

    try_to_do_something_without_registration:
      ...
      on-error:
       - wait_for_all_registrations

    wait_for_all_registrations:
      join: all
      action: send_email

When a task has property "join" assigned with value "all" the task will run
only if all upstream tasks (ones that lead to this task) are completed and
corresponding conditions have triggered. Task A is considered an upstream task
of Task B if Task A has Task B mentioned in any of its "on-success", "on-error"
and "on-complete" clauses regardless of guard expressions.

Partial Join (join: 2)

.. code-block:: mistral

    register_vm_in_load_balancer:
      ...
      on-success:
        - wait_for_two_registrations

    register_vm_in_dns:
      ...
      on-success:
        - wait_for_two_registrations

    register_vm_in_zabbix:
      ...
      on-success:
        - wait_for_two_registrations

    wait_for_two_registrations:
      join: 2
      action: send_email

When a task has property "join" assigned with a numeric value then the task
will run when at least this number of upstream tasks are completed and
corresponding conditions have triggered. In the example above task
"wait_for_two_registrations" will run if two any of
"register_vm_xxx" tasks complete.

Discriminator (join: one)


Discriminator is a special case of Partial Join when "join" property has value
1. It means Mistral will wait for any completed task. In this case instead of 1
it is possible to specify special string value "one" which is introduced for
symmetry with "all". However, it's up to the user whether to use "1" or "one".

Reverse workflow
^^^^^^^^^^^^^^^^

In reverse workflow all relationships in workflow task graph are dependencies.
In order to run this type of workflow we need to specify a task that needs to
be completed, it can be conventionally called 'target task'. When Mistral
Engine starts a workflow it recursively identifies all the dependencies that
need to be completed first.

.. image:: /img/Mistral_reverse_workflow.png

Figure 2 explains how reverse workflow works. In the example, task **T1** is
chosen a target task. So when the workflow starts Mistral will run only tasks
**T7**, **T8**, **T5**, **T6**, **T2** and **T1** in the specified order
(starting from tasks that have no dependencies). Tasks **T3** and **T4** won't
be a part of this workflow because there's no route in the directed graph from
**T1** to **T3** or **T4**.

YAML example
''''''''''''

.. code-block:: mistral

    ---
    version: '2.0'

    create_vm_and_send_email:
      type: reverse

      input:
        - vm_name
        - image_id
        - flavor_id

      output:
        result: <% $.vm_id %>

      tasks:
        create_vm:
          action: nova.servers_create name=<% $.vm_name %> image=<% $.image_id %> flavor=<% $.flavor_id %>
          publish:
            vm_id: <% task(create_vm).result.id %>

        search_for_ip:
          action: nova.floating_ips_findall instance_id=null
          publish:
            vm_ip: <% task(search_for_ip).result[0].ip %>

        associate_ip:
          action: nova.servers_add_floating_ip server=<% $.vm_id %> address=<% $.vm_ip %>
          requires: [search_for_ip]

        send_email:
          action: send_email to='admin@mysite.org' body='Vm is created and id <% $.vm_id %> and ip address <% $.vm_ip %>'
          requires: [create_vm, associate_ip]

Reverse workflow task attributes
''''''''''''''''''''''''''''''''

-  **requires** - List of tasks which should be executed before this
   task. *Optional*.

Processing collections
^^^^^^^^^^^^^^^^^^^^^^

YAML example
''''''''''''

.. code-block:: mistral

    ---
    version: '2.0'

    create_vms:
      description: Creating multiple virtual servers using "with-items".

      input:
        - vm_names
        - image_ref
        - flavor_ref

      output:
        vm_ids: <% $.vm_ids %>

      tasks:
        create_servers:
          with-items: vm_name in <% $.vm_names %>
          action: nova.servers_create name=<% $.vm_name %> image=<% $.image_ref %> flavor=<% $.flavor_ref %>
          publish:
            vm_ids: <% task(create_servers).result.id %>
          on-success:
            - wait_for_servers

        wait_for_servers:
          with-items: vm_id in <% $.vm_ids %>
          action: nova.servers_find id=<% $.vm_id %> status='ACTIVE'
          retry:
            delay: 5
            count: <% $.vm_names.len() * 10 %>

Workflow "create_vms" in this example creates as many virtual servers as we
provide in "vm_names" input parameter. E.g., if we specify
vm_names=["vm1", "vm2"] then it'll create servers with these names based on
same image and flavor. It is possible because of using "with-items" keyword
that makes an action or a workflow associated with a task run multiple times.
Value of "with-items" task property contains an expression in the form: 'my_var' in
<% YAQL_expression %>. Similar for Jinja2 expression: 'my_var' in
{{ Jinja2_expression }}.

The most common form is:

.. code-block:: mistral

    with-items:
      - var1 in <% YAQL_expression_1 %> # or: var1 in <% Jinja2_expression_1 %>
      - var2 in <% YAQL_expression_2 %> # or: var2 in <% Jinja2_expression_2 %>
      ...
      - varN in <% YAQL_expression_N %> # or: varN in <% Jinja2_expression_N %>

where collections expressed as YAQL_expression_1, YAQL_expression_2,
YAQL_expression_N must have equal sizes. When a task gets started Mistral will
iterate over all collections in parallel, i.e. number of iterations will be
equal to length of any collections.

Note that in case of using "with-items" task result accessible in workflow
context as <% task(task_name).result %> will be a list containing results of
corresponding action/workflow calls. If at least one action/workflow call has
failed then the whole task will get into ERROR state. It's also possible to
apply retry policy for tasks with "with-items" property. In this case retry
policy will be relaunching all action/workflow calls according to "with-items"
configuration. Other policies can also be used the same way as with regular non
"with-items" tasks.

.. _actions-dsl:

Actions
-------

Action defines what exactly needs to be done when task starts. Action is
similar to a regular function in general purpose programming language like
Python. It has a name and parameters. Mistral distinguishes 'system actions'
and 'Ad-hoc actions'.

System actions
^^^^^^^^^^^^^^

System actions are provided by Mistral out of the box and can be used by anyone.
It is also possible to add system actions for specific Mistral installation via
a special plugin mechanism. Currently, built-in system actions are:

std.fail
''''''''

This action always fails. It can be used to manually fail a workflow task..

.. code-block:: mistral

  wf:
    tasks:
      manual_fail:
        action: std.fail

The action can be passed the `error_data` parameter. This data will be used as
the action return value.

.. code-block:: mistral

  wf:
    tasks:
      manual_fail:
        action: std.fail
        input: error_data={x:1,y:2}

std.http
''''''''

Sends an HTTP request.

Input parameters:

-  **url** - URL for the HTTP request. *Required*.
-  **method** - method for the HTTP request. *Optional*. Default is
   'GET'.
-  **params** - Dictionary or bytes to be sent in the query string for
   the HTTP request. *Optional*.
-  **body** - Dictionary, bytes, or file-like object to send in the body
   of the HTTP request. *Optional*.
-  **headers** - Dictionary of HTTP Headers to send with the HTTP
   request. *Optional*.
-  **cookies** - Dictionary of HTTP Cookies to send with the HTTP
   request. *Optional*.
-  **auth** - Auth to enable Basic/Digest/Custom HTTP Auth. *Optional*.
-  **timeout** - Float describing the timeout of the request in seconds.
   *Optional*.
-  **allow_redirects** - Boolean. Set to True if POST/PUT/DELETE
   redirect following is allowed. *Optional*.
-  **proxies** - Dictionary mapping protocol to the URL of the proxy.
   *Optional*.
-  **verify** - Either a boolean, in which case it controls whether we verify
   the server's TLS certificate, or a string, in which case it must be a path
   to a CA bundle to use. *Optional*. Default is 'True'.

Example:

.. code-block:: mistral

    http_task:
      action: std.http url='google.com'

std.mistral_http
''''''''''''''''

This action works just like 'std.http' with the only exception: when sending a
request it inserts the following HTTP headers:

-  **Mistral-Workflow-Name** - Name of the workflow that the current
   action execution is associated with.
-  **Mistral-Execution-Id** - Identifier of the workflow execution this
   action is associated with.
-  **Mistral-Task-Id** - Identifier of the task execution this action
   execution is associated with.
-  **Mistral-Action-Execution-Id** - Identifier of the current action
   execution.

Using this action makes it possible to do any work in asynchronous manner
triggered via HTTP protocol. That means that Mistral can send a request using
'std.mistral_http' and then any time later whatever system that received this
request can notify Mistral back (using its public API) with the result of this
action. Header **Mistral-Action-Execution-Id** is required for this operation
because it is used a key to find corresponding action execution in Mistral to
attach the result to.

std.email
'''''''''

Sends an email message via SMTP protocol.

-  **to_addrs** - Comma separated list of recipients. *Required*.
-  **cc_addrs** - Comma separated list of CC recipients. *Optional*.
-  **bcc_addrs** - Comma separated list of BCC recipients. *Optional*.
-  **subject** - Subject of the message. *Optional*.
-  **body** - Text containing message body. *Optional*.
-  **html_body** - Text containing the message in HTML format. *Optional*.
-  **from_addr** - Sender email address. *Required*.
-  **smtp_server** - SMTP server host name. *Required*.
-  **smtp_password** - SMTP server password. *Required*.

Example:

.. code-block:: mistral

    send_email_task:
      action: std.email
      input:
          to_addrs: [admin@mywebsite.org]
          subject: Hello from Mistral :)
          body: |
            Cheers! (:_:)
            -- Thanks, Mistral Team.
          from_addr: mistral@openstack.org
          smtp_server: smtp.google.com
          smtp_password: SECRET

The syntax of 'std.emal' action is pretty verbose. However, it can be
significantly simplified using Ad-hoc actions. More about them
`below <#ad-hoc-actions>`__.

std.ssh
'''''''

Runs Secure Shell command.

Input parameters:

-  **cmd** - String containing a shell command that needs to be
   executed. *Required*.
-  **host** - Host name that the command needs to be executed on.
   *Required*.
-  **username** - User name to authenticate on the host. *Required*.
-  **password** - User password to authenticate on the host. *Optional*.
-  **private_key_filename** - Private key file name which will be used for
   authentication on remote host. All private keys should be on the executor
   host in **<home-user-directory>/.ssh** directory or absolute path of
   the key should be provided. The file needs to be accessible
   for the user account running the executor. *Optional*.

**NOTE**: Authentication using key pairs is supported, key should be
on Mistral Executor server machine.

std.echo
''''''''

Simple action mostly needed for testing purposes that returns a predefined
result.

Input parameters:

-  **output** - Value of any type that needs to be returned as a result
   of the action. *Required*.

std.javascript
''''''''''''''

Evaluates given JavaScript code.

**NOTE**: std.js is an alias for std.javascript i.e, std.js can be used in
place of std.javascript.

Input parameters:

-  **script** - The text of JavaScript snippet that needs to be
   executed. *Required*.
- **context** - This object will be assigned to the *$* javascript variable.
  The default value is None.

To use std.javascript, it is needed to install the
`py_mini_racer <https://github.com/sqreen/PyMiniRacer>`__ and set
*py_mini_racer* to *js_implementation* parameter in *mistral.conf*:

.. code-block:: bash

    pip install py_mini_racer

Other available implementations:

- `pyv8 <https://code.google.com/archive/p/pyv8>`__
- `v8eval <https://github.com/sony/v8eval>`__

Example with *context*:

.. code-block:: mistral

    ---
    version: '2.0'

    generate_uuid:
      description: Generates a Universal Unique ID

      input:
        - radix: 16

      output:
        uuid: <% $.generated_uuid %>

      tasks:
        generate_uuid_task:
          action: std.js
          input:
            context: <% $ %>
            script: |
              return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
                      var r = Math.random() * 16 | 0, v = c == 'x' ? r : (r&0x3|0x8);
                      return v.toString($.radix);
              });
          publish:
            generated_uuid: <% task().result %>

Another example for getting the current date and time:

.. code-block:: mistral

      ---
      version: '2.0'

      get_date_workflow:
        description: Get the current date

        output:
          current_date: <% $.current_date %>

        tasks:
          get_date_task:
            action: std.js
            input:
              script: |
                var date = new Date();
                return date; // returns "2015-07-12T10:32:12.460000" or use date.toLocaleDateString() for "Sunday, July 12, 2015"
            publish:
              current_date: <% task().result %>

Ad-hoc actions
^^^^^^^^^^^^^^

Ad-hoc action is a special type of action that can be created by user. Ad-hoc
action is always created as a wrapper around any other existing system action
and its main goal is to simplify using same actions many times with similar
pattern.

YAML example
''''''''''''

.. code-block:: mistral

    ---
    version: '2.0'

    error_email:
      input:
        - execution_id
      base: std.email
      base-input:
        to_addrs: ['admin@mywebsite.org']
        subject: 'Something went wrong with your Mistral workflow :('
        body: |
            Please take a look at Mistral Dashboard to find out what's wrong
            with your workflow execution <% $.execution_id %>.
            Everything's going to be alright!
            -- Sincerely, Mistral Team.
        from_addr: 'mistral@openstack.org'
        smtp_server: 'smtp.google.com'
        smtp_password: 'SECRET'

Once this action is uploaded to Mistral any workflow will be able to use it as
follows:

.. code-block:: mistral

    my_workflow:
      tasks:
        ...
        send_error_email:
          action: error_email execution_id=<% execution().id %>

Attributes
''''''''''

-  **base** - Name of base action that this action is built on top of.
   *Required*.
-  **base-input** - Actual input parameters provided to base action. Look at the
   example above. *Optional*.
-  **input** - List of declared action parameters which should be specified as
   corresponding task input. This attribute is optional and used only for
   documenting purposes. Mistral now does not enforce actual input parameters to
   exactly correspond to this list. Base parameters will be calculated based on
   provided actual parameters with using expressions so what's used in
   expressions implicitly define real input parameters. Dictionary of actual
   input parameters (expression context) is referenced as '$.' in YAQL and as
   '_.' in Jinja. Redundant parameters will be simply ignored.
-  **output** - Any data structure defining how to calculate output of this
   action based on output of base action. It can optionally have expressions to
   access properties of base action output through expression context.

Workbooks
---------

As mentioned before, workbooks still exist in Mistral Workflow Language version
2 but purely for convenience. Using workbooks users can combine multiple
entities of any type (workflows, actions and triggers) into one document and
upload to Mistral service. When uploading a workbook Mistral will parse it and
save its workflows, actions and triggers as independent objects which will be
accessible via their own API endpoints (/workflows, /actions and /triggers/).
Once it's done the workbook comes out of the game. User can just start workflows
and use references to workflows/actions/triggers as if they were uploaded
without workbook in the first place. However, if we want to modify these
individual objects we can modify the same workbook definition and re-upload it
to Mistral (or, of course, we can do it independently).

Namespacing
^^^^^^^^^^^

One thing that's worth noting is that when using a workbook Mistral uses its
name as a prefix for generating final names of workflows, actions and triggers
included into the workbook. To illustrate this principle let's take a look at
the figure below.

.. image:: /img/Mistral_workbook_namespacing.png

So after a workbook has been uploaded its workflows and actions become
independent objects but with slightly different names.

YAML example
''''''''''''

.. code-block:: mistral

    ---
    version: '2.0'

    name: my_workbook

    description: My set of workflows and ad-hoc actions

    workflows:
      local_workflow1:
        type: direct

        tasks:
          task1:
            action: local_action str1='Hi' str2=' Mistral!'
            on-complete:
              - task2

          task2:
            action: global_action
            ...

      local_workflow2:
        type: reverse

        tasks:
          task1:
            workflow: local_workflow1

          task2:
            workflow: global_workflow param1='val1' param2='val2'
            requires: [task1]
            ...
    actions:
      local_action:
        input:
          - str1
          - str2
        base: std.echo output="<% $.str1 %><% $.str2 %>"

**NOTE**: Even though names of objects inside workbooks change upon uploading
Mistral allows referencing between those objects using local names declared in
the original workbook.

Attributes
^^^^^^^^^^

-  **name** - Workbook name. *Required*.
-  **description** - Workbook description. *Optional*.
-  **tags** - String with arbitrary comma-separated values.
   **Optional**.
-  **workflows** - Dictionary containing workflow definitions.
   *Optional*.
-  **actions** - Dictionary containing ad-hoc action definitions.
   *Optional*.

Predefined values/Functions in execution data context
-----------------------------------------------------

Using expressions it is possible to use some predefined values in Mistral
Workflow Language.

-  **OpenStack context**
-  **Task result**
-  **Execution info**
-  **Environment**

OpenStack context
^^^^^^^^^^^^^^^^^

OpenStack context is available by **$.openstack**. It contains **auth_token**,
**project_id**, **user_id**, **service_catalog**, **user_name**,
**project_name**, **roles**, **is_admin** properties.


Builtin functions in expressions
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

In addition to the current context (i.e. $ in YAQL and _ in Jinja2) expressions
have access to a set of predefined functions.


The expression languages come with their own individual included functions and
operations. Mistral adds the following functions that are available in all the
supported languages.

This section will describe builtin functions added by Mistral.

Tasks function
''''''''''''''

Signature:
  **tasks(workflow_execution_id=null, recursive=false, state=null, flat=false)**

Description:

  This function allows users to filter all tasks by workflow execution id
  and/or state. In addition, it is possible to get task executions recursively
  and flatten the task executions list.

Parameters:

  #. **workflow_execution_id** - If provided the tasks function will return
     task executions for a specific workflow execution (either the current
     execution or a different one). Otherwise it will return all task
     executions that match the other parameters. *Optional.*
  #. **recursive** - This parameter is a boolean value, if it is true then all
     task executions within nested workflow executions will be returned. This
     is usually used in combination with a specific workflow_execution_id
     where you still want to see nested workflow's task executions. *Optional.*
     False by default.
  #. **state** - If provided, the task executions will be filtered by their
     current state. If state isn't provided, all task executions that match the
     other parameters will be returned . *Optional.*
  #. **flat** - if true, only list the task executions that match at least one
     of the next conditions:

       * task executions of type action
       * task executions of type workflow that have a different state from the
         workflow execution they triggered. For example, if used with a
         specific workflow_execution_id and the state ERROR it will return
         tasks that erred despite the workflow succeeding. This can mean that
         there was an error in the task itself, like an invalid expression in
         publish.

     *Optional.* False by default.

Example:

Workflow definition:

.. code-block:: mistral

  ---
  version: "v2.0"
  wf:
    tasks:
      task:
        action: std.noop
        publish:
          all_tasks_in_this_wf_yaql: <% tasks(execution().id) %>
          all_tasks_in_this_wf_jinja: "{{ tasks(execution().id) }}"

          all_tasks_in_error_yaql: <% tasks(null, false, ERROR) %>
          all_tasks_in_error_jinja: "{{ tasks(None, false, 'ERROR') }}"
          all_tasks_in_error_yaql_with_kw: <% tasks(state => ERROR) %>
          all_tasks_in_error_jinja_with_kw: "{{ tasks(state='ERROR') }}"

          all_tasks_yaql_option1: <% tasks() %>
          all_tasks_yaql_option2: <% tasks(null, false, null, false) %>
          all_tasks_jinja_option1: "{{ tasks() }}"
          all_tasks_jinja_option2: "{{ tasks(None, false, None, false) }}"

Task publish result (partial to keep the documentation short):

.. warning::
  The return value for each task execution hasn't been finalized and isn't
  considered stable. It may change in a future Mistral release.

.. code-block:: json

  {
      "all_tasks_in_error_yaql": [
          {
              "id": "3d363d4b-8c19-48fa-a9a0-8721dc5469f2",
              "name": "fail_task",
              "type": "ACTION",
              "workflow_execution_id": "c0a4d2ff-0127-4826-8370-0570ef8cad80",
              "state": "ERROR",
              "state_info": "Failed to run action [action_ex_id=bcb04b28-6d50-458e-9b7e-a45a5ff1ca01, action_cls='<class 'mistral.actions.action_factory.FailAction'>', attributes='{}', params='{}']\n Fail action expected exception.",
              "result": "Failed to run action [action_ex_id=bcb04b28-6d50-458e-9b7e-a45a5ff1ca01, action_cls='<class 'mistral.actions.action_factory.FailAction'>', attributes='{}', params='{}']\n Fail action expected exception.",
              "published": {},
              "spec": {
                  "action": "std.fail",
                  "version": "2.0",
                  "type": "direct",
                  "name": "fail_task"
              }
          }
      ],
      "all_tasks_in_this_wf_jinja": [
          {
              "id": "83a34bfe-268c-46f5-9e5c-c16900540084",
              "name": "task",
              "type": "ACTION",
              "workflow_execution_id": "899a3318-b5c0-4860-82b4-a5bd147a4643",
              "state": "SUCCESS",
              "state_info": null,
              "result": null,
              "published": {},
              "spec": {
                  "action": "std.noop",
                  "version": "2.0",
                  "type": "direct",
                  "name": "task",
                  "publish": {
                      "all_tasks_in_error_yaql": "<% tasks(null, false, ERROR) %>",
                      "all_tasks_in_error_jinja": "{{ tasks(None, false, 'ERROR') }}",
                      "all_tasks_yaql_option2": "<% tasks(null, false, false, false) %>",
                      "all_tasks_yaql_option1": "<% tasks() %>",
                      "all_tasks_jinja_option1": "{{ tasks() }}",
                      "all_tasks_in_error_jinja_with_kw": "{{ tasks(state='ERROR') }}",
                      "all_tasks_jinja_option2": "{{ tasks(None, false, None, false) }}",
                      "all_tasks_in_this_wf_jinja": "{{ tasks(execution().id) }}",
                      "all_tasks_in_this_wf_yaql": "<% tasks(execution().id) %>"
                  }
              }
          }
      ],
      "_comment": "other fields were dropped to keep docs short"
  }


Task result
'''''''''''

Task result is available by **task(<task_name>).result**. It contains task
result and directly depends on action output structure. Note that the
*task(<task_name>)* function itself returns more than only task result. It
returns the following fields of task executions:

* **id** - task execution UUID.
* **name** - task execution name.
* **spec** - task execution spec dict (loaded from Mistral Workflow Language).
* **state** - task execution state.
* **state_info** - task execution state info.
* **result** - task execution result. In case of a non 'with-items' task it's
  simply a result of the task's action/sub-workflow execution. For a
  'with-items' task it will be a list of results of corresponding
  action/sub-workflow execution.
* **published** - task execution published variables.


Execution info
^^^^^^^^^^^^^^

Execution info is available by **execution()**. It contains
information about execution itself such as **id**, **wf_spec**,
**input** and **start_params**.

Executions function
'''''''''''''''''''

Signature:
  **executions(id=null, root_execution_id=null, state=null,
  from_time=null, to_time=null)**

Description:

  This function allows users to filter all executions by execution id,
  root_execution_id ,state and/or created_at time.

Parameters:

  #. **id** - If provided will return a list of executions with that id.
     Otherwise it will return all executions that match the other
     parameters. *Optional.*
  #. **root_execution_id** - Similar to id above, if provided will return
     a list of executions with that root_execution_id. Otherwise it will
     return all executions that match the other parameters. *Optional.*
     False by default.
  #. **state** - If provided, the executions will be filtered by their
     current state. If state isn't provided, all executions that match the
     other parameters will be returned . *Optional.*
  #. **from_time** - If provided, the executions will be filtered by their
     created_at time being greater or equal to the from_time parameter.
     If from_time isn't provided, all executions that match the
     other parameters will be returned. from_time parameter can be provided
     in the format *YYYY-MM-DD hh:mm:ss*
     *Optional.*
  #. **to_time** - If provided, the executions will be filtered by their
     created_at time being less than to the from_time parameter (less than but
     not less than equal as the from_time parameter does)
     If to_time isn't provided, all executions that match the
     other parameters will be returned. to_time parameter can be provided
     in the format *YYYY-MM-DD hh:mm:ss*
     *Optional.*

Example:

Workflow definition:

.. code-block:: mistral

  ---
  version: "v2.0"
  wf:
    tasks:
      task:
        action: std.noop
        publish:
          all_executions_yaql: <% executions() %>
          all_child_executions_of_this_execution: "{{ executions(root_execution_id=execution().id) }}"

          all_executions_in_error_yaql: <% executions(null, null, ERROR) %>
          all_executions_in_error_jinja: "{{ executions(None, None, 'ERROR') }}"
          all_executions_in_error_yaql_with_kw: <% executions(state => ERROR) %>
          all_executions_in_error_jinja_with_kw: "{{ executions(state='ERROR') }}"

          all_executions_filtered_date_jinja: "{{ executions(to_time="2016-12-01 15:01:00") }}"


Environment
^^^^^^^^^^^

Environment info is available by **env()**. It is passed when user submits
workflow execution. It contains variables specified by user.
