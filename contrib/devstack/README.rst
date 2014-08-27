1. Follow Devstack documentation to setup a host for Devstack. Then clone
   Devstack source code.

2. Copy Mistral integration scripts to Devstack::

      $ cp lib/mistral ${DEVSTACK_DIR}/lib
      $ cp extras.d/70-mistral.sh ${DEVSTACK_DIR}/extras.d

3. Create a ``local.conf`` file as input to devstack.

4. The Mistral service is not enabled by default, so it must be
   enabled in ``local.conf`` before running ``stack.sh``. This example ``local.conf``
   file shows all of the settings required for Mistral::

      # Enable Mistral
      enable_service mistral

      # Use Keystone Identity API v3 (override 2.0 default)
      IDENTITY_API_VERSION=3

5. Deploy your OpenStack Cloud with Mistral::

   $ ./stack.sh
