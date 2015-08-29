Rally job related files
=======================

This directory contains rally tasks and plugins that are run by OpenStack CI.

Structure
---------

* task-mistral.yaml is a task that will be run in gates against OpenStack deployed
  by DevStack with installed Rally & Mistral.

* plugins - directory where you can add rally plugins. Almost everything in
  Rally is plugin. Benchmark context, Benchmark scenario, SLA checks, Generic
  cleanup resources, ....

* extra - all files from this directory will be copy pasted to gates, so you
  are able to use absolute path in rally tasks.
  Files will be in ~/.rally/extra/*


Useful links
------------

* More about rally: https://rally.readthedocs.org/en/latest/

* How to add rally-gates: https://rally.readthedocs.org/en/latest/gates.html

* About plugins:  https://rally.readthedocs.org/en/latest/plugins.html

* Plugin samples: https://github.com/openstack/rally/tree/master/samples/plugins

