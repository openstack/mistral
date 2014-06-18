Mistral
=======

Task Orchestration and Scheduling service for OpenStack cloud


Installation
------------

First of all, in a shell run:

    tox

This will install necessary virtual environments and run all the project tests. Installing virtual environments may take significant time (~10-15 mins).

Running Mistral API server
--------------------------

To run Mistral API server perform the following command in a shell:

    tox -evenv -- python mistral/cmd/launch.py --server api --config-file path_to_config*

Note that an example configuration file can be found in etc/mistral.conf.sample.

Running Mistral Engines
-----------------------

To run Mistral Engine perform the following command in a shell:

    tox -evenv -- python mistral/cmd/launch.py --server engine --config-file path_to_config*

Running Mistral Task Executors
------------------------------
To run Mistral Task Executor instance perform the following command in a shell:

    tox -evenv -- python mistral/cmd/launch.py --server executor --config-file path_to_config

Note that at least one Engine instance and one Executor instance should be running so that workflow tasks are processed by Mistral.

Running Multiple Mistral Servers Under the Same Process
-------------------------------------------------------
To run more than one server (API, Engine, or Task Executor) on the same process, perform the following command in a shell:

    tox -evenv -- python mistral/cmd/launch.py --server api,engine --config-file path_to_config

The --server command line option can be a comma delimited list. The valid options are "all" (by default if not specified) or any combination of "api", "engine", and "executor". It's important to note that the "fake" transport for the rpc_backend defined in the config file should only be used if "all" the Mistral servers are launched on the same process. Otherwise, messages do not get delivered if the Mistral servers are launched on different processes because the "fake" transport is using an in process queue.

Debugging
---------

To debug using a local engine and executor without dependencies such as RabbitMQ, create etc/mistral.conf with the following settings::

    [DEFAULT]
    rpc_backend = fake

    [pecan]
    auth_enable = False

and run in pdb, PyDev or PyCharm::

    mistral/cmd/launch.py --server all --config-file etc/mistral.conf --use-debugger

Running examples
----------------

To run the examples find them in mistral-extra repository (https://github.com/stackforge/mistral-extra) and follow the instructions on each example.

Tests
-----

Information about automated tests for Mistral can be found here: https://wiki.openstack.org/wiki/Mistral/Testing
