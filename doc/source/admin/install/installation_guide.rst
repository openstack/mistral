==========================
Mistral Installation Guide
==========================

Prerequisites
-------------

It is necessary to install some specific system libs for installing Mistral.
They can be installed on most popular operating system using their package
manager (for Ubuntu - *apt*, for Fedora - *dnf*, CentOS - *yum*, for Mac OS -
*brew* or *macports*).
The list of needed packages is shown below:

1. **python-dev**
2. **python-setuptools**
3. **python-pip**
4. **libffi-dev**
5. **libxslt1-dev (or libxslt-dev)**
6. **libxml2-dev**
7. **libyaml-dev**
8. **libssl-dev**

In case of Ubuntu, just run::

    $ apt-get install python-dev python-setuptools python-pip libffi-dev \
      libxslt1-dev libxml2-dev libyaml-dev libssl-dev

**NOTE:** **Mistral can be used without authentication at all or it can work
with OpenStack.** In case of OpenStack, it works **only on Keystone v3**, make
sure **Keystone v3** is installed.

Installation
------------

**NOTE**: If it is needed to install Mistral using devstack, please refer to
:doc:`Mistral Devstack Installation <../../contributor/devstack>`

First of all, clone the repo and go to the repo directory::

    $ git clone https://github.com/openstack/mistral.git
    $ cd mistral

Install tox::

    $ pip install tox

Generate config::

    $ tox -egenconfig

Configure Mistral as needed. The configuration file is located in
``etc/mistral.conf.sample``. You will need to modify the configuration options
and then copy it into ``/etc/mistral/mistral.conf``.
For details see :doc:`Mistral Configuration Guide </admin/configuration/index>`

**Virtualenv installation**::

    $ tox

This will install necessary virtual environments and run all the project tests.
Installing virtual environments may take significant time (~10-15 mins).

**Local installation**::

    $ pip install -e .

or::

    $ pip install -r requirements.txt
    $ python setup.py install

**NOTE**: Differences *pip install -e* and *setup.py install*.
**pip install -e** works very similarly to **setup.py install** or the
EasyInstall tool, except that it doesn't actually install anything.
Instead, it creates a special .egg-link file in the deployment directory,
that links to your project's source code.

Before the first run
--------------------

After installation you will see **mistral-server** and **mistral-db-manage**
commands in your environment, either in system or virtual environment.

**NOTE**: In case of using **virtualenv**, all Mistral related commands
available via **tox -evenv --**. For example, *mistral-server* is available via
*tox -evenv -- mistral-server*.

**mistral-db-manage** command can be used for migrations.

For updating the database to the latest revision type::

    $ mistral-db-manage --config-file <path-to-mistral.conf> upgrade head

Before starting Mistral server, run *mistral-db-manage populate* command.
It prepares the database with standard actions and workflows which Mistral
will provide for all users.::

    $ mistral-db-manage --config-file <path-to-mistral.conf> populate

For more detailed information about *mistral-db-manage* script please
see :doc:`Mistral Upgrade Guide </admin/upgrade_guide>`.

**NOTE**: For users who want a dry run with **SQLite** database backend(not
used in production), *mistral-db-manage* is not recommended for database
initialization because of
`SQLite limitations <http://www.sqlite.org/omitted.html>`_.
Please use sync_db script described below instead for database initialization.

**If you use virtualenv**::

    $ tools/sync_db.sh --config-file <path-to-mistral.conf>

**Or run sync_db directly**::

    $ python tools/sync_db.py --config-file <path-to-mistral.conf>

Running Mistral API server
--------------------------

To run Mistral API server perform the following command in a shell::

    $ mistral-server --server api --config-file <path-to-mistral.conf>

Running Mistral Engines
-----------------------

To run Mistral Engine perform the following command in a shell::

    $ mistral-server --server engine --config-file <path-to-mistral.conf>

Running Mistral Task Executors
------------------------------
To run Mistral Task Executor instance perform the following command
in a shell::

    $ mistral-server --server executor --config-file <path-to-mistral.conf>

Running Mistral Notifier
------------------------
To run Mistral Notifier perform the following command in a shell::

    $ mistral-server --server notifier -- config-file <path-to-mistral.conf>

Note that at least one Engine instance and one Executor instance should be
running so that workflow tasks are processed by Mistral.

Running Multiple Mistral Servers Under the Same Process
-------------------------------------------------------
To run more than one server (API, Engine, or Task Executor) on the same
process, perform the following command in a shell::

    $ mistral-server --server api,engine --config-file <path-to-mistral.conf>

