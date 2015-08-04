How to write an Action Plugin
=============================

1. Write a class inherited from mistral.actions.base.Action
::

 from mistral.actions import base

 class RunnerAction(base.Action):
    def __init__(self, param):
        # store the incomming params
        self.param = param

    def run(self):
        # return your results here
        return {'status': 0}

2. Publish the class in a namespace
   (in your setup.cfg)

::

 [entry_points]
 mistral.actions =
    example.runner = my.mistral_plugins.somefile:RunnerAction

3. Reinstall Mistral if it was installed in system (not in virtualenv).
4. Run Db-sync tool via either::

    *tools/sync_db.sh --config-file <path-to-config>*

or::

    *mistral-db-manage --config-file <path-to-config> populate*

5. Use your plugin

 * Now you can call the action "example.runner"

::

 Workflow:
   tasks:
     myaction:
       action: example.runner
       parameters:
         param: avalue_to_pass_in

