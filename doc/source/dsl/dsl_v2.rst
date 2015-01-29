Mistral DSL v2 specification
============================

**NOTE**: DSL described in this document might slightly change within a
short period of time (2-3 weeks) and should be now considered
**experimental**. Mistral team is now actively working on stabilization.

Introduction
------------

Current document fully describes Domain Specific Language (DSL) version
2 of Mistral Workflow Service. Since version 1 issued in May 2014
Mistral team completely reworked the language pursuing with the goal in
mind to make it easier to understand while more consistent and flexible.

Unlike Mistral DSL v1 this second version of DSL assumes that all
entities that Mistral works with like workflows, actions and triggers
are completely independent in terms of how they're referenced and
accessed through API (and also Python Client API and CLI). Workbooks,
the entity that can combine combine workflows/actions/triggers still
exist in the language but only for namespacing and convenience purposes.
See `Workbooks section <#Workbooks>`__ for more details.

All DSL consists of the following main object(entity) types that will be
described in details next:

-  `Workflows <#Workflows>`__
-  `Actions <#Actions>`__
-  `Triggers <#Triggers>`__

Prerequisites
-------------

Mistral DSL is fully based on YAML and knowledge of YAML is a plus for
better understanding of the material in this specification. It also
takes advantage of YAQL query language to define expressions in
workflow, action and trigger definitions.

-  Yet Another Markup Language (YAML): http://yaml.org
-  Yet Another Query Language (YAQL):
   https://pypi.python.org/pypi/yaql/0.3

Workflows
---------

Workflow is the main building block of Mistral DSL, the reason why the
project exists. Workflow represents a process that can be described in a
various number of ways and that can do some job interesting to the end
user. Each workflow consists of tasks (at least one) describing what
exact steps should be made during workflow execution.

YAML example
^^^^^^^^^^^^

| ``---``
| ``version: '2.0'``
| ``create_vm:``
| ``  description: Simple workflow sample``
| ``  type: direct``
| ``  input: # Input parameter declarations``
| ``    - vm_name``
| ``    - image_ref``
| ``    - flavor_ref``
| ``  output: # Output definition``
| ``    vm_id: $.vm_id``
| ``  tasks:``
| ``    create_server:``
| ``      action: nova.servers_create name={$.vm_name} image={$.image_ref} flavor={$.flavor_ref}``
| ``      publish:``
| ``        vm_id: $.id``
| ``      on-success:``
| ``        - wait_for_instance``
| ``    wait_for_instance:``
| ``      action: nova.servers_find id={$.vm_id} status='ACTIVE'``
| ``      policies:``
| ``        retry:``
| ``          delay: 5``
| ``          count: 15``

Workflow Types
^^^^^^^^^^^^^^

Mistral DSL v2 introduces different workflow types and the structure of
each workflow type varies according to its semantics. Currently, Mistral
provides two workflow types:

-  `Direct workflow <#direct-workflow>`__
-  `Reverse workflow <#reverse-workflow>`__

See corresponding sections for details.

Common Workflow Attributes
^^^^^^^^^^^^^^^^^^^^^^^^^^

-  **type** - Workflow type. Either 'direct' or 'reverse'. *Required*.
-  **description** - Arbitrary text containing workflow description.
   *Optional*.
-  **input** - List defining required input parameter names. *Optional*.
-  **output** - Any data structure arbitrarily containing YAQL
   expressions that defines workflow output. May be nested. *Optional*.
-  **task-defaults** - Default settings for some of task attributes
   defined at workflow level. *Optional*. Corresponding attribute
   defined for a specific task always takes precedence. Specific task
   attributes that could be defined in **task-defaults** are the
   following:

   -  **on-error**
   -  **on-success**
   -  **on-complete**
   -  **policies**

-  **tasks** - Dictionary containing workflow tasks. See below for more
   details. *Required*.

Tasks
^^^^^

Task is what a workflow consists of. It defines a specific computational
step in the workflow. Each task can optionally take input data and
produce output. In Mistral DSL v2 task can be associated with an action
or with calling a workflow. In the example below there are two tasks of
different types: 

.. code-block:: yaml

  action_based_task:
     action: std.http url='openstack.org'
  workflow_based_task:
     workflow: backup_vm_workflow vm_id={$.vm_id}


Actions will be explained below in a individual paragraph but looking
ahead it's worth saying that Mistral provides a lot of actions out of
the box (including actions for most of the core OpenStack services) and
it's also easy to plug new actions into Mistral.

