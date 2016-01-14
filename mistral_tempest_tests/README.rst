==============================
Tempest Integration of Mistral
==============================

This directory contains Tempest tests to cover the mistral project.

To list all Mistral tempest cases, go to tempest directory, then run::

    $ testr list-tests mistral

To run only these tests in tempest, go to tempest directory, then run::

    $ ./run_tempest.sh -N -- mistral

To run a single test case, go to tempest directory, then run with test case name, e.g.::

    $ ./run_tempest.sh -N -- mistral_tempest_tests.tests.api.v2.test_mistral_basic_v2.WorkbookTestsV2.test_get_workbook

Alternatively, to run mistral tempest plugin tests using tox, go to tempest directory, then run::

    $ tox -eall-plugin mistral

And, to run a specific test::

    $ tox -eall-plugin mistral_tempest_tests.tests.api.v2.test_mistral_basic_v2.WorkbookTestsV2.test_get_workbook
