Architecture
============

.. image:: img/mistral_architecture.png

* Engine - handles control and data flow of workflow executions. Computes which tasks are ready and places them in a queue. Passes the data from task to task, deals with condition transitions, etc.
* Task Executors - execute task Actions. Pick up tasks from the queue, run actions, and send results back to the engine.
* API server - exposes REST API to operate and monitor workflow executions.
* Scheduler - stores and executes delayed calls. It is the important Mistral component since it interacts with engine and executors. It also triggers workflows on events (e.g., periodic cron event)
* Persistence - stores workflow definitions, current execution states, and past execution results.
