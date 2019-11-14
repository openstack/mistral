Workflow namespaces
===================

General
-------
Mistral allows creating workflows within a namespace. So it is possible to
create many workflows with the same name as long as they are in different
namespaces. This is useful when a user already has many workflows that are
connected to each other (some are sub workflows of others) and one of the
workflow names is already in use and the user does not want to edit that
workflow and all the ones referencing it or combine them into a workbook.
This is possible because the namespace is not a part of the Mistral workflow
language.

If one wants to use a namespace she needs to provide an additional parameter
to a corresponding operation run via REST API or CLI. If it's not provided,
Mistral will be operating within the default namespace.


REST API parameters
-------------------

In order to use namespaces Mistral a number of REST API methods have the
optional **namespace** parameter:

  * create workflow definition within a namespace::

        POST /v2/workflows?namespace=<namespace>

        <Workflow YAML text>

  * delete workflow definition within a namespace::

        DELETE /v2/workflows/<workflow id>?namespace=<namespace>

  * get a workflow definition within a namespace::

        GET /v2/workflows/<workflow id>?namespace=<namespace>

  * get all workflow definitions within a given namespace::

        GET /v2/workflows?namespace=<namespace>

  * update a workflow definition within a given namespace::

        PUT /v2/workflows?namespace=<namespace>

        <Workflow YAML text>

  * create an execution of a workflow that belongs to a non-default namespace::

        POST /v2/executions

        {
          "workflow_name": "<workflow id or name>",
          "workflow_namespace": "<namespace>",
          ...
        }

Resolving a workflow definition
-------------------------------

It's important to understand how Mistral resolves a workflow definition taking
namespaces into account when running workflows and how namespaces work in case
of workflow hierarchies.

The rules are the following:

  * If a user launches a workflow via API (or CLI) then the workflow name
    and the corresponding namespace are provided explicitly so Mistral
    will look for a workflow definition with the given name under the provided
    namespace. If a namespace is not specified then the default namespace
    (empty namespace value) will be used. If Mistral doesn't find a workflow
    definition with the given name and namespace it will return an error
    response.
  * If a workflow is launched as a sub workflow, i.e. it has a parent task
    in a different workflow, then Mistral uses the namespace of the parent
    workflow to resolve a workflow definition. In other words, Mistral
    propagates namespace to its child workflows. However, **if a workflow
    definition does not exist in the namespace of the parent workflow then
    Mistral will try to find it in the default namespace.** This is different
    from the previous case when a workflow is launched via API, Mistral would
    return an error instead of trying to find a workflow definition in the
    default namespace.
  * Workflows declared as part of workbooks are always located in the default
    namespace.

To illustrate how this all works let's look at the following workflow
definitions:

  ::

    ---
    version: '2.0'

    wf1:
      tasks:
        t1:
          workflow: wf2


  ::

    ---
    version: '2.0'

    wf2:
      tasks:
        t2:
          workflow: wf3

  ::

    ---
    version: '2.0'

    wf3:
      tasks:
        t3:
          action: std.noop

  ::

    ---
    version: '2.0'

    wf3:
      tasks:
        should_not_run:
          action: std.fail

So the call chain looks like this:

  .. code-block:: console

   wf1 -> wf2 -> wf3

However, notice that we have two workflows with the name "wf3".

Let's assume that these workflow definitions are uploaded to Mistral under
these namespaces:

  +----+---------------------+-----------+
  | ID | name                | namespace |
  +----+---------------------+-----------+
  | 1  | wf1                 | abc       |
  +----+---------------------+-----------+
  | 2  | wf2                 |           |
  +----+---------------------+-----------+
  | 3  | wf3                 | abc       |
  +----+---------------------+-----------+
  | 4  | wf3                 |           |
  +----+---------------------+-----------+

And we create a workflow execution like this via API:

  .. code-block:: console

    POST /v2/executions

    {
      "workflow_name": "wf1",
      "workflow_namespace": "abc"
    }


In this case, Mistral will:

  * Find "wf1" in the namespace "abc" (it doesn't exist in the default
    namespace anyway)
  * Try to find "wf2" in the namespace "abc" and since it doesn't exist
    there Mistral will find it in the default namespace
  * Find "wf3" in the namespace "abc" because it is propagated from "wf1"


However, if we launch a workflow like this:

  .. code-block:: console

    POST /v2/executions

    {
      "workflow_name": "wf2"
    }


We'll get the call chain

  .. code-block:: console

   wf2 -> wf3


And both workflow definitions will be taken from the default namespace
because a non-default namespace wasn't provided to the endpoint.
