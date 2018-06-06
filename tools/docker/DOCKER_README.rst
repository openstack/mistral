Using Mistral with Docker
=========================

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
Docker container by uncommenting and editing the `volumes` sections in the Mistral
docker-compose files.


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


Using Mistral Client
--------------------

The Mistral API will be accessible from the host machine on the default
port 8989. Install `python-mistralclient` on the host machine to
execute mistral commands.

