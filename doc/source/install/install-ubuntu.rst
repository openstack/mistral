.. _install-ubuntu:

Install and configure for Ubuntu
================================

This section describes how to install and configure the Workflow Service
service for Ubuntu.



Prerequisites
-------------

#. Install the packages:

   .. code-block:: console

      # apt-get update

      # apt-get install python-setuptools python-pip libffi-dev libxslt1-dev \
        libxml2-dev libyaml-dev libssl-dev python3-dev tox mistral-common



Installation
------------

**NOTE**: For instructions on how to install Mistral using devstack, refer to
:doc:`Mistral Devstack Installation </contributor/devstack>`

Clone the repo and go to the repo directory:

.. code-block:: console

    $ git clone https://git.openstack.org/openstack/mistral
    $ cd mistral

Generate the configuration file:

.. code-block:: console

    $ tox -egenconfig

Create the mistral directory and copy the example configuration file:

.. code-block:: console

    $ mkdir /etc/mistral
    $ cp etc/mistral.conf.sample /etc/mistral/mistral.conf


Edit the configuration file:

 .. code-block:: console

    $ vi /etc/mistral/mistral.conf



**Virtualenv installation**:

.. code-block:: console

    $ tox

This installs the necessary virtual environments and runs all the project
tests. Installing the virtual environments may take significant time (~10-15
mins).

**Local installation**:

.. code-block:: console

    $ pip install -e .

or:

.. code-block:: console

    $ pip install -r requirements.txt
    $ python setup.py install

**NOTE**: There are some differences between *pip install -e* and *setup.py
install*. **pip install -e** works similarly to **setup.py install**
or the EasyInstall tool, however, it does not actually install anything.
Instead, it creates a special .egg-link file in the deployment directory that
links to your project’s source code.


.. include:: ../configuration/index.rst


Before the first run
--------------------

After the installation, you will see the **mistral-server** and
**mistral-db-manage** commands in your environment, either in system or virtual
environment.

**NOTE**: If you use **virtualenv**, all Mistral-related commands can be
accessed with **tox -evenv --**. For example, *mistral-server* is available via
*tox -evenv -- mistral-server*.

The **mistral-db-manage** command can be used for migrations.

Updating the database to the latest revision type:

.. code-block:: console

    $ mistral-db-manage --config-file <path-to-mistral.conf> upgrade head

Before starting the Mistral server, run the *mistral-db-manage populate*
command. It creates the DB with all the standard actions and standard workflows
that Mistral provides to all Mistral users.:

.. code-block:: console

    $ mistral-db-manage --config-file <path-to-mistral.conf> populate

For more detailed information on the *mistral-db-manage* script, see
the :doc:`Mistral Upgrade Guide </admin/upgrade_guide>`.

**NOTE**: For users who want a dry run with an **SQLite** database backend (not
used in production), the *mistral-db-manage* script is not recommended for
database initialization because of
`SQLite limitations <http://www.sqlite.org/omitted.html>`_.
Use the sync_db script described below for database
initialization instead.

**If you use virtualenv**:

.. code-block:: console

    $ tools/sync_db.sh --config-file <path-to-mistral.conf>

**Or run sync_db directly**:

.. code-block:: console

    $ python tools/sync_db.py --config-file <path-to-mistral.conf>

Running Mistral API server
--------------------------

To run the Mistral API server, execute the following command in a shell:

.. code-block:: console

    $ mistral-server --server api --config-file <path-to-mistral.conf>

Running Mistral Engines
-----------------------

To run the Mistral Engine, execute the following command in a shell:

.. code-block:: console

    $ mistral-server --server engine --config-file <path-to-mistral.conf>

Running Mistral Executors
-------------------------
To run the Mistral Executor instance, execute the following command in a
shell:

.. code-block:: console

    $ mistral-server --server executor --config-file <path-to-mistral.conf>

Note that at least one Engine instance and one Executor instance should be
running so that workflow tasks are processed by Mistral.

Mistral Notifier
----------------

To run the Mistral Notifier, execute the following command in a shell:

.. code-block:: console

    $ mistral-server --server notifier --config-file <path-to-mistral.conf>

Running Multiple Mistral Servers Under the Same Process
-------------------------------------------------------
To run more than one server (API, Engine, or Task Executor) on the same process,
execute the following command in a shell:

.. code-block:: console

    $ mistral-server --server api,engine --config-file <path-to-mistral.conf>

The --server command line option can be a comma delimited list. The valid
options are "all" (by default if not specified) or any combination of "api",
"engine", and "executor". It is important to note that the "fake" transport for
the rpc_backend defined in the config file should only be used if "all" the
Mistral servers are launched on the same process. Otherwise, messages do not
get delivered if the Mistral servers are launched on different processes
because the "fake" transport is using an in-process queue.


.. include:: mistralclient_guide.rst


Finalize installation
---------------------

Restart the Workflow services:

.. code-block:: console

   # service openstack-mistral-api restart
