Mistral Installation Guide
==========================

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

In case of Ubuntu, just run::

    apt-get install python-dev python-setuptools python-pip libffi-dev libxslt1-dev libxml2-dev libyaml-dev libssl-dev

**NOTE:** **Mistral can be used without authentication at all or it can work with OpenStack.** In case of OpenStack, it works **only on Keystone v3**, make sure **Keystone v3** is installed.

Installation
------------

**NOTE**: If it is needed to install Mistral using devstack, please refer to :doc:`Mistral Devstack Installation </developer/devstack>`

First of all, clone the repo and go to the repo directory::

    git clone https://github.com/openstack/mistral.git
    cd mistral

Generate config::

    tox -egenconfig

Configure Mistral as needed. The configuration file is located in ``etc/mistral.conf``. For details see :doc:`Mistral Configuration Guide </guides/configuration_guide>`

**Virtualenv installation**::

    tox

This will install necessary virtual environments and run all the project tests. Installing virtual environments may take significant time (~10-15 mins).

**Local installation**::

    pip install -e .

or::

    pip install -r requirements.txt
    python setup.py install

**NOTE**: Differences *pip install -e* and *setup.py install*. **pip install -e** works very similarly to **setup.py install** or the EasyInstall tool, except that it doesn’t actually install anything. Instead, it creates a special .egg-link file in the deployment directory, that links to your project’s source code.

Before the first run
--------------------

After installation you will see **mistral-server** and **mistral-db-manage** commands in your environment, either in system or virtual environment.

**NOTE**: In case of using **virtualenv**, all Mistral related commands available via **tox -evenv --**. For example, *mistral-server* is available via *tox -evenv -- mistral-server*.

**mistral-db-manage** command can be used for migrations.

For updating the database to the latest revision type::

    mistral-db-manage --config-file <path-to-mistral.conf> upgrade head

Before starting Mistral server, run *mistral-db-manage populate* command. It prepares the DB, creates in it with all standard actions and standard workflows which Mistral provides for all Mistral users.
::

    mistral-db-manage --config-file <path-to-mistral.conf> populate

For more detailed information about *mistral-db-manage* script please see :doc:`Mistral Upgrade Guide </guides/upgrade_guide>`.

**NOTE**: For users who want a dry run with **SQLite** database backend(not used in production), *mistral-db-manage* is not recommended for database initialization because of `SQLite limitations <http://www.sqlite.org/omitted.html>`_. Please use sync_db script described below instead for database initialization.

**If you use virtualenv**::

    tools/sync_db.sh --config-file <path-to-mistral.conf>

**Or run sync_db directly**::

    python tools/sync_db.py --config-file <path-to-mistral.conf>

Running Mistral API server
--------------------------

To run Mistral API server perform the following command in a shell::

    mistral-server --server api --config-file <path-to-mistral.conf>

Running Mistral Engines
-----------------------

To run Mistral Engine perform the following command in a shell::

    mistral-server --server engine --config-file <path-to-mistral.conf>

Running Mistral Task Executors
------------------------------
To run Mistral Task Executor instance perform the following command in a shell::

    mistral-server --server executor --config-file <path-to-mistral.conf>

Note that at least one Engine instance and one Executor instance should be running so that workflow tasks are processed by Mistral.

Running Multiple Mistral Servers Under the Same Process
-------------------------------------------------------
To run more than one server (API, Engine, or Task Executor) on the same process, perform the following command in a shell::

    mistral-server --server api,engine --config-file <path-to-mistral.conf>

The --server command line option can be a comma delimited list. The valid options are "all" (by default if not specified) or any combination of "api", "engine", and "executor". It's important to note that the "fake" transport for the rpc_backend defined in the config file should only be used if "all" the Mistral servers are launched on the same process. Otherwise, messages do not get delivered if the Mistral servers are launched on different processes because the "fake" transport is using an in process queue.

Mistral And Docker
------------------
Please first refer `installation steps for docker <https://docs.docker.com/installation/>`_.
To build the image from the mistral source, change directory to the root directory of the Mistral git repository and run::

    docker build -t <Name of image> .

In case you want pre-built image, you can download it from `openstack tarballs source <https://tarballs.openstack.org/mistral/images/mistral-docker.tar.gz>`_.

To load this image to docker registry, please run following command::

    docker load -i '<path of mistral-docker.tar.gz>'

The Mistral Docker image is configured to store the database in the user's home directory. For persistence of these data, you may want to keep this directory outside of the container. This may be done by the following steps::

    sudo mkdir '<user-defined-directory>'
    docker run -it -v '<user-defined-directory>':/home/mistral <Name of image>

More about docker: https://www.docker.com/

**NOTE:** This docker image uses **SQLite** database. So, it cannot be used for production environment. If you want to use this for production environment, then put customized mistral.conf to '<user-defined-directory>'.

Mistral Client Installation
---------------------------

Please refer to :doc:`Mistral Client / CLI Guide </guides/mistralclient_guide>`
