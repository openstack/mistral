1. Follow Devstack documentation to setup a host for Devstack. Then clone
   Devstack source code::

      $ git clone https://github.com/openstack-dev/devstack

1. Clone Mistral source code::

      $ git clone https://github.com/stackforge/mistral

1. Copy Mistral integration scripts to Devstack::

      $ cp mistral/contrib/devstack/lib/mistral ${DEVSTACK_DIR}/lib
      $ cp mistral/contrib/devstack/extras.d/70-mistral.sh ${DEVSTACK_DIR}/extras.d/

1. Create/modify a ``localrc`` file as input to devstack::

      $ cd devstack
      $ touch localrc

1. The Mistral service is not enabled by default, so it must be enabled in ``localrc``
   before running ``stack.sh``. This example of ``localrc``
   file shows all of the settings required for Mistral::

      # Enable Mistral
      enable_service mistral

1. Deploy your OpenStack Cloud with Mistral::

   $ ./stack.sh


Note: 
1. All needed Mistral keystone endpoints will be automatically created
during installation.
1. Python-mistralclient also will be automatically cloned and installed.
