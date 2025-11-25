This document describes Mistral benchmarks.

## Overview

This section provides a mechanism for checking the performance of the Mistral.
Mistral, along with robot tests, provides stress tests, which check various difficult scenarios for Mistral and collect metrics that these scenarios characterize.

## Scenarios

This section describes the scenarios that are included in the benchmark list.

### Parallel Workflow With Joins

This scenario is a workflow in which several tasks run in parallel.
The first level of parallel tasks is followed by the next level, 
which consists of the same number of tasks. Each level, except the first one, 
waits for the complete completion of the previous level. 
This scenario loads the mistral with parallel operations, 
as well as a large amount of delayed calls.

In this scenario, the number of parallel tasks, 
and the number of levels are configurable parameters.

The scenario can be schematically represented in the form of the following figure:

![Parallel Workflow With Joins](/custom_doc/img/benchmark_parallel_tasks_with_joins.png)

The scenario assumes the sequential launch of such processes 
with an increase in the number of parallel tasks and levels.

### Workflow With Context Merge

This script is a set of tasks, each of which publishes data as JSON.
The topology of this workflow is a special case of the previous scenario 
with the number of parallel tasks equal to 10, and the number of levels equal to 10.

In this scenario, the amount of data and its size are configurable parameters.

The published JSON data looks like this:

![Workflow With Context Merge](/custom_doc/img/benchmark_wf_with_context_merge.png)

The scenario assumes the sequential launch of such processes 
with an increase in the amount of published data and its size.

### Workflow With Nested Workflows

This scenario is a set of parallel tasks, each of which runs a nested 
workflow of the same kind. At the last level, the launch of nested workflows stops,
the usual std.noop tasks are executed.

In this scenario, the number of tasks, and the depth are configurable parameters.

The scenario can be schematically represented using the image:

![Workflow With Nested Workflows](/custom_doc/img/benchmark_wf_with_nested_wfs.png)

The script assumes the sequential launch of such processes 
with an increase in the number of ticks and the nesting depth.

## Metrics

Benchmarks run collects these metrics:

* `wf duration` - duration of the workflow;
* `wf time per task` - duration of the workflow divided by tasks count;
* `min task duration` - minimal task's duration
* `avg task duration` - average task's duration
* `max task duration` - maximal task's duration

These metrics are collected for every executed scenario and represented as 
a table.

## Installation

To run benchmarks, you should deploy Mistral via operator and change some values
in your `values.yaml`:

```yaml
integrationTests:
  enabled: True
  runBenchmarks: True
```

## Recommendations

The following recommendations are provided for Mistral benchmarks:

* To perform a System Verification Test (SVT), use Mistral with the recommended hardware requirements or higher. Some SVT cases might fail on Mistral installed with minimal requirements.
* To improve the Mistral operation with 2 or more pods, it is recommended to use the following custom Mistral configuration.

```yaml
    [DEFAULT]
    rpc_message_ttl=3000
    rpc_response_timeout = 3000
    rpc_conn_pool_size = 10
    executor_thread_pool_size = 30
    
    [oslo_messaging_rabbit]
    rabbit_qos_prefetch_count = 1
    heartbeat_interval = 1
    heartbeat_rate = 2
    heartbeat_timeout_threshold = 60
```

* It is recommended to install Mistral with monitoring enabled to track the memory or CPU load during the testing.

## Results

All Mistral pods were installed with the recommended hardware requirements. RabbitMQ was installed with the recommended hardware requirements in a 3 pod cluster with a bound PV configuration.

### Mistral release 9.2.0_nc15 Results

The following tables describe the Mistral configuration:

|Mistral service|memory (MiB)|CPU (millicores)|
|---|---|---|
|API|500|1000|
|Engine|500|1000|
|Executor|300|200|
|Notifier|300|200|
|Monitoring|300|100|

|Mistral service|Setup 1 pod count|Setup 2 pod count|Setup 3 pod count|
|---|---|---|---|
|API|1|2|3|
|Engine|1|2|3|
|Executor|1|2|3|
|Notifier|1|2|3|
|Monitoring|1|2|3|

The following table provides the results:

| scenario name                  | wf duration   |---|---| wf time per task   |---|---|   min task duration |---|---|   avg task duration |---|---|   max task duration |---|---|
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
|---|setup 1|setup 2|setup 3|setup 1|setup 2|setup 3|setup 1|setup 2|setup 3|setup 1|setup 2|setup 3|setup 1|setup 2|setup 3|
| parallel_wf_with_joins_5_5     | 0:00:07       |0:00:04   |0:00:03| 0:00:00.280000     |0:00:00.200000  |0:00:00.120000|                   0 |0|0|               0     |0   |0|                   0 |0|0|
| parallel_wf_with_joins_10_10   | 0:00:30       |0:00:20   |0:00:18| 0:00:00.300000     |0:00:00.200000  |0:00:00.180000|                   0 |0|0|               0.02  |0.07|0.03|                   1 |1|1|
| parallel_wf_with_joins_20_10   | 0:01:32       |0:00:52   |0:00:37| 0:00:00.460000     |0:00:00.260000  |0:00:00.185000|                   0 |0|0|               0.015 |0.05|0.03|                   1 |1|1|
| parallel_wf_with_joins_50_5    | 0:05:24       |0:03:03   |0:02:04| 0:00:01.296000     |0:00:00.732000  |0:00:00.496000|                   0 |0|0|               0.068 |0.048|0.072|                   1 |1|1|
| wf_with_context_merge_100_10   | 0:01:00       |0:00:50   |0:00:40| 0:00:00.600000     |0:00:00.500000  |0:00:00.400000|                   0 |0|0|               0.27  |0.31|0.29|                   1 |1|1|
| wf_with_context_merge_100_1000 | 0:01:16       |0:00:58   |0:00:53| 0:00:00.760000     |0:00:00.580000  |0:00:00.530000|                   0 |0|0|               0.33  |0.41|0.36|                   1 |1|1|
| wf_with_context_merge_1000_100 | 0:05:59       |0:05:44   |0:05:30| 0:00:03.590000     |0:00:03.440000  |0:00:03.300000|                   0 |0|0|               2.5   |2.57|2.52|                   5 |6|5|
| wf_with_nested_wfs_1_50        | 0:00:10       |0:00:11   |0:00:12| 0:00:10            |0:00:11         |0:00:12|                  10 |11|12|              10    |11|12|                  10 |11|12|
| wf_with_nested_wfs_1_100       | 0:00:20       |0:00:23   |0:00:22| 0:00:20            |0:00:23         |0:00:22|                  20 |23|22|              20    |23|22|                  20 |23|22|
| wf_with_nested_wfs_1_300       | 0:01:04       |0:01:14   |0:01:08| 0:01:04            |0:01:14         |0:01:08|                  64 |74|68|              64    |74|68|                  64 |74|68|
| wf_with_nested_wfs_2_10        | 0:04:15       |0:02:29   |0:01:39| 0:02:07.500000     |0:01:14.500000  |0:00:49.500000|                 255 |148|98|             255     |148.5|98.5|                 255 |149|99|
| wf_with_nested_wfs_3_7         | 0:05:42       |0:03:20   |0:02:07| 0:01:54            |0:01:06.666667  |0:00:42.333333|                 340 |200|126|             340.333 |200|126|                 341 |200|126|
