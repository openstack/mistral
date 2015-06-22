#. Follow Devstack documentation to setup a host for Devstack. Then clone
   Devstack source code::

      $ git clone https://github.com/openstack-dev/devstack

#. Clone Mistral source code::

      $ git clone https://github.com/openstack/mistral

#. Copy Mistral integration scripts to Devstack::

      $ cp mistral/contrib/devstack/lib/mistral ${DEVSTACK_DIR}/lib
      $ cp mistral/contrib/devstack/extras.d/70-mistral.sh ${DEVSTACK_DIR}/extras.d/

#. Create/modify a ``localrc`` file as input to devstack::

      $ cd devstack
      $ touch localrc

#. The Mistral service is not enabled by default, so it must be enabled in ``localrc``
   before running ``stack.sh``. This example of ``localrc``
   file shows all of the settings required for Mistral::

      # Enable Mistral
      enable_service mistral

#. Deploy your OpenStack Cloud with Mistral::

   $ ./stack.sh


Note:

#. All needed keystone endpoints for Mistral will be automatically created during installation.
#. Python-mistralclient will be also cloned and installed automatically.
