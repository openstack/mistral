1. Follow Devstack documentation to setup a host for Devstack. Then clone
   Devstack source code.

2. Copy Mistral integration scripts to Devstack::

      $ cp lib/mistral ${DEVSTACK_DIR}/lib
      $ cp extras.d/70-mistral.sh ${DEVSTACK_DIR}/extras.d

3. Create a ``localrc`` file as input to devstack.

4. The Mistral service is not enabled by default, so it must be
   enabled in ``localrc`` before running ``stack.sh``. This example ``localrc``
   file shows all of the settings required for Mistral::

      # Enable Mistral
      enable_service mistral

5. Deploy your OpenStack Cloud with Mistral::

   $ ./stack.sh
