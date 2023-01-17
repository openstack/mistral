Profiling Mistral
=================

What Is Profiling?
------------------
Profiling is a procedure for gathering runtime statistics about certain code
snippets like:

 - The maximum run time
 - The minimum run time
 - The average run time
 - The number of runs

Such info is a key to understanding performance bottlenecks residing in
a system. Having these metrics, we can focus on places in code that slow
down the system most and come up with optimisations to improve them.

A typical code snippet eligible for gathering this kind of information is a
function or a method since, most popular engineering techniques encourage
developers to decompose code into functions/methods representing well defined
parts of program logic. However, any arbitrary piece of code may be a target
for measuring.

'osprofiler' Project
--------------------

`osprofiler <https://osprofiler.readthedocs.io/en/latest/>`_ is a project
created within the OpenStack ecosystem to do profiling. The paragraphs below
explain how Mistral uses 'osprofiler' for profiling. The central concept of
'osprofiler' is a profile trace. A developer can mark code snippets with
profiler traces and 'osprofiler' will be tracking them. In general,
'osprofiler' allows cross-service profiling, that is, tracking a chain of
calls that belong to different RESTful services but related with the same
user request. However, this guide doesn't cover this more complex use case
and focus on profiling within just one service, Mistral.

Profiler Traces
---------------

The most common way to create a profiler trace in the code is adding a
special ''@trace"

 .. code-block:: python

    from osprofiler import profiler


    class DefaultEngine(base.Engine):
        ...

        @profiler.trace('engine-on-action-complete', hide_args=True)
        def on_action_complete(self, action_ex_id, result, wf_action=False,
                               async_=False):
            with db_api.transaction():
                if wf_action:
                    action_ex = db_api.get_workflow_execution(action_ex_id)

                    if result is None:
                        result = ml_actions.Result(data=action_ex.output)
                else:
                    action_ex = db_api.get_action_execution(action_ex_id)

                action_handler.on_action_complete(action_ex, result)

                return action_ex.get_clone()

In this example, we applied a special decorator to a method that adds a
profiling trace. The most important argument of the decorator is a trace
name. Its value is 'engine-on-action-complete' in our case. The second
argument 'hide_args' defines whether 'osprofiler' needs to pass method
argument values down to other layers. More specifically, there's a notion
metrics collector in 'osprofiler' that accumulates info about traces
in any desirable form, it depends on a particular implementation. This
topic though is out of the scope of this document. For our purposes, it's
better to set this argument to **True** which will not lead to loosing
performance on processing additional data (argument values of all method
calls).

Another way of adding a profiling trace is the following:

 .. code-block:: python

    try:
        profiler.start("engine-on-action-complete")

        action_handler.on_action_complete(action_ex, result)
    finally:
        profiler.stop()


Here we don't decorate the entire method, we only want to profile just one
line of code. But like in the previous example, we added a profiling trace.
The obvious advantage of using the decorator is that it can live in code
permanently because it doesn't pollute it too much and we can use them any
time we want to profile the system.

Even simpler and more concise way to achieve the same is use a special
context manager from 'osprofiler':

 .. code-block:: python

    with profiler.Trace('engine-on-action-complete'):
        action_handler.on_action_complete(action_ex, result)

Configuring Mistral for Profiling
---------------------------------

To start a profiling session, one needs to make the steps below.

Mistral Configuration File
^^^^^^^^^^^^^^^^^^^^^^^^^^

Make these change in the config file:

 .. code-block:: cfg

    [DEFAULT]
    log_config_append = wf_trace_logging.conf

    [profiler]
    enabled = True
    hmac_keys = secret_word

Defining the 'log_config_append' property allows to have all the logging
configuration in a separate file. In the example above, it's called
'wf_trace_logging.conf' but it can have a different name, if needed.
'[profiler]' group directly refers to the 'osprofiler' project and is
brought by it. The property 'enabled' is self-explaining, but the other one
is not. The value of the property 'hmac_keys' basically needs to be known
by someone who wants to start a profiling session. This value needs to be
passed as part of the user request. It will be shown a bit later.

Logging Configuration File
^^^^^^^^^^^^^^^^^^^^^^^^^^

The content of the logging configuration file conforms the documentation for
the standard 'logging' Python module. Find more details at
https://docs.python.org/3/library/logging.config.html#configuration-file-format

