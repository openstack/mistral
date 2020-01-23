==========================
Frequently Asked Questions
==========================

What is Mistral?
----------------

Mistral is a task management service. It can also be called Workflow Service.
Most business processes consist of multiple distinct interconnected
steps that need to be executed in a particular order. One can describe such
process as a set of tasks and task relations and upload such description to
Mistral so that it takes care of state management, correct execution order,
task distribution and high availability. Mistral also provides flexible task
scheduling so that we can run a process according to a specified schedule
(i.e. every Sunday at 4.00pm) instead of running it immediately. We call such
set of tasks and dependencies between them a workflow. Independent routes are
called flows and Mistral can execute them in parallel.

Who are Mistral users?
----------------------

Potential Mistral users are: Developers. Both who work on OpenStack services
and those running in tenant’s VMs. Developers use Mistral DSL/API to access
it. System integrators. They customize workflows related with deployment
using either special scripts or manually using Mistral CLI/UI. System
administrators can use Mistral via additional toolset for common
administrative tasks. This can be distributed cron, mass deployment tasks,
backups etc.

How does Mistral relate to OpenStack?
-------------------------------------

Mistral was original started within the OpenStack community. It is still
used within a number of OpenStack projects for various purposes. Mistral
has integration with OpenStack: authentication/authorization with Keystone
identity service and actions to interact with all major OpenStack services
like Nova, Neutron, Heat etc.

Why offload business processes to a 3rd party service?
------------------------------------------------------

* *Reason 1*: **High Availability**. A typical application’s workflow consists
  of many independent tasks like collecting data, processing, resource
  acquiring, obtaining user input, reporting, sending notifications,
  replicating data etc. All of the steps must happen in appropriate time as
  they depend on each other. Many such processes can run in parallel. Now if
  your application crashes somewhere in the middle or a power outage occurs
  your business process terminates at unknown stage in an unknown state. So
  you need to track a state of every single flow in some external persistent
  storage like database so that you can resume it (or roll it back) from the
  place it crashed. You also need some health monitoring tool that would watch
  your app and if it crashed schedule unfinished flows on another instance.
  This is exactly what Mistral can do out of the box without reinventing the
  wheel for each application time and time again.
* *Reason 2*: **Scalability**. Most workflows have steps that can be performed
  in parallel (i.e. different routes in a workflow). Mistral can distribute
  execution of such tasks across your application’s instances so that the
  whole execution would scale.
* *Reason 3*: **Observable state**. Because flow state is tracked outside
  of application it becomes observable. At any given moment system
  administrator can access information on what is currently going on, what
  tasks are in pending state and what has already been executed. You can
  obtain metrics on your business processes and profile them.
* *Reason 4*: **Scheduling**. Using Mistral you can schedule your process
  to be run periodically or at a fixed moment in future. You can have your
  execution to be triggered on alarm condition from an external health
  monitoring system or upon a new email in your mailbox.
* *Reason 5*: **Dependency management offloading**. Because you offload task
  management to an external service you don’t have to specify all the
  triggers and actions in advance. For example, you may say “here is the
  task that must be triggered if my domain is down for 1 minute” without
  specifying how exactly the event is obtained. System administrator can
  setup Nagios to watch your domain and trigger the action and replace it
  later with Ceilometer without your application being affected or even
  aware of the change. Administrator can even manually trigger the task
  using CLI or UI console. Or another example is having a task that triggers
  each time a flow reaches some desired state and let administrator configure
  what exactly needs to happen there (like send a notification mail and later
  replace it with SMS).
* *Reason 6*: **Open additional points for integration**. As soon as your
  business process is converted to a Mistral workflow that can be accessed
  by others, other application can setup their own workflow to be triggered
  by your application reaching a certain state. For example suppose
  OpenStack Nova would declare a workflow for new VM instance spawning.
  One application (or system administrator) can hook to a task “finish”
  so that every time Nova spawns another instance you would receive
  a notification. Or suppose you want your users to have flexible quotas
  on how many instances one can spawn based on information in external
  billing system. Normally you would have to patch Nova to access your
  billing system but with Mistral you can just alter Nova’s workflow so
  that it includes your custom tasks that would do it instead.
