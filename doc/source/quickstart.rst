Quick Start
===========

Prerequisites
-------------

Before you start following this guide, make sure you have completed these
three prerequisites.

Install and run Mistral
~~~~~~~~~~~~~~~~~~~~~~~

Go through the installation manual:
:doc:`Mistral Installation Guide <install/index>`

Install Mistral client
~~~~~~~~~~~~~~~~~~~~~~

To install mistralclient, please refer to
:doc:`Mistral Client / CLI Guide <cli/index>`

Export Keystone credentials
~~~~~~~~~~~~~~~~~~~~~~~~~~~

To use the OpenStack command line tools you should specify environment
variables with the configuration details for your OpenStack installation. The
following example assumes that the Identity service is at ``127.0.0.1:5000``,
with a user ``admin`` in the ``admin`` tenant whose password is ``password``:

.. code-block:: bash

    $ export OS_AUTH_URL=http://127.0.0.1:5000/v2.0/
    $ export OS_TENANT_NAME=admin
    $ export OS_USERNAME=admin
    $ export OS_PASSWORD=password

Write a workflow
----------------

For example, we have the following workflow.

.. code-block:: mistral

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

This simple workflow iterates through a list of names in ``task1`` (using
`with-items`), stores them as a task result (using the `std.echo` action) and
then stores the word "Done" as a result of the second task (`task2`).

To learn more about the Mistral Workflows and what you can do, read the
:doc:`Mistral Workflow Language specification <user/wf_lang_v2>`

Upload the workflow
-------------------

Use the *Mistral CLI* to create the workflow::

    $ mistral workflow-create <workflow.yaml>

The output should look similar to this::

    +------------------------------------+-------------+--------+---------+---------------------+------------+
    |ID                                  | Name        | Tags   | Input   | Created at          | Updated at |
    +------------------------------------+-------------+--------+---------+---------------------+------------+
    |9b719d62-2ced-47d3-b500-73261bb0b2ad| my_workflow | <none> | names   | 2015-08-13 08:44:49 | None       |
    +------------------------------------+-------------+--------+---------+---------------------+------------+


Run the workflow and check the result
-------------------------------------

Use the *Mistral CLI* to start the new workflow, passing in a list of names
as JSON::

    $ mistral execution-create my_workflow '{"names": ["John", "Mistral", "Ivan", "Crystal"]}'

Make sure the output is like the following::

    +-------------------+--------------------------------------+
    | Field             | Value                                |
    +-------------------+--------------------------------------+
    | ID                | 49213eb5-196c-421f-b436-775849b55040 |
    | Workflow ID       | 9b719d62-2ced-47d3-b500-73261bb0b2ad |
    | Workflow name     | my_workflow                          |
    | Description       |                                      |
    | Task Execution ID | <none>                               |
    | State             | RUNNING                              |
    | State info        | None                                 |
    | Created at        | 2017-03-06 11:24:10                  |
    | Updated at        | 2017-03-06 11:24:10                  |
    +-------------------+--------------------------------------+

After a moment, check the status of the workflow execution (replace the
example execution id with the ID output above)::

    $ mistral execution-get 49213eb5-196c-421f-b436-775849b55040

    +-------------------+--------------------------------------+
    | Field             | Value                                |
    +-------------------+--------------------------------------+
    | ID                | 49213eb5-196c-421f-b436-775849b55040 |
    | Workflow ID       | 9b719d62-2ced-47d3-b500-73261bb0b2ad |
    | Workflow name     | my_workflow                          |
    | Description       |                                      |
    | Task Execution ID | <none>                               |
    | State             | SUCCESS                              |
    | State info        | None                                 |
    | Created at        | 2017-03-06 11:24:10                  |
    | Updated at        | 2017-03-06 11:24:20                  |
    +-------------------+--------------------------------------+

The status of each **task** also can be checked::

    $ mistral task-list 49213eb5-196c-421f-b436-775849b55040

    +--------------------------------------+-------+---------------+--------------------------------------+---------+------------+---------------------+---------------------+
    | ID                                   | Name  | Workflow name | Execution ID                         | State   | State info | Created at          | Updated at          |
    +--------------------------------------+-------+---------------+--------------------------------------+---------+------------+---------------------+---------------------+
    | f639e7a9-9609-468e-aa08-7650e1472efe | task1 | my_workflow   | 49213eb5-196c-421f-b436-775849b55040 | SUCCESS | None       | 2017-03-06 11:24:11 | 2017-03-06 11:24:17 |
    | d565c5a0-f46f-4ebe-8655-9eb6796307a3 | task2 | my_workflow   | 49213eb5-196c-421f-b436-775849b55040 | SUCCESS | None       | 2017-03-06 11:24:17 | 2017-03-06 11:24:18 |
    +--------------------------------------+-------+---------------+--------------------------------------+---------+------------+---------------------+---------------------+

Check the result of task *'task1'*::

    $ mistral task-get-result f639e7a9-9609-468e-aa08-7650e1472efe

    [
        "John",
        "Mistral",
        "Ivan",
        "Crystal"
    ]

If needed, we can go deeper and look at a list of the results of the
**action_executions** of a single task::

    $ mistral action-execution-list f639e7a9-9609-468e-aa08-7650e1472efe

    +--------------------------------------+----------+---------------+-----------+--------------------------------------+---------+----------+---------------------+---------------------+
    | ID                                   | Name     | Workflow name | Task name | Task ID                              | State   | Accepted | Created at          | Updated at          |
    +--------------------------------------+----------+---------------+-----------+--------------------------------------+---------+----------+---------------------+---------------------+
    | 4e0a60be-04df-42d7-aa59-5107e599d079 | std.echo | my_workflow   | task1     | f639e7a9-9609-468e-aa08-7650e1472efe | SUCCESS | True     | 2017-03-06 11:24:12 | 2017-03-06 11:24:16 |
    | 5bd95da4-9b29-4a79-bcb1-298abd659bd6 | std.echo | my_workflow   | task1     | f639e7a9-9609-468e-aa08-7650e1472efe | SUCCESS | True     | 2017-03-06 11:24:12 | 2017-03-06 11:24:16 |
    | 6ae6c19e-b51b-4910-9e0e-96c788093715 | std.echo | my_workflow   | task1     | f639e7a9-9609-468e-aa08-7650e1472efe | SUCCESS | True     | 2017-03-06 11:24:12 | 2017-03-06 11:24:16 |
    | bed5a6a2-c1d8-460f-a2a5-b36f72f85e19 | std.echo | my_workflow   | task1     | f639e7a9-9609-468e-aa08-7650e1472efe | SUCCESS | True     | 2017-03-06 11:24:12 | 2017-03-06 11:24:17 |
    +--------------------------------------+----------+---------------+-----------+--------------------------------------+---------+----------+---------------------+---------------------+

Check the result of the first **action_execution**::

    $ mistral action-execution-get-output 4e0a60be-04df-42d7-aa59-5107e599d079

    {
        "result": "John"
    }

**Congratulations! Now you are ready to use OpenStack Workflow Service!**
