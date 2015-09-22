Mistral Devstack Installation
=============================

1. Download DevStack::

    git clone https://github.com/openstack-dev/devstack.git
    cd devstack

2. Add this repo as an external repository, edit ``localrc`` file::

     enable_plugin mistral https://github.com/openstack/mistral

3. Run ``stack.sh``
