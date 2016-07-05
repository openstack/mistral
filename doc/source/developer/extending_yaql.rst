======================================
How to extend YAQL with a new function
======================================

********
Tutorial
********

1. Create a new Python project, an empty folder, containing a basic ``setup.py`` file.

.. code-block:: bash

   mkdir my_project
   cd my_project
   vim setup.py

.. code-block:: python

    try:
        from setuptools import setup, find_packages
    except ImportError:
        from distutils.core import setup, find_packages

    setup(
        name="project_name",
        version="0.1.0",
        packages=find_packages(),
        install_requires=["mistral", "yaql"],
        entry_points={
            "mistral.yaql_functions": [
                "random_uuid = my_package.sub_package.yaql:random_uuid_"
            ]
        }
    )


Publish the ``random_uuid_`` function in the ``entry_points`` section, in the
``mistral.yaql_functions`` namespace in ``setup.py``. This function will be
defined later.

Note that the package name will be used in Pip and must not overlap with
other packages installed. ``project_name`` may be replaced by something else.
The package name (``my_package`` here) may overlap with other
packages, but module paths (``.py`` files) may not.

For example, it is possible to have a ``mistral`` package (though not
recommended), but there must not be a ``mistral/version.py`` file, which
would overlap with the file existing in the original ``mistral`` package.

``yaql`` and ``mistral`` are the required packages. ``mistral`` is necessary
in this example only because calls to the Mistral Python DB API are made.

For each entry point, the syntax is:

.. code-block:: python

       "<name_of_YAQL_expression> = <path.to.module>:<function_name>"

``stevedore`` will detect all the entry points and make them available to
all Python applications needing them. Using this feature, there is no need
to modify Mistral's core code.

2. Create a package folder.

A package folder is directory with a ``__init__.py`` file. Create a file
that will contain the custom YAQL functions. There are no restrictions on
the paths or file names used.

.. code-block:: bash

    mkdir -p my_package/sub_package
    touch my_package/__init__.py
    touch my_package/sub_package/__init__.py

3. Write a function in ``yaql.py``.

That function might have ``context`` as first argument to have the current
YAQL context available inside the function.

.. code-block:: bash

    cd my_package/sub_package
    vim yaql.py

.. code-block:: python

    from uuid import uuid5, UUID
    from time import time


    def random_uuid_(context):
        """generate a UUID using the execution ID and the clock"""

        # fetch the current workflow execution ID found in the context
        execution_id = context['__execution']['id']

        time_str = str(time())
        execution_uuid = UUID(execution_id)
        return uuid5(execution_uuid, time_str)

This function returns a random UUID using the current workflow execution ID
as a namespace.

The ``context`` argument will be passed by Mistral YAQL engine to the
function. It is invisble to the user. It contains variables from the current
task execution scope, such as ``__execution`` which is a dictionary with
information about the current workflow execution such as its ``id``.

Note that errors can be raised and will be displayed in the task execution
state information in case they are raised. Any valid Python primitives may
be returned.

The ``context`` argument is optional. There can be as many arguments as wanted,
even list arguments such as ``*args`` or dictionary arguments such as
``**kwargs`` can be used as function arguments.

For more information about YAQL, read the `official YAQL documentation <http://yaql.readthedocs.io/en/latest/.>`_.

4. Install ``pip`` and ``setuptools``.

.. code-block:: bash

    curl https://bootstrap.pypa.io/get-pip.py | python
    pip install --upgrade setuptools
    cd -

5. Install the package (note that there is a dot ``.`` at the end of the line).

.. code-block:: bash

    pip install .

6. The YAQL function can be called in Mistral using its name ``random_uuid``.

The function name in Python ``random_uuid_`` does not matter, only the entry
point name ``random_uuid`` does.

.. code-block:: yaml

    my_workflow:
      tasks:
        my_action_task:
          action: std.echo
          publish:
            random_id: <% random_uuid() %>
          input:
            output: "hello world"

****************
Updating changes
****************

After any new created functions or any modification in the code, re-run
``pip install .`` and restart Mistral.

***********
Development
***********

While developing, it is sufficient to add the root source folder (the parent
folder of ``my_package``) to the ``PYTHONPATH`` environment variable and the
line ``random_uuid = my_package.sub_package.yaql:random_uuid_`` in the Mistral
entry points in the ``mistral.yaql_functions`` namespace. If the path to the
parent folder of ``my_package`` is ``/path/to/my_project``.

.. code-block:: bash

    export PYTHONPATH=$PYTHONPATH:/path/to/my_project
    vim $(find / -name "mistral.*egg-info*")/entry_points.txt

.. code-block:: ini

    [entry_points]
    mistral.yaql_functions =
        random_uuid = my_package.sub_package.yaql:random_uuid_
