Mistral Configuration Guide
===========================

Mistral configuration is needed for getting it work correctly
either with real OpenStack environment or without OpenStack environment.

**NOTE:** The most of the following operations should performed in mistral directory.

1. Generate *mistral.conf* (if it does not already exist)::

    oslo-config-generator --config-file tools/config/config-generator.mistral.conf --output-file etc/mistral.conf

2. Edit file **etc/mistral.conf**.

3. **If you are not using OpenStack, skip this item.** Provide valid keystone auth properties::

    [keystone_authtoken]
    auth_uri = http://<Keystone-host>:5000/v3
    identity_uri = http://<Keystone-host:35357/
    auth_version = v3
    admin_user = <user>
    admin_password = <password>
    admin_tenant_name = <tenant>

4. **If you don't use OpenStack**, provide ``auth_enable = False`` in config file::

    [pecan]
    auth_enable = False

5. **If you are not using OpenStack, skip this item**. Register Mistral service and Mistral endpoints on Keystone::

    $ MISTRAL_URL="http://[host]:[port]/v2"
    $ openstack service create workflow --name mistral --description 'OpenStack Workflow service'
    $ openstack endpoint create workflow --publicurl $MISTRAL_URL --adminurl $MISTRAL_URL --internalurl $MISTRAL_URL

6. Configure transport properties in the corresponding config section: for RabbitMQ it is **oslo_messaging_rabbit**::

    [oslo_messaging_rabbit]
    rabbit_userid = <user_id>
    rabbit_password = <password>
    rabbit_host = <host>

 **NOTE**: Make sure that backend transport configuration is correct. Example for RabbitMQ::

    [DEFAULT]
    rpc_backend = rabbit

7. Configure database. **SQLite can't be used in production**. Use *MySQL* or *PostgreSQL* instead. Here are the steps how to connect *MySQL* DB to Mistral:

 Make sure you have installed **mysql-server** package on your Database machine (it can be your Mistral machine as well).

 Install MySQL driver for python::

    pip install mysql-python

 Create the database and grant privileges::

    mysql -u root -p

    CREATE DATABASE mistral;
    USE mistral
    GRANT ALL ON mistral.* TO 'root':<password>@<database-host>;

 Configure connection in Mistral config::

    [database]
    connection = mysql://<user>:<password>@<database-host>:3306/mistral

 **NOTE**: If PostgreSQL is used, configure connection item as below::

    connection = postgresql://<user>:<password>@<database-host>:5432/mistral

8. **If you are not using OpenStack, skip this item.** Update mistral/actions/openstack/mapping.json file which contains all allowed OpenStack actions, according to the specific client versions of OpenStack projects in your deployment. Please find more detailed information in tools/get_action_list.py script.

9. Configure Task affinity feature if needed. It is needed for distinguishing either single task executor or one task executor from group of task executors::

    [executor]
    host = my_favorite_executor

 Then, this executor can be referred in DSL by::

    ...Workflow YAML...
    my_task:
      ...
      target: my_favorite_executor
    ...Workflow YAML...

10. After that try to run mistral engine and see it is running without any error::

     mistral-server --config-file <path-to-config> --server engine

