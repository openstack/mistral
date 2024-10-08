==============================
Configuration and Policy Guide
==============================

The static configuration for mistral lives in two main files: ``mistral.conf``
and ``policy.yaml``. These are described below.

Configuration
-------------

Mistral, like most OpenStack projects, uses INI-style configuration files to
configure various services and utilities. This functionality is provided by the
`oslo.config` project. *oslo.config* supports loading configuration from both
individual configuration files and a directory of configuration files. By
default, mistral will search for a config file named
``/etc/mistral/mistral.conf``.

More information on how you can use the configuration options to configure
services and what configuration options are available can be found below.

* :doc:`Configuration Guide <config-guide>`: Detailed
  configuration guides for various parts of your Mistral system.

* :doc:`Config Reference <config-reference>`: A complete reference of all
  configuration options available in the ``mistral.conf`` file.

.. only:: html

   * :doc:`Sample Config File <config-sample>`: A sample config
     file with inline documentation.

.. # NOTE(amorin): This is the section where we hide things that we don't
   # actually want in the table of contents but sphinx build would fail if
   # they aren't in the toctree somewhere.
.. toctree::
   :hidden:

   config-guide.rst
   config-reference.rst
   config-sample.rst

Policy
------

Mistral, like most OpenStack projects, uses a policy language to restrict
permissions on REST API actions. This functionality is provided by the
`oslo.policy` project. *oslo.policy* supports loading policy configuration
from both an individual configuration file, which defaults to ``policy.yaml``,
and one or more directories of configuration files, which defaults to
``policy.d``. These must be located in the same directory as the
``mistral.conf`` file(s). This behavior can be overridden by setting the
:oslo.config:option:`oslo_policy.policy_file` and
:oslo.config:option:`oslo_policy.policy_dirs` configuration options.

More information on how mistral's policy configuration works and about what
policies are available can be found below.

* :doc:`Policy Reference <policy-reference>`: A complete reference of all
  policy points in mistral and what they impact.

.. only:: html

   * :doc:`Sample Policy File <policy-sample>`: A sample mistral
     policy file with inline documentation.

.. # NOTE(amorin): This is the section where we hide things that we don't
   # actually want in the table of contents but sphinx build would fail if
   # they aren't in the toctree somewhere.
.. toctree::
   :hidden:

   policy-reference.rst
   policy-sample.rst
