Mistral Client Installation Guide
---------------------------------

To install ``python-mistralclient``, it is required to have ``pip``
(in most cases). Make sure that ``pip`` is installed. Then type::

    $ pip install python-mistralclient

Or, if it is needed to install ``python-mistralclient`` from master branch,
type::

    $ pip install git+https://github.com/openstack/python-mistralclient.git

After ``python-mistralclient`` is installed you will see command ``mistral``
in your environment.

Configure authentication against Keystone
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If Keystone is used for authentication in Mistral, then the environment should
have auth variables::

    $ export OS_AUTH_URL=http://<Keystone_host>:5000/v2.0
    $ export OS_TENANT_NAME=tenant
    $ export OS_USERNAME=admin
    $ export OS_PASSWORD=secret
    $ export OS_MISTRAL_URL=http://<Mistral host>:8989/v2
      ( optional, by default URL=http://localhost:8989/v2)

and in the case when you are authenticating against keystone over https::

    $ export OS_CACERT=<path_to_ca_cert>

.. note:: In client, we can use both Keystone auth versions - v2.0 and v3.
          But server supports only v3.

You can see the list of available commands by typing::

    $ mistral --help

To make sure Mistral client works, type::

    $ mistral workbook-list

Configure authentication against Keycloak
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Mistral also supports authentication against Keycloak server via OpenID Connect
protocol.
In order to use it on the client side the environment should look as follows::

    $ export MISTRAL_AUTH_TYPE=keycloak-oidc
    $ export OS_AUTH_URL=https://<Keycloak-server-host>:<Keycloak-server-port>/auth
    $ export OS_TENANT_NAME=my_keycloak_realm
    $ export OS_USERNAME=admin
    $ export OS_PASSWORD=secret
    $ export OPENID_CLIENT_ID=my_keycloak_client
    $ export OPENID_CLIENT_SECRET=my_keycloak_client_secret
    $ export OS_MISTRAL_URL=http://<Mistral host>:8989/v2
     (optional, by default URL=http://localhost:8989/v2)

.. note:: Variables OS_TENANT_NAME, OS_USERNAME, OS_PASSWORD are used for
    both Keystone and Keycloak authentication. OS_TENANT_NAME in case of
    Keycloak needs to correspond a Keycloak realm. Unlike Keystone, Keycloak
    requires to register a client that access some resources (Mistral server in
    our case) protected by Keycloak in advance. For this reason,
    OPENID_CLIENT_ID and OPENID_CLIENT_SECRET variables should be assigned
    with correct values as registered in Keycloak.

Similar to Keystone OS_CACERT variable can also be added to provide a
certification for SSL/TLS
verification::

    $ export OS_CACERT=<path_to_ca_cert>

In order to disable SSL/TLS certificate verification MISTRALCLIENT_INSECURE
variable needs to be set
to True::

    $ export MISTRALCLIENT_INSECURE=True

Targeting non-preconfigured clouds
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^-

Mistral is capable of executing workflows on external OpenStack clouds,
different from the one defined in the `mistral.conf` file in the
`keystone_authtoken` section. (More detail in the :doc:`/configuration/index`).

For example, if the mistral server is configured to authenticate with the
`http://keystone1.example.com` cloud and the user wants to execute the
workflow on the `http://keystone2.example.com` cloud.

The mistral.conf will look like::

    [keystone_authtoken]
    www_authenticate_uri = http://keystone1.example.com:5000/v3
    ...

The client side parameters will be::

    $ export OS_AUTH_URL=http://keystone1.example.com:5000/v3
    $ export OS_USERNAME=mistral_user
    ...
    $ export OS_TARGET_AUTH_URL=http://keystone2.example.com:5000/v3
    $ export OS_TARGET_USERNAME=cloud_user
    ...

.. note:: Every `OS_*` parameter has an `OS_TARGET_*` correspondent. For more
          detail, check out `mistral --help`

The `OS_*` parameters are used to authenticate and authorize the user with
Mistral, that is, to check if the user is allowed to utilize the Mistral
service. Whereas the `OS_TARGET_*` parameters are used to define the user that
executes the workflow on the external cloud, keystone2.example.com/.

Use cases
"""""""""

**Authenticate in Mistral and execute OpenStack actions with different users**

As a user of Mistral, I want to execute a workflow with a different user on the
cloud.

**Execute workflows on any OpenStack cloud**

As a user of Mistral, I want to execute a workflow on a cloud of my choice.

Special cases
"""""""""""""

**Using Mistral with zero OpenStack configuration**:

With the targeting feature, it is possible to execute a workflow on any
arbitrary cloud without additional configuration on the Mistral server side.
If authentication is turned off in the Mistral server (Pecan's
`auth_enable = False` option in `mistral.conf`), there is no need to set the
`keystone_authtoken` section. It is possible to have Mistral use an external
OpenStack cloud even when it isn't deployed in an OpenStack environment (i.e.
no Keystone integration).

With this setup, the following call will return the heat stack list::

    $ mistral \
        --os-target-auth-url=http://keystone2.example.com:5000/v3 \
        --os-target-username=testuser \
        --os-target-tenant=testtenant \
        --os-target-password="MistralRuleZ" \
        run-action heat.stacks_list

This setup is particularly useful when Mistral is used in standalone mode, when
the Mistral service is not part of the OpenStack cloud and runs separately.

Note that only the OS-TARGET-* parameters enable this operation.
