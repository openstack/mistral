Using Mistral with docker
=========================

In order to minimize the work needed to run the current Mistral code, or
be able to spin up independent or networked Mistral instances in seconds,
Docker containers are a very good option. This guide describes the process
to launch an all-in-one Mistral container.


Docker installation
-------------------

In order to install the latest docker engine, run::

  curl -fsSL https://get.docker.com/ | sh

If you are behind a proxy, additional configuration may be needed to be
able to execute further steps in the setup process. For detailed information
on this process, check out `the official guide at
<http://www.sqlite.org/omitted.html>`_.


Build the Mistral image
-----------------------

The `build.sh` script takes care of creating the `mistral-all` image locally.
This is image is configured to use  RabbitMQ for transport and MySQL as database
backend. It is possible to run Mistral with Sqlite as database backend but
it is very unreliable, thus, MySQL was selected as the default database backend
for this image.


Running Mistral with MySQL
--------------------------

The `start_mistral_rabbit_mysql.sh` script sets up a rabbitmq container, a
mysql container and a mistral container to work together.

The script can be invoked with::

  start_mistral_rabbit_mysql.sh [single|multi]

`single` mode (this is the default) will create

 - rabbitmq container,
 - the mysql container,
 - and the mistral container that runs all Mistral services.


`multi` mode will create

 - rabbitmq,
 - mysql,
 - mistral-api,
 - one mistral-engine,
 - two mistral-executors

Check out the script for more detail and examples for different setup options.

Using Mistral
-------------

Depending on the mode, you may need to use the `mistral` or the `mistral-api`
container.

With the `multi` option execute commands inside the container::

  docker exec -it mistral-api bash

E.g. to list workflows, issue::

  mistral workflow-list

The script also configures the containers so that the Mistral API will be
accessible from the host machine on the default port 8989. So it is also
possible to install the `mistral-pythonclient` to the host machine and
execute commands there.

Configuring Mistral
-------------------

The Mistral configuration is stored in the Docker image. The changes to the
configuration should be synchronized between all deployed containers to
ensure consistent behavior. This can be achieved by mounting the configuration
as a volume::

  export EXTRA_OPTS='-v <path to local mistral.conf>:/etc/mistral/mistral.conf:ro'
  start_mistral_rabbit_mysql.sh multi

