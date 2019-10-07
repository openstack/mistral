cookiecutter-mistral-custom
===========================

A minimal [cookiecutter](https://github.com/audreyr/cookiecutter) template for Mistral custom actions, expressions

Usage
-----

This will run the cookiecutter and will install it if needed

.. code-block:: bash

 $ run_cookiecutter.sh

| Install the python project when finish editing ([sudo] pip install [folder])
| Run the script to update the actions in the database
| NOTE: default configuration file is /etc/mistral/mistral.conf

.. code-block:: bash

 $ update_actions.sh [/path/to/mistral/conf]

Explanation
-----------

The generated directory contains a minimal python project for mistral custom actions
and expressions.

It also has the following:

* LICENSE
   An Apache 2 license if you choose another license then update the setup.cfg file
* README
   A basic README file
* Testing
   Tox to manage test environments using pytest and flake8

