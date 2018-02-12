Mistral Configuration Guide
===========================

Mistral configuration is needed for getting it work correctly
either with real OpenStack environment or without OpenStack environment.

**NOTE:** The most of the following operations should performed in mistral
directory.

#. Generate *mistral.conf* (if it does not already exist)::

    $ oslo-config-generator \
      --config-file tools/config/config-generator.mistral.conf \
      --output-file /etc/mistral/mistral.conf

#. Edit file **/etc/mistral/mistral.conf**.

#. **If you are not using OpenStack, skip this item.** Provide valid keystone
   auth properties::

    [keystone_authtoken]
    auth_uri = http://<Keystone-host>:5000/v3
    identity_uri = http://<Keystone-host:35357
    auth_version = v3
    admin_user = <user>
    admin_password = <password>
    admin_tenant_name = <tenant>

#. Mistral can be also configured to authenticate with Keycloak server
   via OpenID Connect protocol. In order to enable Keycloak authentication
   the following section should be in the config file::

    auth_type = keycloak-oidc

    [keycloak_oidc]
    auth_url = https://<Keycloak-server-host>:<Keycloak-server-port>/auth

   Property 'auth_type' is assigned to 'keystone' by default.
   If SSL/TLS verification needs to be disabled then 'insecure = True'
   should also be added under [keycloak_oidc] group.

#. If you want to configure SSL for Mistral API server, provide following
   options in config file::

    [api]
    enable_ssl_api = True

    [ssl]
    ca_file = <path-to-ca file>
    cert_file = <path-to-certificate file>
    key_file = <path-to-key file>

#. **If you don't use OpenStack or you want to disable authentication for the
   Mistral service**, provide ``auth_enable = False`` in the config file::

    [pecan]
    auth_enable = False

#. **If you are not using OpenStack, skip this item**. Register Mistral service
   and Mistral endpoints on Keystone::

    $ MISTRAL_URL="http://[host]:[port]/v2"
    $ openstack service create workflowv2 --name mistral \
      --description 'OpenStack Workflow service'
    $ openstack endpoint create workflowv2 public $MISTRAL_URL
    $ openstack endpoint create workflowv2 internal $MISTRAL_URL
    $ openstack endpoint create workflowv2 admin $MISTRAL_URL

#. Configure transport properties in the [DEFAULT] section::

    [DEFAULT]
    transport_url = rabbit://<user_id>:<password>@<host>:5672/

#. Configure database. **SQLite can't be used in production**. Use *MySQL* or
   *PostgreSQL* instead. Here are the steps how to connect *MySQL* DB to
   Mistral:

   Make sure you have installed **mysql-server** package on your database
   machine (it can be your Mistral machine as well).

   Install MySQL driver for python::

    $ pip install mysql-python

   Create the database and grant privileges::

    $ mysql -u root -p

    CREATE DATABASE mistral;
    USE mistral
    GRANT ALL ON mistral.* TO 'root'@<database-host> IDENTIFIED BY <password>;

   Configure connection in Mistral config::

    [database]
    connection = mysql+pymysql://<user>:<password>@<database-host>:3306/mistral

   **NOTE**: If PostgreSQL is used, configure connection item as below::

    connection = postgresql://<user>:<password>@<database-host>:5432/mistral

#. **If you are not using OpenStack, skip this item.**
   Update mistral/actions/openstack/mapping.json file which contains all
   allowed OpenStack actions, according to the specific client versions
   of OpenStack projects in your deployment. Please find more detailed
   information in tools/get_action_list.py script.

#. Configure Task affinity feature if needed. It is needed for distinguishing
   either single task executor or one task executor from group of task
   executors::

    [executor]
    host = my_favorite_executor

   Then, this executor can be referred in Workflow Language by

   .. code-block:: yaml

    ...Workflow YAML...
    my_task:
      ...
      target: my_favorite_executor
    ...Workflow YAML...

#. Configure role based access policies for Mistral endpoints (policy.json)::

     [oslo_policy]
     policy_file = <path-of-policy.json file>

   Default policy.json file is in ``mistral/etc/``.
   For more details see `policy.json file
   <https://docs.openstack.org/oslo.policy/latest/admin/policy-json-file.html>`_.

#. After that try to run mistral engine and see it is running without
   any error::

     $ mistral-server --config-file <path-to-config> --server engine

