How to write an Action Plugin
=============================

1. Write a class based on mistral.actions.base.Actions
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
 myproject.plugins.example =
    runner = solum.mistral_plugins.somefile:RunnerAction

3. Add the namespace into /etc/mistral/mistral.conf
   (don't overwrite "mistral.plugins.std")

::

 action_plugins = mistral.plugins.std,myproject.plugins.example

4. Use your plugin

Note on naming the plugin.

 * The namespace is "myproject.plugins.example"
 * The class is named "runner"
 * Now you can call the action "example.runner"

::

 Workflow:
   tasks:
     myaction:
       action: example.runner
       parameters:
         param: avalue_to_pass_in