This particular example of the logging file configures three different loggers
and their corresponding counterparts like handlers. For the purpose of this
document though we only need to pay attention how 'profiler_trace' logger is
configure. Every entity starting with 'profiler' is related to profiling
configuration. The reason why other loggers are also included here is to show
how different loggers can coexist within one configuration file and how they
can reuse same entities.


 .. code-block:: cfg

    [loggers]
    keys=workflow_trace,profiler_trace,root

    [handlers]
    keys=consoleHandler, wfTraceFileHandler, profilerFileHandler, fileHandler

    [formatters]
    keys=wfFormatter, profilerFormatter, simpleFormatter, verboseFormatter

    [logger_workflow_trace]
    level=INFO
    handlers=consoleHandler, wfTraceFileHandler
    qualname=workflow_trace
    propagate=0

    [logger_profiler_trace]
    level=INFO
    handlers=profilerFileHandler
    qualname=profiler_trace

    [logger_root]
    level=DEBUG
    handlers=fileHandler

    [handler_fileHandler]
    class=FileHandler
    level=DEBUG
    formatter=verboseFormatter
    args=("/tmp/mistral.log",)

    [handler_consoleHandler]
    class=StreamHandler
    level=INFO
    formatter=simpleFormatter
    args=(sys.stdout,)

    [handler_wfTraceFileHandler]
    class=FileHandler
    level=INFO
    formatter=wfFormatter
    args=("/tmp/mistral_wf_trace.log",)

    [handler_profilerFileHandler]
    class=FileHandler
    level=INFO
    formatter=profilerFormatter
    args=("/tmp/mistral_osprofile.log",)

    [formatter_verboseFormatter]
    format=%(asctime)s %(thread)s %(levelname)s %(module)s [-] %(message)s
    datefmt=

    [formatter_simpleFormatter]
    format=%(asctime)s - %(message)s
    datefmt=%y-%m-%d %H:%M:%S

    [formatter_wfFormatter]
    format=%(asctime)s WF [-] %(message)s
    datefmt=

    [formatter_profilerFormatter]
    format=%(message)s
    datefmt=%H:%M:%S


Triggering Profiling Sessions
-----------------------------

Once Mistral is configured like explained above, in order to start a
profiling session we need to make a user request to Mistral that we
want to analyse but adding one property to it. The name of the property
is 'profile' and it needs to be set to the value of the 'hmac_keys'
property from the main configuration file.

.. code-block:: bash

    $ mistral execution-create my_slow_workflow --profile secret_word

Profiling Session Result
------------------------