Common Task Attributes
''''''''''''''''''''''

All Mistral tasks regardless of workflow type have the following common
attributes:

-  **description** - Arbitrary text containing task description.
   *Optional*.
-  **action** - Name of the action associated with the task. *Required
   but mutually exclusive with* **workflow**.
-  **workflow** - Name of the workflow associated with the task.
   *Mutually exclusive with* **action**.
-  **input** - Actual input parameter values of the task. *Optional*.
   Value of each parameter is a JSON-compliant type such as number,
   string etc, dictionary or list. It can also be a YAQL expression to
   retrieve value from task context or any of the mentioned types
   containing inline YAQL expressions (for example, string
   "{$.movie\_name} is a cool movie!")
-  **publish** - Dictionary of variables to publish to the workflow
   context. Any JSON-compatible data structure optionally containing
   YAQL expression to select precisely what needs to be published.
   Published variables will be accessible for downstream tasks via using
   YAQL expressions. *Optional*.
-  **policies** - Dictionary-like section defining task policies that
   influence how Mistral Engine runs tasks. Policies are explained in a
   separate `paragraph <#Policies>`__. *Optional*.

Policies
''''''''

Any Mistral task regardless of what its workflow type can optionally
have configured policies.

YAML example
            

| ``my_task:``
| ``  ...``
| ``  policies:``
| ``    wait-before: 2``
| ``    wait-after: 4``
| ``    pause-before: $.my_expr``
| ``    timeout: 30``
| ``    retry:``
| ``      count: 10``
| ``      delay: 20``
| ``      break-on: $.my_var = True``

'wait-before'


Defines a delay in seconds that Mistral Engine should wait before
starting a task.

'wait-after'


Defines a delay in seconds that Mistral Engine should wait after a task
has completed before starting next tasks defined in 'on-success',
'on-error' or 'on-complete'.

'pause-before'


The Mistral Engine will pause the workflow and its task with the 'pause-before'
policy before executing it.  The workflow and task will be paused until a
resume signal is received.  This policy accepts a YAQL expression which will
cause the policy to be applied only if the expression evaluates to 'True'.

'timeout'
         

Defines a period of time in seconds after which a task will be failed
automatically by engine if hasn't completed.

'retry'


Defines a pattern how task should be repeated in case of an error.

-  **count** - Defines a maximum number of times that a task can be
   repeated.
-  **delay** - Defines a delay in seconds between subsequent task
   iterations.
-  **break-on** - Defines a YAQL expression that will break iteration
   loop if it evaluates to 'True'. If it fires then the task is
   considered successful.

Simplified Input Syntax
'''''''''''''''''''''''

When describing a workflow task it's possible to specify its input
parameters in two ways:

Full syntax:

| ``my_task:``
| ``  action: std.http``
| ``  input:``
| ``    url: ``\ ```http://mywebsite.org`` <http://mywebsite.org>`__
| ``    method: GET``

Simplified syntax:

| `` my_task:``
| ``   action: std.http url="``\ ```http://mywebsite.org`` <http://mywebsite.org>`__\ ``" method="GET"``

The same rules apply to tasks associated with workflows.

Full syntax:

| ``my_task:``
| ``  workflow: some_nested_workflow``
| ``  input:``
| ``    param1: val1``
| ``    param2: val2``

Simplified syntax:

| `` my_task:``
| ``   workflow: some_nested_workflow param1='val1' param2='val2'``

**Note**: It's also possible to merge these two approaches and specify a
part of parameters using simplified key-value pairs syntax and using
keyword 'input'. In this case all the parameters will be effectively
merged. If the same parameter is specified in both ways then the one
under 'input' keyword takes precedence.

Direct Workflow
^^^^^^^^^^^^^^^

Direct workflow consists of tasks combined in a graph where every next
task starts after another one depending on produced result. So direct
workflow has a notion of transition. Direct workflow is considered to be
completed if there aren't any transitions left that could be used to
jump to next tasks.

| |Figure 1. Mistral Direct Workflow.|

   Figure 1. Mistral Direct Workflow.

YAML example
''''''''''''

