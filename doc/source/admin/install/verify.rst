.. _verify:

Basic verification
~~~~~~~~~~~~~~~~~~

.. code-block:: console

   $ mistral run-action std.echo '{"output": "Hello world"}'

Should give you something like:

.. code-block:: console

   {"result": "Hello world"}

Congrats!

A step further - your first workflow
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

#. Create a workflow file:

.. code-block:: console

    $ cat >/tmp/test.wf.yaml <<EOL
    ---
    version: '2.0'
    test_wf:
      input:
        - message: "Hello world"
      output:
        output: <% $.output %>
      tasks:
        echo_task:
          action: std.echo output=<% $.message %>
          publish:
            output: <% task().result %>
    EOL


#. Create a workflow from the workflow file:

.. code-block:: console

    $ mistral workflow-create /tmp/test.wf.yaml

#. Create an execution based on the workflow:

.. code-block:: console

    $ mistral execution-create test_wf

#. Run the execution until its returning state is 'SUCCESS':

.. code-block:: console

    $ mistral execution-list

#. You can grab the output of the execution using:

.. code-block:: console

    $ mistral execution-get-output <execution_id>

After performing the above steps, the Mistral service is ready for use.
