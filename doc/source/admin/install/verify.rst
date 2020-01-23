.. _verify:

Basic verification
~~~~~~~~~~~~~~~~~~

.. code-block:: console

   $ mistral run-action std.noop


Verify operation of the Workflow service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. note::

   Perform these commands on the controller node.

#. Create a workflow file:

   .. code-block:: console

      $ cat >/tmp/test.wf.yaml <<EOL
        ---
        version: '2.0'

        test_wf:
          tasks:
            echo_task:
              action: std.echo output="Hello"
        EOL


#. Create a workflow from the workflow file:

   .. code-block:: console

      $ mistral workflow-create /tmp/test.wf.yaml

#. Create an execution based on the workflow:

   .. code-block:: console

     $ mistral execution-create test_wf

#. Run the execution until its returning state is 'SUCCESS':

   .. code-block:: console

      $   mistral execution-list

After performing the above steps, the Mistral service is ready for use.
