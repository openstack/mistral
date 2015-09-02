Workbooks
=========

Using workbooks users can combine multiple entities of any type (workflows and actions) into one document and upload to Mistral service. When uploading a workbook Mistral will parse it and save its workflows and actions as independent objects which will be accessible via their own API endpoints (/workflows and /actions). Once it's done the workbook comes out of the game. User can just start workflows and use references to workflows/actions as if they were uploaded without workbook in the first place. However, if need to modify these individual objects user can modify the same workbook definition and re-upload it to Mistral (or, of course, user can do it independently).

**Namespacing**

One thing that's worth noting is that when using a workbook Mistral uses its name as a prefix for generating final names of workflows and actions included into the workbook. To illustrate this principle let's take a look at the figure below.

.. image:: /img/Mistral_workbook_namespacing.png
    :align: center

So after a workbook has been uploaded its workflows and actions become independent objects but with slightly different names.

YAML example
^^^^^^^^^^^^
::

    ---
    version: '2.0'

    name: my_workbook
    description: My set of workflows and ad-hoc actions

    workflows:
      local_workflow1:
        type: direct

        tasks:
          task1:
            action: local_action str1='Hi' str2=' Mistral!'
            on-complete:
              - task2

        task2:
          action: global_action
          ...

      local_workflow2:
        type: reverse

        tasks:
          task1:
            workflow: local_workflow1

          task2:
            workflow: global_workflow param1='val1' param2='val2'
            requires: [task1]
            ...

    actions:
      local_action:
        input:
          - str1
          - str2
        base: std.echo output="<% $.str1 %><% $.str2 %>"

**NOTE:** Even though names of objects inside workbooks change upon uploading Mistral allows referencing between those objects using local names declared in the original workbook.

**Attributes**

* **name** - Workbook name. **Required.**
* **description** - Workbook description. *Optional*.
* **tags** - String with arbitrary comma-separated values. *Optional*.
* **workflows** - Dictionary containing workflow definitions. *Optional*.
* **actions** - Dictionary containing ad-hoc action definitions. *Optional*.

For more details about DSL itself, please see :doc:`Mistral DSL specification </dsl/index>`
