============================
How to write a Custom Action
============================

1. Write a class inherited from mistral.actions.base.Action

 .. code-block:: python

    from mistral_lib import actions

    class RunnerAction(actions.Action):
        def __init__(self, param):
            # store the incoming params
            self.param = param

        def run(self):
            # return your results here
            return {'status': 0}


2. Publish the class in a namespace (in your ``setup.cfg``)


 .. code-block:: ini

   [entry_points]
   mistral.actions =
       example.runner = my.mistral_plugins.somefile:RunnerAction

3. Install the Python package containing the action. If this was added to
   Mistral itself it will need to be reinstalled.

4. Run the following command so Mistral discovers the new action

 .. code-block:: console

    $ mistral-db-manage --config-file <path-to-config> populate

5. Now you can call the action ``example.runner``

  .. code-block:: yaml

    my_workflow:
      tasks:
        my_action_task:
          action: example.runner
          input:
            param: avalue_to_pass_in
