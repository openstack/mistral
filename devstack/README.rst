============================
Enabling Mistral in Devstack
============================

1. Download DevStack::

    git clone https://github.com/openstack-dev/devstack.git
    cd devstack

2. Add this repo as an external repository in ``local.conf`` file::

     > cat local.conf
     [[local|localrc]]
     enable_plugin mistral https://github.com/openstack/mistral

    To use stable branches, make sure devstack is on that branch, and specify
    the branch name to enable_plugin, for example::

      enable_plugin mistral https://github.com/openstack/mistral stable/pike

3. run ``stack.sh``
