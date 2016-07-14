# Sphinx DOC hints

## Migrating from OpenStack Wiki

* Install pandoc
* Copy wiki code into a file, e.g. `source.mw`
* Convert to .rst

  pandoc --from=mediawiki --to=rst --output=doc/source/dsl/dsl_v1.rst doc/source/dsl/source.mw

* To make code samples fancy:

  TODO: figure how to make YAML samples look nicer with `code::` directive

## Using autodoc with sphinxcontrib.pecanwsme.rest and wsmeext.sphinxext plugins

  TODO: why REST URL is not generated with parameters?

## Running sphinx-autobuild

[auto-loader](https://pypi.python.org/pypi/sphinx-autobuild/0.2.3) - rules for convenient development https://pypi.python.org/pypi/sphinx-autobuild/0.2.3. install, and run:

  sphinx-autobuild doc/source doc/build

