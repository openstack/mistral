Actions
=======

A particular instruction associated with a task that needs to be performed once the task runs. It can be anything like
running a shell script, HTTP request or sending a signal to some system external to Mistral. Actions can be synchronous
or asynchronous.

In case of synchronous action, Mistral will send a signal to Mistral Executor and will be waiting for the result from
Executor. Once Executor completes action, it sends the result to Mistral Engine.

In case of asynchronous action Mistral will send a signal to third party service and will be waiting for a corresponding
action result to be delivered back to Mistral API. Once the signal is sent, Mistral won't care more about action state
and result. Third party service should do a request to Mistral API and provide info about corresponding
*action execution* and its state and result.

.. image:: /img/Mistral_actions.png

:doc:`How to work with asynchronous actions </developer/asynchronous_actions>`

System Actions
--------------

System actions are provided by Mistral out of the box and can be used by anyone. It is also possible to add system
actions for specific Mistral installation via a special plugin mechanism.

:doc:`How to write an Action Plugin </developer/creating_custom_action>`


Ad-hoc Actions
--------------

Ad-hoc actions are a special types of actions that can be created by user. Ad-hoc actions are always created as a
wrapper around any other existing system actions and their main goal is to simplify using same actions many times with
similar pattern.

.. note:: Nested ad-hoc actions currently are not supported (i.e. ad-hoc action around another ad-hoc action).

.. note:: More about actions - :ref:`actions-dsl`.
