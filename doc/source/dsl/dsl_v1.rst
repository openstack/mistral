Mistral DSL specification
-------------------------

Version 0.1

Main objects
~~~~~~~~~~~~

-  **Namespace**
-  **Action**
-  **Workflow**
-  **Task**
-  **Trigger**

Namespaces
~~~~~~~~~~

Contains a list of namespaces grouping custom (ad-hoc) actions. For
example, it's possible to create namespace "Nova" that would provide
actions "createVM", "deleteVM" and similar for VM management in
OpenStack.

Attributes
^^^^^^^^^^

All attributes are inside main keys of **Namespaces** - **namespaces
names**. Attributes of an individual namespace are:

-  **class** - currently Mistral supports the following action classes
   out of the box: std.http, std.mistral\_http, std.echo, std.email,
   std.ssh, this is an optional attribute
-  **base-parameters** - dictionary depending on type of the namespace,
   this parameter is optional. Values of these parameters apply to all
   actions inside the namespace. For example for std.http it can contain
   url, method, body and headers.
-  **actions** - list of actions provided by this namespace.

YAML example:
^^^^^^^^^^^^^

| ``Namespaces:``
| ``  Nova:``
| ``    class: std.http``
| ``    base-parameters:``
| ``      method: GET``
| ``    actions:``
| ``      create-vm:``
| ``      ......``
| ``      delete-vm:  ``
| ``      .....``

Action
~~~~~~

A function provided by specific namespace.

Attributes
^^^^^^^^^^

-  **name** - action name (string without space, mandatory attribute).
-  **base-parameters** - dictionary whose structure is defined by action
   class (or namespace class if defined). For std.http class it contains
   url, method, body and headers according to HTTP protocol
   specification.
-  **parameters** - list containing parameter names which should or
   could be specified in task. This attribute is optional and used only
   for documenting purposes.
-  **output** - dictionary-transformer for action output to send this
   output next to task. Keys of this dictionary will be included in task
   result, values are pure YAQL or inline YAQL expressions per key which
   define how the specific output should be retrieved from raw output
   (from action). See more about YAQL at
   https://pypi.python.org/pypi/yaql/0.3

YAML example:
^^^^^^^^^^^^^

| ``create-vm:``
| ``  base-parameters:``
| ``    url: servers``
| ``  parameters:``
| ``    - name``
| ``    - server_name  ``
| ``  output:``
| ``    vm_id: $.content.server.id``

Workflow
~~~~~~~~

Attributes
^^^^^^^^^^

-  **tasks** - list of tasks in this workflow, each task represents a
   computational step in the workflow.

YAML example:
^^^^^^^^^^^^^

| `` Workflow:``
| ``   tasks:``
| ``     create-vms:``
| ``     .....``
| ``     attache-volumes: ``
| ``     .....``

Task
~~~~

Represents a step in workflow, for example creating the VM

Attributes
^^^^^^^^^^

-  **action** - name of action to perform
-  **requires** - list of tasks which should be execute before this
   tasks, or list of task names as a keys and condition as a value, this
   is optional parameter
-  **parameters** - actual parameters for the task, each value can be
   either some number, string etc, or YAQL expression to retrieve value
   from task context
-  **on-success** - task which will be scheduled on execution after
   current task has finished with state 'SUCCESS'
-  **on-error** - task which will be scheduled on execution after
   current task has finished with state 'ERROR'
-  **on-finish** - task which will be scheduled on execution after
   current task has finished

YAML example:
'''''''''''''

| ``create-vm:``
| ``  action: Nova.create-vm``
| ``  parameters:``
| ``    image_id: $.image_id``
| ``    flavor_id: 42``
| ``  requires:``
| ``    task2: '$.value2 = 123'``
| ``    task4: '$.value4 = 122'``
| ``  on-success: task3``

Triggers
~~~~~~~~