| ``---``
| ``version: '2.0'``
| ``create_vm_and_send_email:``
| ``  type: direct``
| ``  input:``
| ``    - vm_name``
| ``    - image_id``
| ``    - flavor_id``
| ``  output:``
| ``    result: $.vm_id``
| ``  tasks:``
| ``    create_vm:``
| ``      action: nova.servers_create name={$.vm_name} image={$.image_id} flavor={$.flavor_id}``
| ``      publish:``
| ``        vm_id: $.id``
| ``      on-error:``
| ``        - send_error_email``
| ``      on-success:``
| ``        - send_success_email``
| ``    send_error_email:``
| ``      action: send_email to='admin@mysite.org' body='Failed to create a VM'``
| ``      on_complete:``
| ``        - fail``
| ``    send_success_email:``
| ``      action: send_email to='admin@mysite.org' body='Vm is successfully created and its id: {$.vm_id}'``

Transitions with YAQL expressions
'''''''''''''''''''''''''''''''''

Task transitions can be determined by success/error/completeness of the
previous tasks and also by additional YAQL guard expressions that can
access any data produced by upstream tasks. So in the example above task
'create\_vm' could also have a YAQL expression on transition to task
'send\_success\_email' as follows:

| ``create_vm:``
| ``  ...``
| ``  on-success:``
| ``    - send_success_email: $.vm_id != null``

And this would tell Mistral to run 'send\_success\_email' task only if
'vm\_id' variable published by task 'create\_vm' is not empty. YAQL
expressions can also be applied to 'on-error' and 'on-complete'.

Direct Workflow Task Attributes
'''''''''''''''''''''''''''''''

-  **on-success** - List of tasks which will run after the task has
   completed successfully. *Optional*.
-  **on-error** - List of tasks which will run after the task has
   completed with an error. *Optional*.
-  **on-complete** - List of tasks which will run after the task has
   completed regardless of whether it is successful or not. *Optional*.

Reverse Workflow
^^^^^^^^^^^^^^^^

In reverse workflow all relationships in workflow task graph are
dependencies. In order to run this type of workflow we need to specify a
task that needs to be completed, it can be conventionally called 'target
task'. When Mistral Engine starts a workflow it recursively identifies
all the dependencies that need to be completed first.

| |Figure 2. Mistral Reverse Workflow.|

   Figure 2. Mistral Reverse Workflow.

Figure 2 explains how reverse workflow works. In the example, task
**T1** is chosen a target task. So when the workflow starts Mistral will
run only tasks **T7**, **T8**, **T5**, **T6**, **T2** and **T1** in the
specified order (starting from tasks that have no dependencies). Tasks
**T3** and **T4** won't be a part of this workflow because there's no
route in the directed graph from **T1** to **T3** or **T4**.

YAML example
''''''''''''

| ``---``
| ``version: '2.0'``
| ``create_vm_and_send_email:``
| ``  type: reverse``
| ``  input:``
| ``    - vm_name``
| ``    - image_id``
| ``    - flavor_id``
| ``  output:``
| ``    result: $.vm_id``
| ``  tasks:``
| ``    create_vm:``
| ``      action: nova.servers_create name={$.vm_name} image={$.image_id} flavor={$.flavor_id}``
| ``      publish:``
| ``        vm_id: $.id``
| ``    search_for_ip:``
| ``      action: nova.floating_ips_findall instance_id=null``
| ``      publish:``
| ``        vm_ip: $[0].ip``
| ``    associate_ip:``
| ``      action: nova.servers_add_floating_ip server={$.vm_id} address={$.vm_ip}``
| ``      requires: [search_for_ip]``
| ``    send_email:``
| ``      action: send_email to='admin@mysite.org' body='Vm is created and id {$.vm_id} and ip address {$.vm_ip}'``
| ``      requires: [create_vm, associate_ip]``

Reverse Workflow Task Attributes
''''''''''''''''''''''''''''''''

-  **requires** - List of tasks which should be executed before this
   task. *Optional*.


Actions
-------

Action defines what exactly needs to be done when task starts. Action is
similar to a regular function in general purpose programming language
like Python. It has a name and parameters. Mistral distinguishes 'system
actions' and 'Ad-hoc actions'.

System Actions
^^^^^^^^^^^^^^

System actions are provided by Mistral out of the box and can be used by
anyone. It is also possible to add system actions for specific Mistral
installation via a special plugin mechanism. Currently, built-in system
actions are:

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
-  **allow\_redirects** - Boolean. Set to True if POST/PUT/DELETE
   redirect following is allowed. *Optional*.
-  **proxies** - Dictionary mapping protocol to the URL of the proxy.
   *Optional*.

| 
| Example:

| ``http_task:``
| ``  action: std.http url='google.com'``

std.mistral\_http
'''''''''''''''''

