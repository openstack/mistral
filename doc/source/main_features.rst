Mistral Main Features
=====================


Task result / Data Flow
-----------------------

Mistral supports transferring data from one task to another. In other words, if *taskA* produces a value then
*taskB* which follows *taskA* can use it. In order to use this data Mistral relies on a query language called
`YAQL <https://github.com/openstack/yaql>`_. YAQL is a powerful yet simple tool
that allows the user to filter information,
transform data and call functions. Find more information about it in the
`YAQL official documentation <http://yaql.readthedocs.org>`_ . This mechanism for transferring data plays a
central role in the workflow concept and is referred to as Data Flow.

Below is a simple example of how Mistral Data Flow looks like from the DSL (workflow language) perspective:

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

The task called "task1" produces a result that contains a list of the files in a user's home folder on a host
(both username and host are provided as workflow input) and the task "task2" uses this data using the YAQL
expression "task(task1).result".
"task()" here is a function registered in YAQL by Mistral to get information about a task by its name.

Task affinity
-------------

Task affinity is a feature which could be useful for executing particular
tasks on specific Mistral executors. In fact, there are 2 cases:

1. You need to execute the task on a single executor.
2. You need to execute the task on any executor within a named group.

To enable the task affinity feature, edit the "host" property in the "executor" section of the configuration
file::

    [executor]
    host = my_favorite_executor

Then start (restart) the executor. Use the "target" task property to specify
this executor in Workflow DSL::

    ... Workflow YAML ...
    task1:
      ...
      target: my_favorite_executor
    ... Workflow YAML ...

Task policies
-------------

Any Mistral task regardless of its workflow type can optionally have configured policies.
Policies control the flow of the task - for example, a policy can delay task execution before the task starts
or after the task completes.

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

 Specifies whether Mistral Engine should put the workflow on pause or not before starting a task.

2. **wait-before**

 Specifies a delay in seconds that Mistral Engine should wait before starting a task.

3. **wait-after**

 Specifies a delay in seconds that Mistral Engine should wait after a task has completed before starting the tasks specified in *'on-success'*, *'on-error'* or *'on-complete'*.

4. **timeout**

 Specifies a period of time in seconds after which a task will be failed automatically by the engine if it hasn't completed.

5. **retry**

 Specifies a pattern for how the task should be repeated.

* *count* - Specifies a maximum number of times that a task can be repeated.
* *delay* - Specifies a delay in seconds between subsequent task iterations.
* *break-on* - Specifies a YAQL expression that will break the iteration loop if it evaluates to *'true'*. If
  it fires then the task is considered to have experienced an error.
* *continue-on* - Specifies a YAQL expression that will continue the iteration loop if it evaluates to
  *'true'*. If it fires then the task is considered successful.

 A retry policy can also be configured on a single line, as follows::

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

When a task has a numeric value assigned to the property *"join"*, then the task
will run once at least this number of upstream tasks are completed and the
corresponding conditions have triggered. In the example above, the task
"wait_for_two_registrations" will run if two any of the "register_vm_xxx" tasks are complete.

**Discriminator (join: one)**

Discriminator is the special case of Partial Join where the *"join"* property has the value 1.
In this case instead of 1 it is possible to specify the special string value *"one"*
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

The workflow *"create_vms"* in this example creates as many virtual servers as we
provide in the *"vm_names"* input parameter. E.g., if we specify *vm_names=["vm1", "vm2"]*
then it'll create servers with these names based on the same image and flavor.
This is possible because we are using the *"with-items"* keyword that associates an action
or a workflow with a task run multiple times. The value of the *"with-items"*
task property contains an expression in the form: **<variable_name> in <% YAQL_expression %>**.

The most common form is::

    with-items:
      - var1 in <% YAQL_expression_1 %>
      - var2 in <% YAQL_expression_2 %>
      ...
      - varN in <% YAQL_expression_N %>

where collections expressed as YAQL_expression_1, YAQL_expression_2,
YAQL_expression_N must have equal sizes. When a task gets started Mistral
will iterate over all collections in parallel, i.e. the number of iterations will
be equal to the length of any of the collections.

Note that in the *"with-items"* case, the task result (accessible in workflow
context as <% $.task_name %>) will be a list containing results of corresponding
action/workflow calls. If at least one action/workflow call has failed then
the whole task will get into *ERROR* state. It's also possible to apply retry
policy for tasks with a *"with-items"* property. In this case the retry policy will
relaunch all action/workflow calls according to the *"with-items"*
configuration. Other policies can also be used in the same way as with regular non-*"with-items"* tasks.

Execution expiration policy
---------------------------

When Mistral is used in production it can be difficult to control the number
of completed workflow executions. By default Mistral will store all
executions indefinitely and over time the number stored will accumulate. This
can be resolved by setting an expiration policy.

**By default this feature is disabled.**

When enabled, the policy will define the maximum age of an execution in
minutes since the last updated time. To enable and set a policy, edit the
Mistral configuration file and specify ``older_than`` and
``evaluation_interval`` in minutes.

.. code-block:: cfg

    [execution_expiration_policy]
    older_than = 10080  # 1 week
    evaluation_interval = 120  # 2 hours

For the expiration policy to be enabled, both of these configuration options
must be set.

- **older_than**

 This defines the maximum age of an execution in minutes since it was last
 updated. It must be greater or equal to ``1``.

- **evaluation_interval**

 The evaluation interval defines how frequently Mistral will check and expire
 old executions. In the above example it is set to two hours, so every two
 hours Mistral will clean up and look for expired executions.