Using triggers it is possible to run workflows according to specific
rules: periodically setting a cron (http://en.wikipedia.org/wiki/Cron)
pattern or on external events like ceilometer alarm.

Attributes
^^^^^^^^^^

-  **type** - can be PERIODIC, CEILOMETER\_ALARM
-  **tasks** - list of tasks which should be execute on trigger
-  **parameters** - list of task parameters

YAML example:
^^^^^^^^^^^^^

| ``triggers:``
| ``  backup-vm:``
| ``    type: periodic``
| ``    tasks: [create_backup, delete_old_backup] ``
| ``    parameters:``
| ``      cron-pattern: 1 0 * * *``

Full YAML example:
~~~~~~~~~~~~~~~~~~

This example requires the following properties provided in execution context:
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

#. - nova\_url ## url to Nova service, e.g. http://0.0.0.0:8774/v3
#. - server\_name ## Name you want to give to new instance
#. - image\_id ## image id from Glance service
#. - flavor\_id ## flavor id - type of instance hardware
#. - ssh\_username ## username of your VM
#. - ssh\_password ## password to your VM
#. - admin\_email ## email address to send notifications to
#. - from\_email ## email address to send notifications from
#. - smtp\_server ## SMTP server to use for sending emails (e.g.
   smtp.gmail.com:587)
#. - smtp\_password ## password to connect to SMTP server

| ``Namespaces:``
| `` Nova:``
| ``   # Nova actions for creating VM, retrieving IP and VM deleting.``
| ``   class: std.http``
| ``   actions:``
| ``     createVM:``
| ``       base-parameters:``
| ``         url: '{$.nova_url}/{$.project_id}/servers'``
| ``         method: POST``
| ``         headers:``
| ``           X-Auth-Token: $.auth_token``
| ``           Content-Type: application/json``
| ``         body:``
| ``           server:``
| ``             name: $.server_name``
| ``             imageRef: $.image_id``
| ``             flavorRef: $.flavor_id``
| ``       output:``
| ``         vm_id: $.content.server.id``
| `` ``
| ``     getIP:``
| ``       base-parameters:``
| ``         url: '{$.nova_url}/{$.project_id}/servers/{$.vm_id}'``
| ``         method: GET``
| ``         headers:``
| ``           X-Auth-Token: $.auth_token``
| ``       output:``
| ``         vm_ip: "$.content.server.addresses.novanetwork.where($.'OS-EXT-IPS:type' = 'floating')[0].addr"``
| `` ``
| ``     deleteVM:``
| ``       base-parameters:``
| ``         url: '{$.nova_url}/{$.project_id}/servers/{$.vm_id}'``
| ``         method: DELETE``
| ``         headers:``
| ``           X-Auth-Token: $.auth_token``
| ``       output:``
| ``         status: $.status``
| `` ``
| `` Server:``
| ``   actions:``
| ``     # HTTP request to the server.``
| ``     calcSumm:``
| ``       class: std.http``
| ``       base-parameters:``
| ``         url: '``\ ```http://`` <http://>`__\ ``{$.vm_ip}:5000/summ'``
| ``         method: POST``
| ``         body:``
| ``           arguments: $.arguments``
| ``       output:``
| ``         summ_result: $.content.result``
| `` ``
| `` Ssh:``
| ``   class: std.ssh``
| ``   base-parameters:``
| ``     host: $.vm_ip``
| ``     username: $.username``
| ``     password: $.password``
| ``   actions:``
| ``     # Simple SSH command.``
| ``     waitSSH:``
| ``       base-parameters:``
| ``         cmd: 'ls -l'``
| `` ``
| ``     # SSH command to run the server.``
| ``     runServer:``
| ``       base-parameters:``
| ``         cmd: 'nohup python ~/web_app.py > web_app.log &'``
| `` ``
| ``Workflow:``
| `` tasks:``
| ``   # Create a VM (request to Nova).``
| ``   createVM:``
| ``     action: Nova.createVM``
| ``     parameters:``
| ``       server_name: $.server_name``
| ``       image_id: $.image_id``
| ``       flavor_id: $.flavor_id``
| ``       nova_url: $.nova_url``
| ``       project_id: $.project_id``
| ``       auth_token: $.auth_token``
| ``     publish:``
| ``       vm_id: vm_id``
| ``     on-success: waitForIP``
| ``     on-error: sendCreateVMError``
| `` ``
| ``   # Wait till the VM is assigned with IP address (request to Nova).``
| ``   waitForIP:``
| ``     action: Nova.getIP``
| ``     retry:``
| ``       count: 10``
| ``       delay: 10``
| ``     publish:``
| ``       vm_ip: vm_ip``
| ``     parameters:``
| ``       nova_url: $.nova_url``
| ``       project_id: $.project_id``
| ``       auth_token: $.auth_token``
| ``       vm_id: $.vm_id``
| ``     on-success: waitSSH``
| ``     on-error: sendCreateVMError``
| `` ``
| ``   # Wait till operating system on the VM is up (SSH command).``
| ``   waitSSH:``
| ``     action: Ssh.waitSSH``
| ``     retry:``
| ``       count: 10``
| ``       delay: 10``
| ``     parameters:``
| ``       username: $.ssh_username``
| ``       password: $.ssh_password``
| ``       vm_ip: $.vm_ip``
| ``     on-success: runServer``
| ``     on-error: sendCreateVMError``
| `` ``
| ``   # When SSH is up, we are able to run the server on VM (SSH command).``
| ``   runServer:``
| ``     action: Ssh.runServer``
| ``     parameters:``
| ``       vm_ip: $.vm_ip``
| ``       username: $.ssh_username``
| ``       password: $.ssh_password``
| ``     on-success: calcSumm``
| ``     on-error: sendCreateVMError``
| `` ``
| ``   # Send HTTP request on server and calc the result.``
| ``   calcSumm:``
| ``     action: Server.calcSumm``
| ``     retry:``
| ``       count: 10``
| ``       delay: 1``
| ``     parameters:``
| ``       arguments:``
| ``         - 32``
| ``         - 45``
| ``         - 23``
| ``       vm_ip: $.vm_ip``
| ``     publish:``
| ``       result: summ_result``
| ``     on-finish: sendResultEmail``
| `` ``
| ``   # In case of createVM error send e-mail with error message.``
| ``   sendResultEmail:``
| ``     action: std.email``
| ``     parameters:``
| ``       params:``
| ``         to: [$.admin_email]``
| ``         subject: Workflow result``
| ``         body: |``
| ``           Workflow result of execution {$.__execution.id} is {$.result}``
| `` ``
| ``           -- Thanks, Mistral Team.``
| ``       settings:``
| ``         smtp_server: $.smtp_server``
| ``         from: $.from_email``
| ``         password: $.smtp_password``
| ``     on-finish: deleteVM``
| `` ``
| ``   # In case of createVM error send e-mail with error message.``
| ``   sendCreateVMError:``
| ``     action: std.email``
| ``     parameters:``
| ``       params:``
| ``         to: [$.admin_email]``
| ``         subject: Workflow error``
| ``         body: |``
| ``           Failed to create a VM in execution {$.__execution.id}``
| `` ``
| ``           -- Thanks, Mistral Team.``
| ``       settings:``
| ``         smtp_server: $.smtp_server``
| ``         from: $.from_email``
| ``         password: $.smtp_password``
| ``     on-finish: deleteVM``
| `` ``
| ``   # Destroy the VM (request to Nova).``
| ``   deleteVM:``
| ``     action: Nova.deleteVM``
| ``     parameters:``
| ``       nova_url: $.nova_url``
| ``       project_id: $.project_id``
| ``       auth_token: $.auth_token``
| ``       vm_id: $.vm_id``