When started in a profiling mode like just shown, Mistral will be writing
info about the profiling traces into the configured file. In our case it is
'/tmp/mistral_osprofile.log'.

 .. code-block:: cfg

    2020-02-27T08:04:25.789433          f12e75d5-5d59-4cbc-b74d-357f19290dd7 f12e75d5-5d59-4cbc-b74d-357f19290dd7 b9b29981-0916-4635-af18-d6c92f991f46 engine-start-workflow-start
    2020-02-27T08:04:25.790232          f12e75d5-5d59-4cbc-b74d-357f19290dd7 b9b29981-0916-4635-af18-d6c92f991f46 3cdd41b5-318a-4926-a38e-63344b6aef7a workflow-handler-start-workflow-start
    2020-02-27T08:04:25.812879          f12e75d5-5d59-4cbc-b74d-357f19290dd7 3cdd41b5-318a-4926-a38e-63344b6aef7a 603f1fab-be78-438d-af13-d94ed3b7e416 workflow-start-start
    2020-02-27T08:04:25.954502          f12e75d5-5d59-4cbc-b74d-357f19290dd7 603f1fab-be78-438d-af13-d94ed3b7e416 b1d0a77a-52f5-4415-a6c4-f16b3591a47d workflow-set-state-start
    2020-02-27T08:04:25.961298 0.006782 f12e75d5-5d59-4cbc-b74d-357f19290dd7 603f1fab-be78-438d-af13-d94ed3b7e416 b1d0a77a-52f5-4415-a6c4-f16b3591a47d workflow-set-state-stop
    2020-02-27T08:04:25.961769          f12e75d5-5d59-4cbc-b74d-357f19290dd7 603f1fab-be78-438d-af13-d94ed3b7e416 27b58351-aebe-4e37-9cec-91fdbef5c68b wf-controller-get-controller-start
    2020-02-27T08:04:25.962041 0.000267 f12e75d5-5d59-4cbc-b74d-357f19290dd7 603f1fab-be78-438d-af13-d94ed3b7e416 27b58351-aebe-4e37-9cec-91fdbef5c68b wf-controller-get-controller-stop
    2020-02-27T08:04:25.962311          f12e75d5-5d59-4cbc-b74d-357f19290dd7 603f1fab-be78-438d-af13-d94ed3b7e416 605ebfc2-a2bb-4fe1-8159-fc16f6741f5f workflow-controller-continue-workflow-start
    2020-02-27T08:04:26.023134 0.060832 f12e75d5-5d59-4cbc-b74d-357f19290dd7 603f1fab-be78-438d-af13-d94ed3b7e416 605ebfc2-a2bb-4fe1-8159-fc16f6741f5f workflow-controller-continue-workflow-stop
    2020-02-27T08:04:26.023600          f12e75d5-5d59-4cbc-b74d-357f19290dd7 603f1fab-be78-438d-af13-d94ed3b7e416 3a5a384a-9598-4844-a740-981f92e604af dispatcher-dispatch-commands-start
    2020-02-27T08:04:26.023918          f12e75d5-5d59-4cbc-b74d-357f19290dd7 3a5a384a-9598-4844-a740-981f92e604af d84a13e4-4763-4321-ab08-8cbd19656f2f task-handler-run-task-start
    2020-02-27T08:04:26.024179          f12e75d5-5d59-4cbc-b74d-357f19290dd7 d84a13e4-4763-4321-ab08-8cbd19656f2f 7878e4f8-aaaa-4b9b-b15a-35848b5cdd61 task-handler-build-task-from-command-start
    2020-02-27T08:04:26.024422 0.000243 f12e75d5-5d59-4cbc-b74d-357f19290dd7 d84a13e4-4763-4321-ab08-8cbd19656f2f 7878e4f8-aaaa-4b9b-b15a-35848b5cdd61 task-handler-build-task-from-command-stop

So any time Mistral runs code marked as a profiling trace it prints two
entries into the file: right before the code snippet starts and right
after its completion. Notice also that for the corresponding "-stop" entry
(the suffix going after the trace name) Mistral prints an additional number
in the second column. This is a duration of the code snippet.

This content of this file itself is probably not so useful (although, it
might be for some purpose) but based on it we can build the following
report:

 .. code-block:: bash

    Total time | Max time | Avg time | Occurrences | Trace name
    -------------------------------------------------------------------------------------------
    2948.326     8.612      1.218      2420          engine-on-action-complete
    2859.172     8.516      1.181      2420          action-handler-on-action-complete
    2812.726     8.482      1.162      2420          task-handler-on-action-complete
    2767.836     8.412      1.144      2420          regular-task-on-action-complete
    2766.199     8.411      1.143      2420          task-complete
    2702.764     8.351      0.460      5878          task-run
    2506.531     8.354      0.850      2948          dispatcher-dispatch-commands
    2503.398     8.353      0.437      5735          task-handler-run-task
    2488.940     8.350      0.434      5735          task-run-new
    1669.179     54.737     0.881      1894          default-executor-run-action
    1201.582     3.687      0.497      2420          regular-task-get-action-input
    1126.351     2.093      0.476      2366          ad-hoc-action-validate-input
    1125.129     2.092      0.238      4732          ad-hoc-action-prepare-input
    687.619      7.594      0.651      1056          task-handler-refresh-task-state
    387.622      3.872      0.300      1291          workflow-handler-check-and-fix-integrity
    234.231      4.068      0.392      597           workflow-handler-check-and-complete
    224.026      4.042      0.375      597           workflow-check-and-complete
    210.184      6.694      1.470      143           task-run-existing
    160.118      8.343      0.304      526           workflow-action-schedule
    141.398      4.546      0.268      528           workflow-handler-start-workflow
    109.641      4.361      0.208      528           workflow-start
    78.683       2.004      0.077      1024          direct-wf-controller-get-join-logical-state

    ...

To generate this report, run:

 .. code-block:: bash

    $ python tools/rank_profiled_methods.py /tmp/mistral_osprofile.log report.txt

And this report is somewhat really useful when it comes to analysing
performance bottlenecks. All times are shown in seconds.
