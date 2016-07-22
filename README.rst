Mistral
=======

Workflow Service for OpenStack cloud.

Installation
~~~~~~~~~~~~

Prerequisites
-------------

It is necessary to install some specific system libs for installing Mistral.
They can be installed on most popular operating systems using their package
manager (for Ubuntu - *apt*, for Fedora, CentOS - *yum*, for Mac OS - *brew*
or *macports*).

The list of needed packages is shown below:

* **python-dev**
* **python-setuptools**
* **python-pip**
* **libffi-dev**
* **libxslt1-dev (or libxslt-dev)**
* **libxml2-dev**
* **libyaml-dev**
* **libssl-dev**

In case of ubuntu, just run::

 apt-get install python-dev python-setuptools libffi-dev \
   libxslt1-dev libxml2-dev libyaml-dev libssl-dev

**Mistral can be used without authentication at all or it can work with
OpenStack.**

In case of OpenStack, it works **only with Keystone v3**, make sure **Keystone
v3** is installed.


Install Mistral
---------------

First of all, clone the repo and go to the repo directory::

  $ git clone https://git.openstack.org/openstack/mistral.git
  $ cd mistral


**Devstack installation**

Information about how to install Mistral with devstack can be found
`here <https://git.openstack.org/openstack/mistral/tree/master/devstack>`_.

**Virtualenv installation**::

  $ tox

This will install necessary virtual environments and run all the project tests.
Installing virtual environments may take significant time (~10-15 mins).

**Local installation**::

  $ pip install -e .

or::

  $ pip install -r requirements.txt
  $ python setup.py install


Configuring Mistral
~~~~~~~~~~~~~~~~~~~

Mistral configuration is needed for getting it work correctly with and without
an OpenStack environment.

