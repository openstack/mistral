Mistral Client / CLI Guide
==========================

Mistralclient installation
--------------------------

To install ``python-mistralclient``, it is required to have ``pip`` (in most cases). Make sure that ``pip`` is installed. Then type::

    pip install python-mistralclient

Or, if it is needed to install ``python-mistralclient`` from master branch, type::

    pip install git+https://github.com/openstack/python-mistralclient.git

After ``python-mistralclient`` is installed you will see command ``mistral`` in your environment.

Configure authentication against Keystone
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If Keystone is used for authentication in Mistral, then the environment should have auth variables::

    export OS_AUTH_URL=http://<Keystone_host>:5000/v2.0
    export OS_USERNAME=admin
    export OS_TENANT_NAME=tenant
    export OS_PASSWORD=secret
    export OS_MISTRAL_URL=http://<Mistral host>:8989/v2  (optional, by default URL=http://localhost:8989/v2)

and in the case when you are authenticating against keystone over https::

    export OS_CACERT=<path_to_ca_cert>

.. note:: In client, we can use both Keystone auth versions - v2.0 and v3. But server supports only v3.

You can see the list of available commands by typing::

    mistral --help

To make sure Mistral client works, type::

    mistral workbook-list

Mistralclient commands
----------------------

Workbooks
^^^^^^^^^

TBD

Workflows
^^^^^^^^^

TBD

Actions
^^^^^^^

TBD

Workflow executions
^^^^^^^^^^^^^^^^^^^

TBD

Task executions
^^^^^^^^^^^^^^^

TBD

Action executions
^^^^^^^^^^^^^^^^^

TBD

Cron-triggers
^^^^^^^^^^^^^

TBD

Environments
^^^^^^^^^^^^

TBD
