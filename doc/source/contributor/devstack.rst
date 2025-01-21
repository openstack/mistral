=============================
Mistral Devstack Installation
=============================

Installing devstack for mistral
===============================

First, install devstack, see the following link for this:

`Devstack Installation <https://docs.openstack.org/devstack/latest/>`__


Before running ``stack.sh``, enable mistral plugin, heat and swift by adding:
your ``local.conf`` file to add::

    enable_plugin mistral https://opendev.org/openstack/mistral
    enable_plugin heat https://opendev.org/openstack/heat
    enable_service s-proxy s-object s-container s-account
    SWIFT_HASH=$ADMIN_PASSWORD


Finally, run ``stack.sh``

.. code-block:: console

    $ ./stack.sh

The mistral code will land in /opt/stack/mistral


OpenStack actions
=================

You may want to add mistral-extra to have openstack actions available in your
installation.

You can achieve that with an extra optional step:

.. code-block:: console

    $ git clone https://opendev.org/openstack/mistral-extra /opt/stack/mistral-extra
    $ /opt/stack/data/venv/bin/pip install /opt/stack/mistral-extra
    $ sudo systemctl restart devstack@mistral*


Tempest for mistral
===================

Clone the mistral-tempest-plugin repo:

.. code-block:: console

    $ git clone https://opendev.org/openstack/mistral-tempest-plugin.git /opt/stack/mistral-tempest-plugin

Install them:

.. code-block:: console

    $ /opt/stack/tempest/.tox/tempest/bin/pip install /opt/stack/mistral-tempest-plugin

Run tempest:

.. code-block:: console

    $ cd /opt/stack/tempest/
    $ /opt/stack/tempest/.tox/tempest/bin/tempest run --regex mistral --concurrency=6