Initial execution context
^^^^^^^^^^^^^^^^^^^^^^^^^

| `` {``
| ``   "nova_url": ``\ \ ``,``
| ``   "image_id": ``\ \ ``,``
| ``   "flavor_id": ``\ \ ``,``
| ``   "server_name": ``\ \ ``,``
| ``   "ssh_username": ``\ \ ``,``
| ``   "ssh_password": ``\ \ ``,``
| ``   "admin_email": ``\ \ ``,``
| ``   "from_email": ``\ \ ``,``
| ``   "smtp_server": ``\ \ ``,``
| ``   "smtp_password": ``\ \ ``,``
| `` }``

**When a workflow starts Mistral also adds execution information into
the context so the context looks like the following:**

| `` {``
| ``   "nova_url": TBD,``
| ``   "image_id": TBD,``
| ``   "image_id": ``\ \ ``,``
| ``   "flavor_id": ``\ \ ``,``
| ``   "server_name": ``\ \ ``,``
| ``   "ssh_username": ``\ \ ``,``
| ``   "ssh_password": ``\ \ ``,``
| ``   "admin_email": ``\ \ ``,``
| ``   "from_email": ``\ \ ``,``
| ``   "smtp_server": ``\ \ ``,``
| ``   "smtp_password": ``\ \ ``,``
| ``   "__execution": {``
| ``     "id": "234234",``
| ``     "workbook_name" : "my_workbook",``
| ``     "project_id": "ghfgsdfasdfasdf"``
| ``     "auth_token": "sdfljsdfsdf-234234234",``
| ``     "trust_id": "oiretoilkjsdfglkjsdfglkjsdfg"``
| ``   }``
| `` }``
