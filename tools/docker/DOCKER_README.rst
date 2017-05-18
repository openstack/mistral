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

  docker run -d  --link rabbitmq:rabbitmq -p 8989:8989 --name mistral mistral-all

To execute commands inside the container::

  docker exec -it mistral bash

E.g. to list workflows, issue::

  mistral workflow-list


Running Mistral From A Volume
-----------------------------

A scenario you may find useful for development is to clone a Mistral git repo
and link it into the container via a volume. This will allow you to make changes
to the Mistral source on your local machine and execute them immediately in the
container.

The following example illustrates launching the container from the local
directory of a git repo clone of Mistral.::

  docker run -d --link rabbitmq:rabbitmq -v $(pwd):/opt/stack/mistral:Z -p 8989:8989 --name mistral mistral-all

You might want to mount an additional drive to move files easily between your
development computer and the container.  An easy way to do this is to mount an
additional volume that maps to /home/mistral/ in the container.

Since the directory is already being used to store the mistral.conf and
mistral.sqlite files, you will want to copy these to the local directory you
intend to use for the mount. This example assumes the directory to mount is
"/tmp/mistral".  You should change this to the actual directory you intend to
use.::

  docker cp mistral:/home/mistral/mistral.conf /tmp/mistral/mistral.conf
  docker cp mistral:/home/mistral/mistral.sqlite /tmp/mistral/mistral.sqlite

  docker run -d --link rabbitmq:rabbitmq -v $(pwd):/opt/stack/mistral:Z -v /tmp/mistral:/home/mistral:Z -p 8989:8989 --name mistral mistral-all


Running Mistral with MySQL
--------------------------

Other than the simplest use cases will very probably fail with various errors
due to the default Sqlite database. It is highly recommended that, for
example, MySQL is used as database backend.

The `start_mistral_rabbit_mysql.sh` script sets up a rabbitmq container, a
mysql container and a mistral container to work together.

Check out the script for more detail.
