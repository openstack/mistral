Mistral
=======

Workflow Service for OpenStack cloud.


Prerequisites
-------------

It is necessary to install some specific system libs for installing Mistral. They can be installed on most popular operating system using their package manager (for Ubuntu - *apt*, for Fedora, CentOS - *yum*, for Mac OS - *brew* or *macports*).
The list of needed packages is shown below:

1. **python-dev**
2. **python-setuptools**
3. **python-pip**
4. **libffi-dev**
5. **libxslt1-dev (or libxslt-dev)**
6. **libxml2-dev**
7. **libyaml-dev**
8. **libssl-dev**

**Mistral can be used without authentication at all or it can works with OpenStack**
*In case of OpenStack, it works **only on Keystone v3**, make sure Keystone v3 is installed.*

Installation
------------

First of all, clone the repo and go to the repo directory:

    git clone https://github.com/stackforge/mistral.git
    cd mistral


**Devstack installation**

Information about how to install Mistral with devstack can be found here: https://github.com/stackforge/mistral/tree/master/contrib/devstack

**Virtualenv installation**

    tox

This will install necessary virtual environments and run all the project tests. Installing virtual environments may take significant time (~10-15 mins).

**Local installation**

    pip install -e .

  or

    python setup.py install

===================
Configuring Mistral
===================

Mistral configuration is needed for getting it work correctly either with real OpenStack environment or without OpenStack environment.

1. Copy mistral.conf:

    cp etc/mistral.conf.sample etc/mistral.conf

    *Note: mistral.conf.sample is the example configuration file.*

2. Edit file *etc/mistral.conf*
3. **If you are not using OpenStack, skip this item.** Provide valid keystone auth properties:

    [keystone_authtoken]

    auth_uri = http://<Keystone-host>:5000/v3

    identity_uri = http://<Keystone-host:35357/

    auth_version = v3

    admin_user = <user>

    admin_password = <password>

    admin_tenant_name = <tenant>

4. **If you don't use OpenStack**, provide *auth_enable = False* in config file:

    [pecan]

    auth_enable = False

Before the first run
--------------------

Before starting Mistral server, run sync_db script. It prepares the DB, creates in it all standard actions and standard workflows which Mistral provides for all mistral users.

  **If you use virtualenv:**

    tools/sync_db.sh --config-file path_to_config*

  **Or run sync_db directly:**

    python tools/sync_db.py --config-file path_to_config*

  *Note: After local installation you will see **mistral-server** command in your environment*.


Running Mistral API server
--------------------------

To run Mistral API server perform the following command in a shell:

    tox -evenv -- python mistral/cmd/launch.py --server api --config-file path_to_config*

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

Mistral client
--------------

Python-mistralclient is available here - https://github.com/stackforge/python-mistralclient


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

There is an ability to run part of functional tests in non-openstack mode locally. To do this:

    1. set *auth_enable=false* in the mistral.conf and restart Mistral
    2. execute: *./run_functional_tests.sh*

To run tests for only one version need to specify it: bash run_functional_tests.sh v1

More information about automated tests for Mistral can be found here: https://wiki.openstack.org/wiki/Mistral/Testing