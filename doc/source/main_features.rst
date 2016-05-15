Mistral Main Features
=====================


Task result / Data Flow
-----------------------

Mistral supports transferring data from one task to another. In other words, if *taskA* produces a value then
*taskB* which follows *taskA* can use it. In order to use this data Mistral relies on query language called
`YAQL <https://github.com/openstack/yaql>`_. YAQL is powerful yet simple tool that allows to filter needed information,
transform data and call functions. Find more information about it in
`YAQL official documentation <http://yaql.readthedocs.org>`_ . This mechanism allowing to transfer data plays one of the
central roles in workflow concept and is referred to as Data Flow.

Below is a simple example of how Mistral Data Flow looks like from DSL (workflow language) perspective:

::

 version: '2.0'

 my_workflow:
   input:
     - host
     - username
     - password

   tasks:
     task1:
       action: std.ssh host=<% $.host %> username=<% $.username %> password=<% $.password %>
       input:
         cmd: "cd ~ && ls"
       on-complete: task2

     task2:
       action: do_something data=<% task(task1).result %>

Task called "task1" produces a result that contains a list of files in a user home folder of a host (both username and
host are provided as workflow input) and task "task2" uses this data using YAQL expression "task(task1).result".
"task()" here is a function registered in YAQL by Mistral to get information about a task by its name.

Task affinity
-------------

Task affinity is a feature which could be useful for executing particular
tasks on specific Mistral executors. In fact, there are 2 cases:

1. Need to execute the task on single executor.
2. Need to execute the task on one of executor in executors group which has one name.

For enabling task affinity feature, edit section "executor" host property
in configuration file::

    [executor]
    host = my_favorite_executor

Then start (restart) executor. Use target task property to specify
this executor in Workflow DSL::

    ... Workflow YAML ...
    task1:
      ...
      target: my_favorite_executor
    ... Workflow YAML ...

Task policies
-------------

Any Mistral task regardless of its workflow type can optionally have configured policies.
Policies itself control the flow of the task - for example, policy can delay task execution before task starts
or after task completes.

YAML example
^^^^^^^^^^^^
::

    my_task:
      action: my_action
      pause-before: true
      wait-before: 2
      wait-after: 4
      timeout: 30
      retry:
        count: 10
        delay: 20
        break-on: <% $.my_var = true %>

There are different types of policies in Mistral.

1. **pause-before**

 Defines whether Mistral Engine should put the workflow on pause or not before starting a task.

2. **wait-before**

 Defines a delay in seconds that Mistral Engine should wait before starting a task.

3. **wait-after**

 Defines a delay in seconds that Mistral Engine should wait after a task has completed before starting next tasks defined in *'on-success'*, *'on-error'* or *'on-complete'*.

4. **timeout**

 Defines a period of time in seconds after which a task will be failed automatically by engine if hasn't completed.

5. **retry**

 Defines a pattern how task should be repeated.

* *count* - Defines a maximum number of times that a task can be repeated.
* *delay* - Defines a delay in seconds between subsequent task iterations.
* *break-on* - Defines a YAQL expression that will break iteration loop if it evaluates to *'true'*. If it fires then the task is considered error.
* *continue-on* - Defines a YAQL expression that will continue iteration loop if it evaluates to *'true'*. If it fires then the task is considered successful.

 Retry policy can also be configured on a single line as::

    task1:
      action: my_action
      retry: count=10 delay=5 break-on=<% $.foo = 'bar' %>

 All parameter values for any policy can be defined as YAQL expressions.

Join
----

Join flow control allows to synchronize multiple parallel workflow branches and aggregate their data.

**Full Join (join: all)**.

YAML example
^^^^^^^^^^^^
::

    register_vm_in_load_balancer:
      ...
      on-success:
        - wait_for_all_registrations

    register_vm_in_dns:
      ...
      on-success:
        - wait_for_all_registrations

    try_to_do_something_without_registration:
      ...
      on-error:
        - wait_for_all_registrations

    wait_for_all_registrations:
      join: all
      action: send_email

