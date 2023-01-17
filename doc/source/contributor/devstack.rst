=============================
Mistral Devstack Installation
=============================

First, install devstack, see the following link for this:
`Devstack Installation <https://docs.openstack.org/devstack/latest/>`_


Before running ``stack.sh``, enable mistral plugin by editing your
``local.conf`` file to add:

    enable_plugin mistral https://github.com/openstack/mistral


Finally, run ``stack.sh``

The mistral code will land in /opt/stack/mistral
