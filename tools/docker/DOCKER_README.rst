Using Mistral with docker
=========================

In order to minimize the work needed to the current Mistral code, or be able
to spin up independent or networked Mistral instances in seconds, docker
containers are a very good option. This guide describes the process to
launch an all-in-one Mistral container.


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


Running Mistral
---------------

Start a RabbitMQ container::

  docker run -d --name rabbitmq rabbitmq

Start Mistral::

  docker run -d -p 8989:8989 --name mistral mistral-all

To execute commands inside the container::

  docker exec -it mistral bash

E.g. to list workflows, issue::

  mistral workflow-list


Running Mistral with MySQL
--------------------------

Other than the simplest use cases will very probably fail with various errors
due to the default Sqlight database. It is highly recommended that, for
example, MySQL is used as database backend.

The `start_mistral_rabbit_mysql.sh` script sets up a rabbitmq container, a
mysql container and a mistral container to work together.

Check out the script for more detail.
