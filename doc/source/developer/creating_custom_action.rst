=============================
How to write an Action Plugin
=============================

1. Write a class inherited from mistral.actions.base.Action

 .. code-block:: python

    from mistral.actions import base

    class RunnerAction(base.Action):
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

3. Reinstall Mistral if it was installed in system (not in virtualenv).

4. Run db-sync tool via either

 .. code-block:: console

    $ tools/sync_db.sh --config-file <path-to-config>

 or

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
