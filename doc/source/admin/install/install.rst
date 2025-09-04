=====================
Install and configure
=====================

This section describes how to install and configure the
Workflow Service, code-named mistral, on the controller node.

.. note::

    Mistral can be used in standalone mode or it can work with OpenStack.

If Mistral is used with OpenStack, you must already have a working OpenStack
environment with at least the following components installed:

- Keystone with API v3 support

Note that installation and configuration may vary by distribution.

Overview
--------

The Workflow service consists of the following components:

``Mistral API`` service
  Provides a REST API for operating and monitoring workflow executions.

``Mistral Engine`` service
  Controls workflow executions and handles their data flow, places finished
  tasks in a queue, transfers data from task to task, and deals with condition
  transitions, and so on.

``Mistral Executor`` service
  Executes task actions, picks up the tasks from the queue, runs actions, and
  sends results back to the engine.

``Mistral Notifier`` service
  Send notifications based on state of workflow and task executions.
  `This service is optional`.

``Mistral Event Engine`` service
  Create workflow executions based on external events (like RabbitMQ, HTTP,
  kafka, etc.).
  `This service is optional`.

The mistral project is also providing the following python libraries:

``mistral-dashboard``
  Mistral Dashboard is a Horizon (OpenSack dashboard) plugin.

``python-mistralclient``
  Python client API and Command Line Interface.

``mistral-lib``
  A library used by mistral internals.

``mistral-extra``
  A collection of extra actions that could be installed to extend mistral
  standard actions with openstack ones (by default mistral is not having any
  OpenStack related action).

Prerequisites
-------------

Install the following dependencies:

On ``apt`` based distributions:

.. code-block:: console

    $ apt-get update
    $ apt-get install python3 python3-venv python3-pip git

On ``dnf`` based distributions:

.. code-block:: console

    $ dnf update
    $ dnf install python3 python3-venv python3-pip git

.. note::

    you may need to adapt the previous commands based on your distribution.

Installation
------------

.. note::

    For instructions on how to install Mistral using devstack, refer to
    :doc:`Mistral Devstack Installation <../../contributor/devstack>`

Clone the repo and go to the repo directory:

.. code-block:: console

    $ git clone https://opendev.org/openstack/mistral
    $ cd mistral

Create a venv:

.. code-block:: console

    $ python3 -m venv venv
    $ source venv/bin/activate

Now install mistral:

.. code-block:: console

    $ pip install \
      -c https://releases.openstack.org/constraints/upper/master \
      -r requirements.txt \
      .

.. note::

    You may need to adjust the constraints file based on the release
    of mistral you are installing

Generate the configuration file:

.. code-block:: console

    $ pip install tox
    $ tox -egenconfig

Create the mistral directory and copy the example configuration file:

.. code-block:: console

    $ mkdir /etc/mistral
    $ cp etc/mistral.conf.sample /etc/mistral/mistral.conf

Edit the configuration file:

.. code-block:: console

    $ vi /etc/mistral/mistral.conf

You may also want to install the `mistral-extra` package to have the
opentack actions available (but this is not mandatory):

.. code-block:: console

    $ pip install mistral-extra


Configuring Mistral
-------------------

Refer :doc:`../configuration/index` to find general information on how to
configure Mistral server.


Before The First Run
--------------------

After the installation, you will see the **mistral-server** and
**mistral-db-manage** commands in your virtual env.

The **mistral-db-manage** command can be used for database migrations.

Update the database to the latest revision:

.. code-block:: console

    # For MySQL / MariaDB / PostgreSQL
    $ mistral-db-manage upgrade head

    # For SQLite - do not use sqlite in production!
    # e.g. connection = 'sqlite:////var/lib/mistral.sqlite'
    $ python tools/sync_db.py

Before starting the Mistral server, run the *mistral-db-manage populate*
command. It creates the DB with all the standard actions and standard workflows
that Mistral provides to all Mistral users.:

.. code-block:: console

    $ mistral-db-manage populate

For more detailed information on the *mistral-db-manage* script, see
the :doc:`Mistral Upgrade Guide </admin/upgrade_guide>`.


Running Mistral server
----------------------

To run the Mistral components, execute the following command in a shell:

.. code-block:: console

    $ mistral-server --server all

.. note::

    in this situation API will start only one worker! If you need more than
    worker for you API, you should start the API with uWSGI (see below)

Running Mistral components separately
-------------------------------------

You can choose to split the Mistral component execution on more than one
server, e.g. to start only the engine:

.. code-block:: console

    $ mistral-server --server engine

The --server command line option can be a comma delimited list, so you can
build combination of components, like this:

.. code-block:: console

    $ mistral-server --server engine,executor

The valid options are:

* all (by default if not specified)
* api
* engine
* executor
* event-engine
* notifier

Running Mistral API with uWSGI
------------------------------

The WSGI application
~~~~~~~~~~~~~~~~~~~~

One downside of running ``mistral-server --server api`` directly is that it
will start only one process (worker) to handle HTTP requests.

While this may be enough for small/dev deployments, it may not for production.

In that situation, Mistral provides a WSGI application at
``mistral.wsgi:application`` that can be used with any WSGI server.

The below example uses uWSGI


Using uWSGI
~~~~~~~~~~~

Install uWSGI:

.. code-block:: console

    $ pip install uwsgi


Create a uWSGI configuration file (e.g., ``/etc/uwsgi/mistral.ini``):

.. code-block:: cfg

    [uwsgi]
    # Listen on port 8989 and start as a full web server
    http-socket = 0.0.0.0:8989

    # Stats on port 9191
    stats = 0.0.0.0:9191

    # App to start
    virtualenv = /opt/openstack/mistral/
    module = mistral.wsgi:application

    # load apps in each worker instead of the master
    lazy-apps = true

    # Number of processes
    processes = 4

    # Will kill processes that run more that 60s
    harakiri = 60

    # Enable threads
    enable-threads = true

    # Gracefully manage processes
    master = true

    # Thunder-lock - serialize accept() usage (if possible)
    thunder-lock = true


Start uWSGI:

.. code-block:: console

    $ uwsgi --ini /etc/uwsgi/mistral.ini


Passing Configuration Options
------------------------------

By default, Mistral will use its standard configuration file search paths:

* ``/etc/mistral/mistral.conf``
* ``/etc/mistral/mistral.conf.d/``
* ``/etc/mistral.conf.d/``
* many others, see:
  https://docs.openstack.org/oslo.config/latest/configuration/options.html

You can also provide ``config-dir`` or ``config-file`` options to
``mistral-server`` command line to provide a custom file/folder:

.. code-block:: console

    $ mistral-server --config-dir /etc/mycustomdir/

Note that, when using ``uwsgi``, you won't be able to provide such params. In
that situation, you can use ``MISTRAL_CONFIG_DIR`` and/or
``MISTRAL_CONFIG_FILE`` environment variable instead:

.. code-block:: cfg

    [uwsgi]
    ...
    env = MISTRAL_CONFIG_DIR=/etc/mycustomdir/

.. _install-osa:

Deploying with OpenStack-Ansible
--------------------------------
You can also deploy and set up Mistral using `OpenStack-Ansible <https://docs.openstack.org/openstack-ansible/latest/>`_ by following
the `Mistral role for OpenStack-Ansible <https://docs.openstack.org/openstack-ansible-os_mistral/latest/>`_
which installs and configures Mistral as part of your OpenStack deployment.