#. Install and configure a database which can be *MySQL* or *PostgreSQL*
   (**SQLite can't be used in production.**). Here are the steps to connect
   Mistral to a *MySQL* database.

   * Make sure you have installed ``mysql-server`` package on your Mistral
     machine.
   * Install *MySQL driver* for python::

     $ pip install mysql-python

     or, if you work in virtualenv, run::

     $ tox -evenv -- pip install mysql-python

     NOTE: If you're using Python 3 then you need to install ``mysqlclient``
     instead of ``mysql-python``.

   * Create the database and grant privileges::

     $ mysql -u root -p
       CREATE DATABASE mistral;
       USE mistral
       GRANT ALL ON mistral.* TO 'root'@'localhost';

#. Generate ``mistral.conf`` file::

    $ oslo-config-generator \
      --config-file tools/config/config-generator.mistral.conf \
      --output-file etc/mistral.conf

#. Edit file ``etc/mistral.conf`` according to your setup. Pay attention to
   the following sections and options::

    [oslo_messaging_rabbit]
    rabbit_host = <RABBIT_HOST>
    rabbit_userid = <RABBIT_USERID>
    rabbit_password = <RABBIT_PASSWORD>

    [database]
    # Use the following line if *PostgreSQL* is used
    # connection = postgresql://<DB_USER>:<DB_PASSWORD>@localhost:5432/mistral
    connection = mysql://<DB_USER>:<DB_PASSWORD>@localhost:3306/mistral

#. If you are not using OpenStack, add the following entry to the
   ``/etc/mistral.conf`` file and **skip the following steps**::

    [pecan]
    auth_enable = False

#. Provide valid keystone auth properties::

    [keystone_authtoken]
    auth_uri = http://<Keystone-host>:5000/v3
    identity_uri = http://<Keystone-host:35357/
    auth_version = v3
    admin_user = <user>
    admin_password = <password>
    admin_tenant_name = <tenant>

#. Register Mistral service and Mistral endpoints on Keystone::

    $ MISTRAL_URL="http://[host]:[port]/v2"
    $ openstack service create --name mistral workflowv2
    $ openstack endpoint create \
        --publicurl $MISTRAL_URL \
        --adminurl $MISTRAL_URL \
        --internalurl $MISTRAL_URL \
        mistral

#. Update the ``mistral/actions/openstack/mapping.json`` file which contains
   all available OpenStack actions, according to the specific client versions
   of OpenStack projects in your deployment. Please find more detailed
   information in the ``tools/get_action_list.py`` script.


Before the First Run
~~~~~~~~~~~~~~~~~~~~

After local installation you will find the commands ``mistral-server`` and
``mistral-db-manage`` available in your environment. The ``mistral-db-manage``
command can be used for migrating database schema versions. If Mistral is not
installed in system then this script can be found at
``mistral/db/sqlalchemy/migration/cli.py``, it can be executed using Python
command line.

To update the database schema to the latest revision, type::

  $ mistral-db-manage --config-file <path_to_config> upgrade head

For more detailed information about ``mistral-db-manage`` script please check
file ``mistral/db/sqlalchemy/migration/alembic_migrations/README.md``.

** NOTE: For users want a dry run with SQLite backend(not used in production),
``mistral-db-manage`` is not recommended for database initialization due to
`SQLite limitations <http://www.sqlite.org/omitted.html>`_. Please use
``sync_db`` script described below instead for database initialization.

Before starting Mistral server, run ``sync_db`` script. It prepares the DB,
creates in it with all standard actions and standard workflows which Mistral
provides for all mistral users.

If you are using virtualenv::

  $ tools/sync_db.sh --config-file <path_to_config>

Or run ``sync_db`` directly::

  $ python tools/sync_db.py --config-file <path_to_config>


Running Mistral API server
~~~~~~~~~~~~~~~~~~~~~~~~~~

To run Mistral API server::

  $ tox -evenv -- python mistral/cmd/launch.py \
      --server api --config-file <path_to_config>

Running Mistral Engines
~~~~~~~~~~~~~~~~~~~~~~~

To run Mistral Engine::

  $ tox -evenv -- python mistral/cmd/launch.py \
      --server engine --config-file <path_to_config>

Running Mistral Task Executors
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To run Mistral Task Executor instance::

  $ tox -evenv -- python mistral/cmd/launch.py \
      --server executor --config-file <path_to_config>

Note that at least one Engine instance and one Executor instance should be
running in order for workflow tasks to be processed by Mistral.

If you want to run some tasks on specific executor, the *task affinity* feature
can be used to send these tasks directly to a specific executor. You can edit
the following property in your mistral configuration file for this purpose::

    [executor]
    host = my_favorite_executor

After changing this option, you will need to start (restart) the executor. Use
the ``target`` property of a task to specify the executor::

    ... Workflow YAML ...
    task1:
      ...
      target: my_favorite_executor
    ... Workflow YAML ...

Running Multiple Mistral Servers Under the Same Process
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To run more than one server (API, Engine, or Task Executor) on the same
process::

  $ tox -evenv -- python mistral/cmd/launch.py \
      --server api,engine --config-file <path_to_config>

The value for the ``--server`` option can be a comma-delimited list. The valid
options are ``all`` (which is the default if not specified) or any combination
of ``api``, ``engine``, and ``executor``.

It's important to note that the ``fake`` transport for the ``rpc_backend``
defined in the configuration file should only be used if ``all`` Mistral
servers are launched on the same process. Otherwise, messages do not get
delivered because the ``fake`` transport is using an in-process queue.


Mistral Client
~~~~~~~~~~~~~~

The Mistral command line tool is provided by the ``python-mistralclient``
package which is available
`here <https://git.openstack.org/openstack/python-mistralclient>`__.


Debugging
~~~~~~~~~

To debug using a local engine and executor without dependencies such as
RabbitMQ, make sure your ``etc/mistral.conf`` has the following settings::

  [DEFAULT]
  rpc_backend = fake

  [pecan]
  auth_enable = False

and run the following command in *pdb*, *PyDev* or *PyCharm*::

  mistral/cmd/launch.py --server all --config-file etc/mistral.conf --use-debugger

Running examples
~~~~~~~~~~~~~~~~

To run the examples find them in mistral-extra repository
(https://github.com/openstack/mistral-extra) and follow the instructions on
each example.


Tests
~~~~~

You can run some of the functional tests in non-openstack mode locally. To do
this:

#. set ``auth_enable = False`` in the ``mistral.conf`` and restart Mistral
#. execute::

    $ ./run_functional_tests.sh

To run tests for only one version need to specify it::

  $ bash run_functional_tests.sh v1

More information about automated tests for Mistral can be found on
`Mistral Wiki <https://wiki.openstack.org/wiki/Mistral/Testing>`_.
