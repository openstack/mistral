========================
Mistral Workflow Service
========================

What is Mistral?
================

Mistral is a workflow service. Lots of computations in computer systems
nowadays can be represented as processes that consist of multiple
interconnected steps that need to run in a particular order. Those steps
are often interactions with components distributed across different machines:
real hardware machines, cloud virtual machines or containers. Mistral provides
capabilities to automate such processes.

Particularly, Mistral can be used, for example, for solving administrator
tasks related to managing clusters of software, or for any other tasks
that span multiple components and take long to complete. It can also be used
as a central component for deploying distributed software in a truly large
scale. In any case where the ability to track the progress of the activity
becomes crucial, Mistral is a good fit.

A Mistral user can describe such a process as a set of tasks and transitions
between them, and upload such a definition to Mistral, which will take care of
state management, correct execution order, parallelism, synchronization and
high availability. In Mistral terminology such a set of tasks and
relations between them is called a **workflow**.


Just to Get Started
===================

* :doc:`user/overview`: If you've just started with Mistral, this short
  article will help you understand the main Mistral ideas and concepts.
* :doc:`user/faq`: Some of the typical questions you have may have already
  been answered here.


For End Users
=============

* :doc:`user/index`: If you're going to use Mistral functionality as an
  end user, i.e. writing and running workflows, then you need to read
  the full user documentation that tells about all Mistral features,
  including the full description of the Mistral Workflow Language and
  Mistral ReST API.
* :doc:`user/wf_lang_v2`: If you just want a direct link to the full
  specification of the Mistral Workflow Language, this is it.
* :doc:`user/rest_api_v2`: This is where you can find the full specification
  of the Mistral REST API.

For Administrators and Operators
================================

* :doc:`admin/index`: If you need to install, configure and maintain a
  Mistral cluster, this is a place to start.

For Developers
==============

* :doc:`contributor/index`: If you want to contribute to the project or
  write Mistral extensions, please start here.

Workflow Visualization (CloudFlow)
==================================

* `CloudFlow <https://github.com/nokia/CloudFlow>`_: If you're looking for
  a nice workflow visualization tool then visit this web page. CloudFlow
  provides a nice UI for debugging and analysing workflow executions.

Main Chapters
=============

.. toctree::
    :maxdepth: 1
    :includehidden:

    user/index
    admin/index
    contributor/index

.. only:: html

Search
======

* :ref:`Document search <search>`: Search the contents of this document.
