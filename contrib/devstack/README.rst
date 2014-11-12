1. Follow Devstack documentation to setup a host for Devstack. Then clone
   Devstack source code::

      $ git clone https://github.com/openstack-dev/devstack

2. Clone Mistral source code::

      $ git clone https://github.com/stackforge/mistral

2. Copy Mistral integration scripts to Devstack::

      $ cp mistral/contrib/devstack/lib/mistral ${DEVSTACK_DIR}/lib
      $ cp mistral/contrib/devstack/extras.d/70-mistral.sh ${DEVSTACK_DIR}/extras.d/

3. Create/modify a ``localrc`` file as input to devstack.

      $ cd devstack
      $ touch localrc

4. The Mistral service is not enabled by default, so it must be enabled in ``localrc``
   before running ``stack.sh``. This example of ``localrc``
   file shows all of the settings required for Mistral::

      # Enable Mistral
      enable_service mistral

      # Use Keystone Identity API v3 (override 2.0 default)
      IDENTITY_API_VERSION=3

5. Deploy your OpenStack Cloud with Mistral::

   $ ./stack.sh


Note: 
1. All needed Mistral keystone endpoints will be automatically created
during installation.
2. Python-mistralclient also will be automatically cloned and installed.
