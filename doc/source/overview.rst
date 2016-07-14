Mistral Overview
================

What is Mistral?
----------------

Mistral is a workflow service. Most business processes consist of multiple
distinct interconnected steps that need to be executed in a particular order
in a distributed environment. A user can describe such a process as a set of
tasks and their transitions. After that it is possible to upload such a
description to Mistral, which will take care of state management, correct
execution order, parallelism, synchronization and high availability. Mistral
also provides flexible task scheduling so that it can run a process according
to a specified schedule (for example, every Sunday at 4.00pm) instead of
running it immediately. In Mistral terminology such a set of tasks and
relations between them is called a **workflow**.

Main use cases
--------------

Task Scheduling - Cloud Cron
^^^^^^^^^^^^^^^^^^^^^^^^^^^^
A user can use Mistral to schedule tasks to run within a cloud. Tasks can be
anything from executing local processes (shell scripts, binaries) on specified
virtual instances to calling REST APIs accessible in a cloud environment. They
can also be tasks related to cloud management like creating or terminating
virtual instances. It is important that several tasks can be combined in a
single workflow and run in a scheduled manner (for example, on Sundays at 2.00
am). Mistral will take care of their parallel execution (if it's logically
possible) and fault tolerance, and will provide workflow execution
management/monitoring capabilities (stop, resume, current status, errors and
other statistics).

Cloud Environment Deployment
^^^^^^^^^^^^^^^^^^^^^^^^^^^^
A user or a framework can use Mistral to specify workflows needed for
deploying environments consisting of multiple VMs and applications.

Long-running business process
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
A user makes a request to run a complex multi-step business process and
wants it to be fault-tolerant so that if the execution crashes at some point
on one node then another active node of the system can automatically take on
and continue from the exact same point where it stopped. In this use case the
user splits the business process into a set of tasks and lets Mistral handle
them, in the sense that it serves as a coordinator and decides what particular
task should be started at what time. So that Mistral calls back with "Execute
action X, here is the data". If an application that executes action X dies
then another instance takes the responsibility to continue the work.

Big Data analysis & reporting
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
A data analyst can use Mistral as a tool for data crawling. For example,
in order to prepare a financial report the whole set of steps for gathering
and processing required report data can be represented as a graph of related
Mistral tasks. As with other cases, Mistral makes sure to supply fault
tolerance, high availability and scalability.

Live migration
^^^^^^^^^^^^^^
A user specifies tasks for VM live migration triggered upon an event from
Ceilometer (CPU consumption 100%).

Rationale
---------

The main idea behind the Mistral service includes the following main points:

- Ability to upload custom workflow definitions.

- The actual task execution may not be performed by the service itself.
  The service can rather serve as a coordinator for other worker processes
  that do the actual work, and notify back about task execution results.
  In other words, task execution may be asynchronous, thus providing
  flexibility for plugging in any domain specific handling and opportunities
  to make this service scalable and highly available.

- The service provides a notion of **task action**, which is a pluggable piece
  of logic that a workflow task is associated with. Out of the box, the service
  provides a set of standard actions for user convenience. However, the user
  can create custom actions based on the standard action pack.