When a task has property *"join"* assigned with value *"all"* the task will run only
if all upstream tasks (ones that lead to this task) are completed and corresponding
conditions have triggered. Task A is considered an upstream task of Task B if Task A
has Task B mentioned in any of its *"on-success"*, *"on-error"* and *"on-complete"* clauses
regardless of YAQL guard expressions.

**Partial Join (join: 2)**

YAML example
^^^^^^^^^^^^
::

    register_vm_in_load_balancer:
      ...
      on-success:
        - wait_for_all_registrations

    register_vm_in_dns:
      ...
      on-success:
        - wait_for_all_registrations

    register_vm_in_zabbix:
      ...
      on-success:
        - wait_for_all_registrations

    wait_for_two_registrations:
      join: 2
      action: send_email

When a task has property *"join"* assigned with a numeric value then the task
will run once at least this number of upstream tasks are completed and
corresponding conditions have triggered. In the example about task
"wait_for_two_registrations" will run if two any of "register_vm_xxx" tasks complete.

**Discriminator (join: one)**

Discriminator is a special case of Partial Join when *"join"* property has value 1.
In this case instead of 1 it is possible to specify special string value *"one"*
which is introduced for symmetry with *"all"*. However, it's up to the user whether to use *"1"* or *"one"*.


Processing Collections (with-items)
-----------------------------------

YAML example
^^^^^^^^^^^^
::

    ---
    version: '2.0'

    create_vms:
      description: Creating multiple virtual servers using "with-items".
      input:
        - vm_names
        - image_ref
        - flavor_ref
      output:
        vm_ids: <% $.vm_ids %>

      tasks:
        create_servers:
          with-items: vm_name in <% $.vm_names %>
          action: nova.servers_create name=<% $.vm_name %> image=<% $.image_ref %> flavor=<% $.flavor_ref %>
          publish:
            vm_ids: <% $.create_servers.id %>
          on-success:
            - wait_for_servers

        wait_for_servers:
          with-items: vm_id in <% $.vm_ids %>
          action: nova.servers_find id=<% $.vm_id %> status='ACTIVE'
          retry:
            delay: 5
            count: <% $.vm_names.len() * 10 %>

Workflow *"create_vms"* in this example creates as many virtual servers as we
provide in *"vm_names"* input parameter. E.g., if it is specified *vm_names=["vm1", "vm2"]*
then it'll create servers with these names based on same image and flavor.
It is possible because of using *"with-items"* keyword that makes an action
or a workflow associated with a task run multiple times. Value of *"with-items"*
task property contains an expression in the form: **<variable_name> in <% YAQL_expression %>**.

The most common form is::

    with-items:
      - var1 in <% YAQL_expression_1 %>
      - var2 in <% YAQL_expression_2 %>
      ...
      - varN in <% YAQL_expression_N %>

where collections expressed as YAQL_expression_1, YAQL_expression_2,
YAQL_expression_N must have equal sizes. When a task gets started Mistral
will iterate over all collections in parallel, i.e. number of iterations will
be equal to length of any collections.

Note that in case of using *"with-items"* task result accessible in workflow
context as <% $.task_name %> will be a list containing results of corresponding
action/workflow calls. If at least one action/workflow call has failed then
the whole task will get into *ERROR* state. It's also possible to apply retry
policy for tasks with *"with-items"* property. In this case retry policy will
be relaunching all action/workflow calls according to *"with-items"*
configuration. Other policies can also be used the same way as with regular non *"with-items"* tasks.

Execution expiration policy
---------------------------

For Mistral used in production, it is often hardly to control the number of workflow executions. The number of
workflow executions is significantly growing for the long time of Mistral running. The purpose of this feature to
delete old workflow executions which has been already completed. The criteria is the time when a workflow execution was
updated last time.

**By default this feature is disabled.**

In order to configure this feature, please open and edit configuration file and specify time in minutes::

    [execution_expiration_policy]
    older_than = 10080  # Workflow executions older than 1 week will be deleted automatically.