The --server command line option can be a comma delimited list. The valid
options are "all" (by default if not specified) or any combination of "api",
"engine", "notifier" and "executor". It's important to note
that the "fake" transport for
the rpc_backend defined in the config file should only be used if "all" the
Mistral servers are launched on the same process. Otherwise, messages do not
get delivered if the Mistral servers are launched on different processes
because the "fake" transport is using an in process queue.

Running Mistral By Systemd
--------------------------
#. Create an upstart config, it could be named as
   ``/etc/systemd/system/mistral-api.service``:

   .. code-block:: bash

      [Unit]
      Description = Openstack Workflow Service API

      [Service]
      ExecStart = /usr/bin/mistral-server --server api --config-file /etc/mistral/mistral.conf
      User = mistral

      [Install]
      WantedBy = multi-user.target

#. Enable and start mistral-api:

   .. code-block:: console

      # systemctl enable mistral-api
      # systemctl start mistral-api

#. Verify that mistral-api services are running:

   .. code-block:: console

      # systemctl status mistral-api

#. Create an upstart config, it could be named as
   ``/etc/systemd/system/mistral-engine.service``:

   .. code-block:: bash

      [Unit]
      Description = Openstack Workflow Service Engine

      [Service]
      ExecStart = /usr/bin/mistral-server --server engine --config-file /etc/mistral/mistral.conf
      User = mistral

      [Install]
      WantedBy = multi-user.target

#. Enable and start mistral-engine:

   .. code-block:: console

      # systemctl enable mistral-engine
      # systemctl start mistral-engine

#. Verify that mistral-engine services are running:

   .. code-block:: console

      # systemctl status mistral-engine

#. Create an upstart config, it could be named as
   ``/etc/systemd/system/mistral-notifier.service``:

   .. code-block:: bash

      [Unit]
      Description = Openstack Workflow Service Notifier

      [Service]
      ExecStart = /usr/bin/mistral-server --server notifier --config-file /etc/mistral/mistral.conf
      User = mistral

      [Install]
      WantedBy = multi-user.target

#. Enable and start mistral-notifier:

   .. code-block:: console

      # systemctl enable mistral-notifier
      # systemctl start mistral-notifier

#. Verify that mistral-notifier services are running:

   .. code-block:: console

      # systemctl status mistral-notifier

#. Create an upstart config, it could be named as
   ``/etc/systemd/system/mistral-executor.service``:

   .. code-block:: bash

      [Unit]
      Description = Openstack Workflow Service Executor

      [Service]
      ExecStart = /usr/bin/mistral-server --server executor --config-file /etc/mistral/mistral.conf
      User = mistral

      [Install]
      WantedBy = multi-user.target

#. Enable and start mistral-executor:

   .. code-block:: console

      # systemctl enable mistral-executor
      # systemctl start mistral-executor

#. Verify that mistral-executor services are running:

   .. code-block:: console

      # systemctl status mistral-executor


Mistral And Docker
------------------

Docker containers provide an easy way to quickly deploy independent or
networked Mistral instances in seconds. This guide describes the process
to launch an all-in-one Mistral container.


Docker Installation
-------------------

The following links contain instructions to install latest Docker software:

* `Docker Engine <https://docs.docker.com/engine/installation/>`_
* `Docker Compose <https://docs.docker.com/compose/install/>`_


Build the Mistral Image Manually
--------------------------------

Execute the following command from the repository top-level directory::

  docker build -t mistral -f tools/docker/Dockerfile .

The Mistral Docker image has one build parameter:

+-------------------------+-------------+--------------------------------------+
|Name                     |Default value| Description                          |
+=========================+=============+======================================+
|`BUILD_TEST_DEPENDENCIES`|false        |If the `BUILD_TEST_DEPENDENCIES`      |
|                         |             |equals `true`, the Mistral test       |
|                         |             |dependencies will be installed inside |
|                         |             |the Docker image                      |
+-------------------------+-------------+----------------------+---------------+


Running Mistral using Docker Compose
------------------------------------

To launch Mistral in the single node configuration::

  docker-compose -f tools/docker/docker-compose/infrastructure.yaml \
               -f tools/docker/docker-compose/mistral-single-node.yaml \
               -p mistral up -d

To launch Mistral in the multi node configuration::

  docker-compose -f tools/docker/docker-compose/infrastructure.yaml \
               -f tools/docker/docker-compose/mistral-multi-node.yaml \
               -p mistral up -d

