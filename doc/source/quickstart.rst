Quick Start
===========

Install and Run Mistral
-----------------------

* Go through the installation manual: :doc:`Mistral Installation Guide </guides/installation_guide>`

Install Mistral Client
----------------------

* For installing mistralclient, please refer to :doc:`Mistral Client / CLI Guide </guides/mistralclient_guide>`

Export Keystone Credentials
---------------------------

To use the OpenStack command line tools you should specify environment variables with the configuration details for your OpenStack installation. The following example assumes that the Identity service is at ``127.0.0.1:5000``, with a user ``admin`` in the ``admin`` tenant whose password is ``password``::

    $ export OS_AUTH_URL=http://127.0.0.1:5000/v2.0/
    $ export OS_TENANT_NAME=admin
    $ export OS_USERNAME=admin
    $ export OS_PASSWORD=password

Write Workflow
--------------

For example, we have the following workflow::

    ---
    version: "2.0"

    my_workflow:
      type: direct

      input:
        - names

      tasks:
        task1:
          with-items: name in <% $.names %>
          action: std.echo output=<% $.name %>
          on-success: task2

        task2:
          action: std.echo output="Done"

This simple workflow iterates through the given list of names in its first task (using "with-items"), stores
them as a task result (using echo action) and then stores the word "Done" as a result of the second task.

Create Workflow Object
----------------------

Use *Mistral CLI* to create the workflow::

    mistral workflow-create <workflow.yaml>

Make sure that output is like the following::

    +-------------+--------+---------+---------------------+------------+
    | Name        | Tags   | Input   | Created at          | Updated at |
    +-------------+--------+---------+---------------------+------------+
    | my_workflow | <none> | names   | 2015-08-13 08:44:49 | None       |
    +-------------+--------+---------+---------------------+------------+


Run Workflow and Check the Result
---------------------------------

Use *Mistral CLI* to run the newly-created workflow. Pass the variable **names** as **workflow_input**::

    mistral execution-create my_workflow '{"names": ["John", "Mistral", "Ivan", "Crystal"]}'

Make sure the output is like the following::

    +-------------+--------------------------------------+
    | Field       | Value                                |
    +-------------+--------------------------------------+
    | ID          | 056c2ed1-695f-4ccd-92af-e31bc6153784 |
    | Workflow    | my_workflow                          |
    | Description |                                      |
    | State       | RUNNING                              |
    | State info  | None                                 |
    | Created at  | 2015-08-28 09:05:00.065917           |
    | Updated at  | 2015-08-28 09:05:00.844990           |
    +-------------+--------------------------------------+

After a while, check the status of the workflow execution (replace the example execution id with the real one)::

    mistral execution-get 056c2ed1-695f-4ccd-92af-e31bc6153784

    +-------------+--------------------------------------+
    | Field       | Value                                |
    +-------------+--------------------------------------+
    | ID          | 056c2ed1-695f-4ccd-92af-e31bc6153784 |
    | Workflow    | my_workflow                          |
    | Description |                                      |
    | State       | SUCCESS                              |
    | State info  | None                                 |
    | Created at  | 2015-08-28 09:05:00                  |
    | Updated at  | 2015-08-28 09:05:03                  |
    +-------------+--------------------------------------+

The status of each **task** also can be checked::

    mistral task-list 056c2ed1-695f-4ccd-92af-e31bc6153784

    +--------------------------------------+-------+---------------+--------------------------------------+---------+
    | ID                                   | Name  | Workflow name | Execution ID                         | State   |
    +--------------------------------------+-------+---------------+--------------------------------------+---------+
    | 91874635-dcd4-4718-a864-ac90408c1085 | task1 | my_workflow   | 056c2ed1-695f-4ccd-92af-e31bc6153784 | SUCCESS |
    | 3bf82863-28cb-4148-bfb8-1a6c3c115022 | task2 | my_workflow   | 056c2ed1-695f-4ccd-92af-e31bc6153784 | SUCCESS |
    +--------------------------------------+-------+---------------+--------------------------------------+---------+

Check the result of task *'task1'*::

    mistral task-get-result 91874635-dcd4-4718-a864-ac90408c1085

    [
        "John",
        "Mistral",
        "Ivan",
        "Crystal"
    ]

If needed, we can go deeper and look at a list of the results of the **action_executions** of a single task::

    mistral action-execution-list 91874635-dcd4-4718-a864-ac90408c1085

    +--------------------------------------+----------+---------------+-----------+---------+------------+-------------+
    | ID                                   | Name     | Workflow name | Task name | State   | State info | Is accepted |
    +--------------------------------------+----------+---------------+-----------+---------+------------+-------------+
    | 20c2b65d-b899-437f-8e1b-50fe477fbf4b | std.echo | my_workflow   | task1     | SUCCESS | None       | True        |
    | 6773c887-6eff-46e6-bed9-d6b67d77813b | std.echo | my_workflow   | task1     | SUCCESS | None       | True        |
    | 753a9e39-d93e-4751-a3c1-569d1b4eac64 | std.echo | my_workflow   | task1     | SUCCESS | None       | True        |
    | 9872ddbc-61c5-4511-aa7e-dc4016607822 | std.echo | my_workflow   | task1     | SUCCESS | None       | True        |
    +--------------------------------------+----------+---------------+-----------+---------+------------+-------------+

Check the result of the first **action_execution**::

    mistral action-execution-get-output 20c2b65d-b899-437f-8e1b-50fe477fbf4b

    {
        "result": "John"
    }

**Congratulations! Now you are ready to use OpenStack Workflow Service!**