* *Reason 7*:
  **Formalized graphs of tasks are just easier to manage and understand**.
  They can be visualized, analyzed and optimized. They simplify program
  development and debugging. You can model program workflows, replace task
  actions with stubs, easily mock external dependencies, do task profiling.

Why not use Celery or something similar?
----------------------------------------

While Celery is a distributed task engine it was designed to execute custom
Python code on pre-installed private workers. Again, this is a different use
case from Mistral, which assumes that tasks can be executed on a shared
service and they do not require (or allow) custom code uploaded in advance.
In other words, Celery itself could be implemented on top of Mistral, if it
was started now.

How does Mistral relate to Amazon SWF?
--------------------------------------

Amazon SWF shares many ideas with Mistral but, in fact, is designed to be
language-oriented (Java, Ruby, Python). It is hard and mostly meaningless
to use SWF without its, for example, Java SDK that exposes its functionality
as a set of Java annotations and interfaces. In this sense SWF is closer to
Celery than to Mistral. Mistral on the other hand aims to be both simpler
and more user-friendly. We want to have a service that is usable without
an SDK in any programming language. At the same time it’s always possible
to implement additional convenient language-oriented bindings based on cool
features like Python decorators, Java annotations and aspects.

How do I make Mistral know about my workflows?
----------------------------------------------

Workflows are described using the Mistral Workflow Language based on YAML.
There is a REST API that is used to upload workflows, execute them and make
run-time modifications against them. The Workflow Language describes

* Workflows
* Tasks
* Transitions between tasks (what should run next once a task completed).
  Applicable for "direct" workflow type.
* Dependencies between tasks (what tasks need to be run before this task
  can be executed). Applicable for "reverse" workflow type.
* Various policies applied to how tasks should run. For example, "retry"
  policies helps with running a task multiple times in case of failures.
* Ad-hoc actions that can be used for to transform input or output of other
  actions for convenience.

What are Mistral tasks?
-----------------------

Tasks are entities written with the Mistral Workflow Language that define
certain workflow steps. Each task has:

* Name
* Optional tag names
* List of tasks it depends on for reverse workflows or list of transitions
  for direct workflows
* Optional YAQL expression that extracts data from current data context so
  that it would go as a task execution input
* Optional task action (concrete work to do)
* Optional task workflow. If specified, such task is associated with another
  workflow execution (subworkflow).

What are Mistral Workflows?
---------------------------

A set of tasks and rules according to which these tasks run. Each workflow
is designed to solve a certain domain problem like auto-scaling a web
application.

What are Mistral Workbooks?
---------------------------

Workbook is a convenience bag to carry multiple workflows and ad-hoc actions
within a single file. Workbooks can also be used like namespaces.

What are Mistral actions and how does Mistral execute them?
-----------------------------------------------------------

Action is what to do when a particular task runs. Examples are:

* Run a shell script
* Send an email
* Call your app’s URI. Send an AMQP (RabbitMQ) message to some queue.
* Other types of signaling (email, UDP message, polling etc.).

Mistral can be extended to include other general purpose actions like
calling Puppet, Chef, Ansible etc. etc.

Is it possible to organize a data flow between different tasks in Mistral?
--------------------------------------------------------------------------

Yes, tasks belonging to the same workflow can take some input as a json
structure, query a subset of this structure interesting for this particular
task using YAQL expression (https://pypi.python.org/pypi/yaql) and pass it
along to a corresponding action. Once the action has done its processing it
returns the result back using similar json format. So in this case Mistral
acts as a data flow hub dispatching results of one tasks to inputs of other
tasks.

Does Mistral provide a mechanism to run nested workflows?
---------------------------------------------------------

Instead of performing a concrete action associated with a task Mistral can
start a nested workflow. That is, given the input that came to the task,
Mistral starts a new workflow with that input and after completion execution
jumps back to the parent workflow and continues from the same point. The
closest analogy in programming would be calling one method from another
passing all required parameters and optionally getting back a result. It’s
worth noting that the nested workflow works in parallel with the rest of the
activities belonging to the parent execution and it has its own isolated
execution context observable via API.