The infrastructure docker-compose file contains examples of RabbitMQ,
PostgreSQL and MySQL configurations. Feel free to modify the docker-compose
files as needed.

The docker-compose Mistral configurations also include the CloudFlow container.
It is available at `link <http://localhost:8000/>`_

The `--build` option can be used when it is necessary to rebuild the image,
for example::

  docker-compose -f tools/docker/docker-compose/infrastructure.yaml \
               -f tools/docker/docker-compose/mistral-single-node.yaml \
               -p mistral up -d --build

Running the Mistral client from the Docker Compose container
------------------------------------------------------------

To run the mistral client against the server in the container using the client
present in the container::

  docker run -it mistral_mistral mistral workflow-list

Configuring Mistral
-------------------

The Docker image contains the minimal set of Mistral configuration parameters
by default:

+--------------------+------------------+--------------------------------------+
|Name                |Default value     | Description                          |
+====================+==================+======================================+
|`MESSAGE_BROKER_URL`|rabbit://guest:gu\|The message broker URL                |
|                    |est@rabbitmq:5672 |                                      |
+--------------------+------------------+----------------------+---------------+
|`DATABASE_URL`      |sqlite:///mistral\|The database URL                      |
|                    |.db               |                                      |
+--------------------+------------------+----------------------+---------------+
|`UPGRADE_DB`        |false             |If the `UPGRADE_DB` equals `true`,    |
|                    |                  |a database upgrade will be launched   |
|                    |                  |before Mistral main process           |
+--------------------+------------------+----------------------+---------------+
|`MISTRAL_SERVER`    |all               |Specifies which mistral server to     |
|                    |                  |start by the launch script.           |
+--------------------+------------------+----------------------+---------------+
|`LOG_DEBUG`         |false             |If set to true, the logging level will|
|                    |                  |be set to DEBUG instead of the default|
|                    |                  |INFO level.                           |
+--------------------+------------------+----------------------+---------------+
|`RUN_TESTS`         |false             |If the `UPGRADE_DB` equals `true`,    |
|                    |                  |the Mistral unit tests will be        |
|                    |                  |launched inside container             |
+--------------------+------------------+----------------------+---------------+

The `/etc/mistral/mistral.conf` configuration file can be mounted to the Mistral
Docker container by uncommenting and editing the `volumes` sections in the
Mistral docker-compose files.


Launch tests inside Container
-----------------------------

Build mistral::

  docker build -t mistral -f tools/docker/Dockerfile \
        --build-arg BUILD_TEST_DEPENDENCIES=true .

Run tests using SQLite::

  docker run -it -e RUN_TESTS=true mistral

or PostgreSQL::

  docker run -it \
    -e DATABASE_URL=postgresql://postgres:postgres@localhost:5432/postgres \
    -e RUN_TESTS=true mistral


Keycloak integration
--------------------

If you set AUTH_ENABLE to True value in the mistral.env file then Mistral will
enable Keycloak integration by default. Keycloak will be deployed with
mistral/mistral credentials. You should uncomment the volume line in the
`infrastructure.yaml` for the CloudFlow.

Next step you login in the administrative console using the
http://localhost:8080/auth/admin URL. Create a oauth client, you can
specify only a name, for example mistral.

Specify valid redirect URL: http://localhost:8000/* and turn on the
"Implicit Flow Enabled" in the your client page. Save your changes.

Add the following line to your /etc/hosts file::

  127.0.0.1   keycloak

Export the following environments variable for mistral cli::

  export MISTRAL_AUTH_TYPE=keycloak-oidc
  export OS_AUTH_URL=http://keycloak:8080/auth
  export OS_TENANT_NAME=master
  export OS_USERNAME=mistral
  export OS_PASSWORD=mistral
  export OS_MISTRAL_URL=http://localhost:8989/v2
  export OPENID_CLIENT_ID=mistral
  export OPENID_CLIENT_SECRET=
  export MISTRALCLIENT_INSECURE=True

Check your configuration::

  mistral workflow-list

Or open a cloud flow page in a browser::

  http://localhost:8000


Using Mistral Client with Docker
--------------------------------

The Mistral API will be accessible from the host machine on the default
port 8989. Install `python-mistralclient` on the host machine to
execute mistral commands.

Mistral Client Installation
---------------------------

Please refer to :doc:`Mistral Client / CLI Guide </user/cli/index>`
