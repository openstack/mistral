Using Mistral with Docker
=========================

In order to minimize the work needed to run the current Mistral code, or
be able to spin up independent or networked Mistral instances in seconds,
Docker containers are a very good option. This guide describes the process
to launch an all-in-one Mistral container.


Docker installation
-------------------

The links help you to install latest Docker software:

* `Docker Engine <https://docs.docker.com/engine/installation/>`_
* `Docker Compose <https://docs.docker.com/compose/install/>`_


Build the Mistral image manually
--------------------------------

The `build.sh` script takes care of creating the `mistral-all` image locally.
On the other hand you could execute the following command::

  docker build -t mistral -f tools/docker/Dockerfile .

The Mistral Docker image has set of build parameters. **Pay attention**, the
compile of 'V8EVAL'  can take a long time.

+-------------------------+-------------+--------------------------------------+
|Name                     |Default value| Description                          |
+=========================+=============+======================================+
|`BUILD_V8EVAL`           |true         |If the `BUILD_V8EVAL` equals `true`,  |
|                         |             |the `v8eval` library will be build for|
|                         |             |std.javascript action. `Read more <ht |
|                         |             |tps://docs.openstack.org/mistral/lates|
|                         |             |t/user/dsl_v2.html#std-javascript>`_  |
+-------------------------+-------------+----------------------+---------------+
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

The infrastructure docker-compose file contains a example of RabbitMQ,
PostgreSQL and MySQL. Fill free to modify docker-compose files.

Also the docker-compose contains the Clould-flow container.
It is available by `link <http://localhost:8000/>`_

If you want to rebuild image you should add `--build` option, for example::

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
|`DATABASE_URL`      |sqlite://mistral.\|The database URL                      |
|                    |db                |                                      |
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

Other way you can mount the your config file to a Mistral Docker container.
You should uncomment the volume sections in the docker-compose files.


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

The script also configures the containers so that the Mistral API will be
accessible from the host machine on the default port 8989. So it is also
possible to install the `mistral-pythonclient` to the host machine and
execute commands there.