This actions works just like 'std.http' with the only exception: when
sending a request it inserts the following HTTP headers:

-  **Mistral-Execution-Id** - Identifier of the workflow execution this
   action is associated with.
-  **Mistral-Task-Id** - Identifier of the task instance this action is
   associated with.

Using this action makes it possible to do any work in asynchronous
manner triggered via HTTP protocol. That means that Mistral can send a
request using 'std.mistral\_http' and then any time later whatever
system that received this request can notify Mistral back (using its
public API) with the result of this action. Header **Mistral-Task-Id**
is required for this operation because it is used a key to find
corresponding task in Mistral to attach the result to.

std.email
'''''''''

Sends an email message via SMTP protocol.

-  **params** - Dictionary containing the following keys:

   -  **to** - Comma separated list of recipients. *Required*.
   -  **subject** - Subject of the message. *Required*.
   -  **body** - Text containing message body. *Required*.

-  **settings** - Dictionary containing the following keys:

   -  **from** - Sender email address. *Required*.
   -  **smtp\_server** - SMTP server host name. *Required*.
   -  **password** - SMTP server password. *Required*.

| 
| Example:

| ``http_task:``
| ``  action: std.email``
| ``  input:``
| ``    params:``
| ``      to: admin@mywebsite.org``
| ``      subject: Hello from Mistral :)``
| ``      body: |``
| ``        Cheers! (:_:)``
| ``        -- Thanks, Mistral Team.``
| ``    settings:``
| ``      from: mistral@openstack.org``
| ``      smtp_server: smtp.google.com``
| ``      password: SECRET ``

The syntax of 'std.emal' action is pretty verbose. However, it can be
significantly simplified using Ad-hoc actions. More about them
`below <#Ad-hoc_Actions>`__.

std.ssh
'''''''

Runs Secure Shell command.

Input parameters:

-  **cmd** - String containing a shell command that needs to be
   executed. *Required*.
-  **host** - Host name that the command needs to be executed on.
   *Required*.
-  **username** - User name to authenticate on the host.
-  **password** - User password to to authenticate on the host.

| 
| **Note**: Authentication using key pairs is currently not supported.

std.echo
''''''''

Simple action mostly needed for testing purposes that returns a
predefined result.

Input parameters:

-  **output** - Value of any type that needs to be returned as a result
   of the action. *Required*.

Ad-hoc Actions
^^^^^^^^^^^^^^

Ad-hoc action is a special type of action that can be created by user.
Ad-hoc action is always created as a wrapper around any other existing
system action and its main goal is to simplify using same actions many
times with similar pattern.

**Note**: Nested ad-hoc actions currently are not supported (i.e. ad-hoc
action around another ad-hoc action).

YAML example
''''''''''''

| ``---``
| ``version: '2.0'``
| ``error_email:``
| ``  input:``
| ``    - execution_id``
| ``  base: std.email``
| ``  base-input:``
| ``    params:``
| ``      to: admin@mywebsite.org``
| ``      subject: Something went wrong with your Mistral workflow :(``
| ``      body: |``
| ``          Please take a look at Mistral Dashboard to find out what's wrong``
| ``          with your workflow execution {$.execution_id}.``
| ``          Everything's going to be alright!``
| ``          -- Sincerely, Mistral Team.``
| ``      settings:``
| ``        from: mistral@openstack.org``
| ``        smtp_server: smtp.google.com``
| ``        password: SECRET ``

Once this action is uploaded to Mistral any workflow will be able to use
it as follows:

| ``my_workflow:``
| ``  tasks:``
| ``    ...``
| ``    send_error_email``
| ``      action: error_email execution_id={$.__execution.id}``

Attributes
''''''''''

-  **base** - Name of base action that this action is built on top of.
   *Required*.
-  **base-input** - Actual input parameters provided to base action.
   Look at the example above. *Optional*.
-  **input** - List of declared action parameters which should be
   specified as corresponding task input. This attribute is optional and
   used only for documenting purposes. Mistral now does not enforce
   actual input parameters to exactly correspond to this list. Based
   parameters will be calculated based on provided actual parameters
   with using YAQL expressions so what's used in expressions implicitly
   define real input parameters. Dictionary of actual input parameters
   is referenced in YAQL as '$.'. Redundant parameters will be simply
   ignored.
