============================
Mistral Policy Configuration
============================

.. warning::

   JSON formatted policy file is deprecated since Mistral 12.0.0 (Wallaby).
   This `oslopolicy-convert-json-to-yaml`__ tool will migrate your existing
   JSON-formatted policy file to YAML in a backward-compatible way.

.. __: https://docs.openstack.org/oslo.policy/latest/cli/oslopolicy-convert-json-to-yaml.html

Configuration
~~~~~~~~~~~~~

The following is an overview of all available policies in Mistral. For a sample
configuration file, refer to :doc:`samples/policy-yaml`.

.. show-policy::
   :config-file: ../../tools/config/policy-generator.mistral.conf
