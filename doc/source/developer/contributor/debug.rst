Mistral Debugging Guide
=======================

To debug using a local engine and executor without dependencies such as
RabbitMQ, make sure your ``/etc/mistral/mistral.conf`` has the following
settings::

  [DEFAULT]
  rpc_backend = fake

  [pecan]
  auth_enable = False

and run the following command in *pdb*, *PyDev* or *PyCharm*::

  mistral/cmd/launch.py --server all --config-file /etc/mistral/mistral.conf --use-debugger

.. note::

    In PyCharm, you also need to enable the Gevent compatibility flag in
    Settings -> Build, Execution, Deployment -> Python Debugger -> Gevent
    compatible. Without this setting, PyCharm will not show variable values
    and become unstable during debugging.


Running unit tests in PyCharm
-----------------------------

In order to be able to conveniently run unit tests, you need to:

1. Set unit tests as the default runner:

  Settings -> Tools -> Python Integrated Tools ->
  Default test runner: Unittests

2. Enable test detection for all classes:

  Run/Debug Configurations -> Defaults -> Python tests -> Unittests -> uncheck
  Inspect only subclasses of unittest.TestCase

Running examples
----------------

To run the examples find them in mistral-extra repository
(https://github.com/openstack/mistral-extra) and follow the instructions on
each example.


Tests
-----

You can run some of the functional tests in non-openstack mode locally. To do
this:

#. set ``auth_enable = False`` in the ``mistral.conf`` and restart Mistral
#. execute::

    $ ./run_functional_tests.sh

To run tests for only one version need to specify it::

  $ bash run_functional_tests.sh v1

More information about automated tests for Mistral can be found on
`Mistral Wiki <https://wiki.openstack.org/wiki/Mistral/Testing>`_.
