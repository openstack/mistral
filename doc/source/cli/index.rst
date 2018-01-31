Mistral Client Commands Guide
=============================

The Mistral CLI can be used with ``mistral`` command or via `OpenStackClient
<https://docs.openstack.org/python-openstackclient/latest/>`_.

Mistral Client
--------------

The best way to learn about all the commands and arguments that are expected
is to use the ``mistral help`` command.

.. code-block:: bash

    $ mistral help
    usage: mistral [--version] [-v] [--log-file LOG_FILE] [-q] [-h] [--debug]
                   [--os-mistral-url MISTRAL_URL]
                   [--os-mistral-version MISTRAL_VERSION]
                   [--os-mistral-service-type SERVICE_TYPE]
    ...

It can also be used with the name of a sub-command.

.. code-block:: bash

    $ mistral help execution-create
    usage: mistral execution-create [-h] [-f {json,shell,table,value,yaml}]
                                    [-c COLUMN] [--max-width <integer>]
                                    [--print-empty] [--noindent] [--prefix PREFIX]
                                    [-d DESCRIPTION]
                                    workflow_identifier [workflow_input] [params]

    Create new execution.

    positional arguments:
      workflow_identifier   Workflow ID or name. Workflow name will be deprecated
                            since Mitaka.
    ...


OpenStack Client
----------------

OpenStack client works in a similar way, the command ``openstack help`` shows
all the available commands and then ``openstack help <sub-command>`` will show
the detailed usage.

The full list of Mistral commands that are registered with OpenStack client
can be listed with ``openstack command list``. By default it will list all
commands grouped together, but we can specify only the Mistral command group.

.. code-block:: bash

    $ openstack command list --group openstack.workflow_engine.v2
    +------------------------------+-----------------------------------+
    | Command Group                | Commands                          |
    +------------------------------+-----------------------------------+
    | openstack.workflow_engine.v2 | action definition create          |
    |                              | action definition definition show |
    |                              | action definition delete          |
    |                              | action definition list            |
    |                              | action definition show            |
    |                              | action definition update          |
    |                              | action execution delete           |
    ...

Then detailed help output can be requested for an individual command.

.. code-block:: bash

    $ openstack help workflow execution create
    usage: openstack workflow execution create [-h]
                                               [-f {json,shell,table,value,yaml}]
                                               [-c COLUMN] [--max-width <integer>]
                                               [--print-empty] [--noindent]
                                               [--prefix PREFIX] [-d DESCRIPTION]
                                               workflow_identifier
                                               [workflow_input] [params]

    Create new execution.

    positional arguments:
      workflow_identifier   Workflow ID or name. Workflow name will be deprecated
                            since Mitaka.
      workflow_input        Workflow input
      params                Workflow additional parameters

