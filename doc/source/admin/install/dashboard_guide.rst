====================================
Mistral Dashboard Installation Guide
====================================

Mistral dashboard is the plugin for Horizon where it is easily possible to
control mistral objects by interacting with web user interface.

Setup Instructions
------------------

This instruction assumes that Horizon is already installed and it's
installation folder is *<horizon>*.

Detailed information on how to install
Horizon can be found at `Horizon Installation
<https://docs.openstack.org/horizon/latest/contributor/quickstart.html#setup>`_

The following steps should get you started:

#. Install mistral-dashboard in horizon virtual env:

.. code-block:: console

    $ pip install mistral-dashboard

#. Enable the dashboard:

.. code-block:: console

    $ cp -b <horizon>/mistraldashboard/enabled/_50_mistral.py \
      <horizon>/openstack_dashboard/local/enabled/_50_mistral.py

#. When you're ready, you would need to restart horizon, e.g. with apache:

.. code-block:: console

    # Debian based
    $ systemctl restart apache2

    # Or RHEL/CentOS
    $ systemctl restart httpd
