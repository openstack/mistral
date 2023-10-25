=============================
Mistral Devstack Installation
=============================

Installing devstack for mistral
===============================

First, install devstack, see the following link for this:
`Devstack Installation <https://docs.openstack.org/devstack/latest/>`_


Before running ``stack.sh``, enable mistral plugin by editing your
``local.conf`` file to add:

    enable_plugin mistral https://github.com/openstack/mistral


Finally, run ``stack.sh``

The mistral code will land in /opt/stack/mistral

Tempest for mistral
===================

As stack user, clone the mistral-tempest-plugin repo::

    git clone https://github.com/openstack/mistral-tempest-plugin.git /opt/stack/mistral-tempest-plugin

Install the plugin::

    /opt/stack/tempest/.tox/tempest/bin/pip install /opt/stack/tempest/.tox/tempest/bin/

Run tempest::

    /opt/stack/tempest/.tox/tempest/bin/tempest run --regex mistral --concurrency=6