-  **output** - Any data structure defining how to calculate output of
   this action based on output of base action. It can optionally have
   YAQL expressions to access properties of base action output
   referenced in YAQL as '$.'.

Triggers [coming soon...]
-------------------------

**NOTE**: Triggers are not yet implemented as part of version 0.1, they
will go into in one of the next builds, likely 0.2

Using triggers it is possible to run workflows according to specific
rules: periodically setting a cron (http://en.wikipedia.org/wiki/Cron)
pattern or on external events like ceilometer alarm.

Below are two options picturing what Mistral team is currently
discussing as a candidate for implementation:

Option 1:

| ``---``
| ``version: '2.0'``
| ``cron_trigger:``
| ``  type: periodic``
| ``  parameters:``
| ``    cron-pattern: "*/1 * * * *"``
| ``  workflows:``
| ``    - wf1:``
| ``      parameters:``
| ``        # Regular dictionary (heavy syntax)``
| ``      ...``
| ``    - wf2 param1=val1 param2=val2 task_name='task1' # Short syntax``
| ``  actions:``
| ``    # The same for actions``

Option 2:

| ``---``
| ``version: '2.0'``
| ``cron_trigger:``
| ``  type: periodic``
| ``  parameters:``
| ``    cron-pattern: "*/1 * * * *"``
| ``  workflows: ["wf2 param1=val1 param2=val2 task_name='task1'", ...] # List of workflows with using simplified syntax.``
| ``  actions: # same for actions``

If you are interested in this functionality you can participate in
mailing list
`openstack-dev@lists.openstack.org <mailto:openstack-dev@lists.openstack.org?subject=%5Bopenstack-dev%5D%5Bmistral%5D>`__.

Workbooks
---------

As mentioned before, workbooks still exist in Mistral DSL version 2 but
purely for convenience. Using workbooks users can combine multiple
entities of any type (workflows, actions and triggers) into one document
and upload to Mistral service. When uploading a workbook Mistral will
parse it and save its workflows, actions and triggers as independent
objects which will be accessible via their own API endpoints
(/workflows, /actions and /triggers/). Once it's done the workbook comes
out of the game. User can just start workflows and use references to
workflows/actions/triggers as if they were uploaded without workbook in
the first place. However, if we want to modify these individual objects
we can modify the same workbook definition and re-upload it to Mistral
(or, of course, we can do it independently).

Namespacing
^^^^^^^^^^^

One thing that's worth noting is that when using a workbook Mistral uses
its name as a prefix for generating final names of workflows, actions
and triggers included into the workbook. To illustrate this principle
let's take a look at the figure below.

| |Figure 3. Mistral Workbook Namespacing.|
|  So after a workbook has been uploaded its workflows, actions and
   triggers become independent objects but with slightly different
   names.

YAML example
^^^^^^^^^^^^

| ``---``
| ``version: '2.0'``
| ``name: my_workbook``
| ``description: My set of workflows and ad-hoc actions``
| ``workflows:``
| ``  local_workflow1:``
| ``    type: direct``
| ``    ``
| ``    tasks:``
| ``      task1:``
| ``        action: local_action str1='Hi' str2=' Mistral!'``
| ``        on-complete:``
| ``          - task2``
| ``    task2:``
| ``      action: global_action``
| ``      ...``
| ``    ``
| ``  local_workflow2:``
| ``    type: reverse``
| ``    tasks:``
| ``      task1:``
| ``        workflow: local_workflow1``
| ``        on-complete:``
| ``          - task2``
| ``      ``
| ``      task2:``
| ``        workflow: global_workflow param1='val1' param2='val2'``
| ``        ...``
| ``actions:``
| ``  local_action:``
| ``    input:``
| ``      - str1``
| ``      - str2``
| ``    base: std.echo output="{$.str1}{$.str2}"``

**Note**: Even though names of objects inside workbooks change upon
uploading Mistral allows referencing between those objects using local
names declared in the original workbook.

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
-  **triggers** - Dictionary containing trigger definitions. *Optional*.
   (**Currently not supported**)

.. |Figure 1. Mistral Direct Workflow.| image:: /img/Mistral_direct_workflow.png
.. |Figure 2. Mistral Reverse Workflow.| image:: /img/Mistral_reverse_workflow.png
.. |Figure 3. Mistral Workbook Namespacing.| image:: /img/Mistral_workbook_namespacing.png
