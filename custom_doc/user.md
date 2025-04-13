The topics covered in this section are as follows:

* [Useful Links](#useful-links)
    * [Main Information](#main-information)
* [Features](#features)
    * [CloudFlow](#cloudflow)
    * [Action and Notifications](#action-and-notifications)
    * [Monitoring](#monitoring)
    * [Async Notification](#async-notification)
    * [Recovery Job](#recovery-job)
    * [Task Execution Duration](#task-execution-duration)
    * [Task Skip](#task-skip)
    * [Safe Input](#safe-input)
    * [Filtering Execution by Fields](#filtering-execution-by-fields)
    * [Idempotent Creation of Workflow Executions](#idempotent-creation-of-workflow-executions)
    * [Mistral Configuration Parameters Customization](#mistral-configuration-parameters-customization)
    * [RPC Implementations](#rpc-implementations)
    * [Mistral Deployment Configuration](#mistral-deployment-configuration)
    * [Mechanism to Close Stuck Running Action Executions](#mechanism-to-close-stuck-running-action-executions)
    * [Mistral Disaster Recovery](#mistral-disaster-recovery)
    * [Maintenance Mode](#maintenance-mode)
    * [Dry-run](#dry-run)
    * [Merge Type](#merge-type)
    * [Logging Configuration](#logging-configuration)
    * [HTTP Action Logging](#http-action-logging)
    * [Termination of Workflow Execution to ERROR](#termination-of-workflow-execution-to-error)
    * [Termination of Workflow Execution to CANCELLED](#termination-of-workflow-execution-to-cancelled)
    * [Mechanism to Execute std.noop Actions Inside Engine](#mechanism-to-execute-std-noop-actions-inside-engine)
    * [Mistral Smoke Test](#mistral-smoke-test)
    * [Headers Propagation](#headers-propagation)
    * [Action Timeout](#action-timeout)
    * [Workflow Definition Checksum](#workflow-definition-checksum)
    * [Execution Errors Report](#execution-errors-report)
    * [Total Amount of Objects in Collections](#total-amount-of-objects-in-collections)

# Useful Links

The useful links are provided in this section.

## Main Information

You can find information using the following links:

* Mistral Github [https://github.com/openstack/mistral](https://github.com/openstack/mistral)
* Documentation [https://docs.openstack.org/mistral/latest/](https://docs.openstack.org/mistral/latest/)
* REST API [https://docs.openstack.org/mistral/latest/user/rest_api_v2.html](https://docs.openstack.org/mistral/latest/user/rest_api_v2.html)
* DSL Specification [https://docs.openstack.org/mistral/latest/user/wf_lang_v2.html](https://docs.openstack.org/mistral/latest/user/wf_lang_v2.html)
* Mistral CLI [https://github.com/openstack/python-mistralclient](https://github.com/openstack/python-mistralclient)

# Features

The features are described in the sections below.

## CloudFlow

CloudFlow provides a workflow visualization tool for OpenStack Mistral.

For more information, refer to [https://github.com/nokia/CloudFlow](https://github.com/nokia/CloudFlow)

### Deploy

For more information about installation and deploy, refer to _Workflow Service Installation Procedure_.

## Action and Notifications

The following actions support mitreid integration:

* `oauth2.http` same as `std.http`.
* `oauth2.mistral_http` same as `std.mistral_http`.

When the `SECURITY_PROFILE` values is set to `prod`, Mistral generates a `m2m` token and pass to a HTTP request.

Similar process is followed for the `webhook` notifier plugin.

### Mistral CLI

Install the Mistral CLI. For more information, refer to the _Official Mistral Documentation_ at [https://docs.openstack.org/mistral/latest/user/cli/index.html](https://docs.openstack.org/mistral/latest/user/cli/index.html).

### Performance

Mitreid integration support does not affect performance.

## Monitoring

The monitoring information is explained below.

### Introduction

Monitoring collects Mistral metrics and displays them on Grafana dashboard.

For more information, refer to the _Grafana Documentation_ at [http://docs.grafana.org/](http://docs.grafana.org/)

### Dashboard Overview

Refer to the [Workflow Service Monitoring](/custom_doc/grafana_dashboards_overview.md) section under _Data Management Monitoring Guide_ for more information about dashboard. 

### Enabling Monitoring

Set the monitoring environment variables to enable monitoring.

For example:

```
MONITORING_ENABLED=True;
```

### Change in Deployment Process

Additionally, Mistral is deployed with the following:

* monitoring-agent
* Config map containing the URL and grouping metrics
* Service account for monitoring agent

## Async Notification

The Async Notification information is given below.

### Introduction

Mistral can be used by external system(s) to create workflow definitions and schedule workflow execution over API. However, there is no API for Mistral to communicate back to these external system(s) that the workflow execution is complete. Currently, an external system polls the Mistral API periodically to query workflow execution state, and that proves to be unscalable with the increasing amount of queries against the Mistral API. If there is a mechanism for Mistral to make a callback to the external system, the integration is more timely, efficient, stable, and scalable.

### Use Cases

An external system schedules a Mistral workflow execution. As the workflow execution progresses, status and other metadata is published as an event, and the external system chooses which event to consume.

### List of Events

The List of events is specified below.

#### Workflow Events

* WORKFLOW_PLANNED
* WORKFLOW_LAUNCHED
* WORKFLOW_SUCCEEDED
* WORKFLOW_FAILED
* WORKFLOW_CANCELLED
* WORKFLOW_PAUSED
* WORKFLOW_RESUMED
* WORKFLOW_RERUN

#### Task Events

* TASK_LAUNCHED
* TASK_SUCCEEDED
* TASK_FAILED
* TASK_RESUMED
* TASK_RERUN
* TASK_SKIPPED

### How to Use

Event subscription is done per execution when it is started. Pass arguments of events to execution parameters. 
For example:

```
json
{
  "workflow_id":"123e4567-e89b-12d3-a456-426655441111",
  "params": {
     "notify": [
         {
             "type": "webhook",
             "event_types": [
                 "WORKFLOW_SUCCEEDED"
             ],
             "url": "http://endpoint/of/webhook",
             "headers": {
                 "Content-Type": "application/json",
                 "X-Auth-Token": "123456789"
             }
         }
     ]
  }
}
```

### Plugins

Custom plugins are implemented as stevedore extensions and registered at **setup.cfg**. The custom plugin encapsulates any additional configuration, logic, and filtering for processing. Authentication to external systems using API keys or other means can be configured here. By default, there are three plugins:

* `noop` - Logs data and event type to stdout.
* `webhook` - Sends HTTP POST request by URL. List of parameters:
  * `url`
  * `headers`
* `webhook_with_retries` - Sends HTTP POST request by URL with retries. List of parameters:
  * `url`
  * `headers`
  * `number_of_retries`. The default value is 3. Use `-1` to have unlimited number of retries (be aware that if one of subscribers failed delivery process will be blocked).
  * `polling_time`. The time is specified in seconds. The default value is 10 seconds.

```
json
{
    "type": "webhook",
    "event_types": [
        "WORKFLOW_SUCCEEDED"
    ],
    "url": "http://endpoint/of/webhook",
    "headers": {
        "Content-Type": "application/json",
        "X-Auth-Token": "123456789"
    },
    "number_of_retries": 5,
    "polling_time": 10
}
```

**Note**: It is possible to write your own plugins.

### Notifications Example

Consider the following workflows:

```yaml
version: '2.0'
parent:
  tasks:
    parent_task0:
      on-success: [parent_task1]
    parent_task1:
      workflow: child
      on-success: [parent_task2]
    parent_task2:
      action: std.noop
child:
  tasks:
    child_task1:
      action: std.fail
      on-success: [child_task2]
    child_task2:
      action: std.noop
```
Start the workflow:

```bash
curl -X POST --data '{"workflow_name": "parent", "params": {"notify": [{"type": "noop"}]}}' -H "Content-Type: application/json" http://localhost:8989/v2/executions
```

`child_task1` fails because it contains `std.fail` action, this standard Mistral action always fails. Workflow produces the following events:

```text
The event WORKFLOW_LAUNCHED for (parent, a0fc44d2-7d35-405a-80dd-d6287667795b) is published by the noop notifier.
The event TASK_LAUNCHED for (parent_task0, fb1f3f8a-d491-40e9-ac85-966afd45ed53) is published by the noop notifier.
The event TASK_SUCCEEDED for (parent_task0, fb1f3f8a-d491-40e9-ac85-966afd45ed53) is published by the noop notifier.
The event TASK_LAUNCHED for (parent_task1, e6af8daa-ddf3-42d8-9a20-e9806eab751b) is published by the noop notifier.
The event WORKFLOW_LAUNCHED for (child, 3586e3c8-c774-4572-b0fe-e7c8f91c26a7) is published by the noop notifier.
The event TASK_LAUNCHED for (child_task1, 6267156b-5170-42ce-8bfd-881395364cc4) is published by the noop notifier.
The event TASK_FAILED for (child_task1, 6267156b-5170-42ce-8bfd-881395364cc4) is published by the noop notifier.
The event WORKFLOW_FAILED for (child, 3586e3c8-c774-4572-b0fe-e7c8f91c26a7) is published by the noop notifier.
The event TASK_FAILED for (parent_task1, e6af8daa-ddf3-42d8-9a20-e9806eab751b) is published by the noop notifier.
The event WORKFLOW_FAILED for (parent, a0fc44d2-7d35-405a-80dd-d6287667795b) is published by the noop notifier.
```

Change the action `child_task1` on `std.noop` in the database:

```sql
update task_executions_v2 set spec = '{"action": "std.noop", "version": "2.0", "type": "direct", "name": "child_task1", "on-success": ["child_task2"]}' where id = '$1
```

Rerun the `child_task1` task:

```bash
mistral task-rerun 6267156b-5170-42ce-8bfd-881395364cc4
```

After rerun, the workflow execution produces the following events:

```text
The event WORKFLOW_RERUN for (child, 3586e3c8-c774-4572-b0fe-e7c8f91c26a7) is published by the noop notifier.
The event WORKFLOW_RERUN for (parent, a0fc44d2-7d35-405a-80dd-d6287667795b) is published by the noop notifier.
The event TASK_RERUN for (parent_task1, e6af8daa-ddf3-42d8-9a20-e9806eab751b) is published by the noop notifier.
The event TASK_RERUN for (child_task1, 6267156b-5170-42ce-8bfd-881395364cc4) is published by the noop notifier.
The event TASK_SUCCEEDED for (child_task1, 6267156b-5170-42ce-8bfd-881395364cc4) is published by the noop notifier.
The event TASK_LAUNCHED for (child_task2, a78cd921-7f78-478e-b780-139215964336) is published by the noop notifier.
The event TASK_SUCCEEDED for (child_task2, a78cd921-7f78-478e-b780-139215964336) is published by the noop notifier.
The event WORKFLOW_SUCCEEDED for (child, 3586e3c8-c774-4572-b0fe-e7c8f91c26a7) is published by the noop notifier.
The event TASK_SUCCEEDED for (parent_task1, e6af8daa-ddf3-42d8-9a20-e9806eab751b) is published by the noop notifier.
The event TASK_LAUNCHED for (parent_task2, 034f1d60-ccf5-4b7b-8168-b032097379ce) is published by the noop notifier.
The event TASK_SUCCEEDED for (parent_task2, 034f1d60-ccf5-4b7b-8168-b032097379ce) is published by the noop notifier.
The event WORKFLOW_SUCCEEDED for (parent, a0fc44d2-7d35-405a-80dd-d6287667795b) is published by the noop notifier.
```

### Notification DTO

Notification DTO has fields described below:

For workflow execution:
* id
* name
* workflow_name
* workflow_namespace
* workflow_id
* root_execution_id
* state
* state_info
* project_id
* task_execution_id
* params
* created_at
* updated_at
* input
* output (*Note: available only for complete events like WORKFLOW_SUCCEEDED, WORKFLOW_FAILED and etc*)

For task execution:
* id
* name
* workflow_execution_id
* workflow_name
* workflow_namespace
* workflow_id
* root_execution_id
* state
* state_info
* type
* project_id
* created_at
* updated_at
* workflow_execution_input
* published (*Note: available only for complete events like TASK_SUCCEEDED, TASK_FAILED and etc*)

### Implementation

There is a new service, Mistral Notifier.

At the triggering of events such as completed tasks, started process, and so on, Mistral Notifier sends a message to RabbitMQ asynchronously.
Then, RabbitMQ passes it in the Mistral Notifier service. Events are processed at the final step by the plugins.
For example, the status of the task is sent to some service.

### Notifications Based on Kafka

There is an ability to store notifications in Kafka instead of RabbitMQ.
To guarantee notifications' order, use the **only one** instance of mistral-notifier.

The default configuration is as follows:

```text
[kafka_notifications]
enabled = true
kafka_host = 0.0.0.0
kafka_topic = mistral_notifications
kafka_consumer_group_id = notification_consumer_group
kafka_max_poll_interval = 3600
kafka_security_enabled = true
kafka_sasl_plain_username = username
kafka_sasl_plain_password = password
```

### Sequence Diagram with Notifications

An example of simple workflow processing with notifications is shown below.

![Simple WF Processing with Notifications](/custom_doc/img/mistral_notifications_sequence.png)

## Recovery Job

The purpose is to provide High Availability for Mistral.

* Failover - The currently running workflow is able to proceed on another pod in case of current pod failure.
* Recovery - The currently running workflow is able to proceed on the same pod after the pod is restarted.

Assumption: PostgreSQL is HA ready and RabbitMQ is out of scope.

### Problem Description

Two issues have been identified with Mistral services: Mistral-Executor and Mistral-Engine.

#### Mistral Executor

The Executor executes task Actions. When some actions are in the `RUNNING` state, during Mistral-Executor failure, these actions are stuck in the `RUNNING` state forever. This is because Mistral does not know how long your actions last.

**Solution**: For this case, the timeout and retry policy should be defined for all tasks. This combination of timeout and retry policy repeats actions or moves the task to the `ERROR` state. For more information, refer to the _Official Mistral Documentation_ [https://docs.openstack.org/mistral/latest/user/wf_lang_v2.html#policies](https://docs.openstack.org/mistral/latest/user/wf_lang_v2.html#policies).

For example:

This task setup moves the task to the `ERROR` state after timeout is expired.

```
yaml
my_task:
  action: my_action
  timeout: 30
```

This task setup repeats the action several times.

```
yaml
my_task:
  action: my_action
  timeout: 30
  retry:
    count: 10
    delay: 20
```

####  Mistral Engine

The Mistral-Engine orchestrates executions. Some actions of Mistral-Engine are scheduled. 

For example:

* Join operations
* Timeout policies
* Finished executions

When Mistral wants to make a scheduled call, it creates a row in the database. If some scheduled calls are executed during Mistral-Engine failure, then these calls are never executed again.

The Mistral community is aware of this problem. They promise to rewrite implementation of scheduled calls in the 6.0.0 release.

**Solution**: To execute these scheduled calls again, a special Recovery job has been introduced. The Recovery job searches scheduled calls by the following patterns:

* The current time is more than sum of the execution time of a scheduled call and custom interval.
* The time execution of calls is less one second.

The job executes the following query:

```
sql
UPDATE delayed_calls_v2
SET processing = FALSE
WHERE processing = TRUE
    AND now() > execution_time + '{0} second' :: INTERVAL
    AND now() > updated_at + '{0} second' :: INTERVAL
RETURNING factory_method_path, target_method_name, method_arguments, execution_time, key;
```

The following parameters can be passed to the parameters of Deploy jobs. For more information, refer to _Workflow Service Installation Procedure_,
or change in the environment variables in the Mistral-Monitoring Deployment Descriptor:

|Name|Default|Description|
|---|---|---|
|RECOVERY_INTERVAL|30|The recovery job is triggered with this interval.|
|HANG_INTERVAL|300|Delayed calls are updated with this interval.|
|RECOVERY_ENABLED|false|If set to `true`, the recovery job is enabled.|

When Mistral wants to start a new task, it creates task with IDLE state in the database and make RPC call to start the task.
If "run_task" RPC calls are executed during Mistral-Engine failure, then these tasks are stuck in IDLE state.
To prevent this special recovery job make additional "run_task" calls for tasks in IDLE state.
This job uses `RECOVERY_INTERVAL` and `RECOVERY_ENABLED` parameters described above, and the following additional parameter:

|Name|Default|Description|
|---|---|---|
|IDLE_TASK_TIMEOUT|20|Timeout for IDLE tasks to send run_task call again.|

### Recovery Scenarios

Due to non-persistent RabbitMQ, Mistral can lose some RPC calls. To avoid an error, Mistral can provide recovery operations for the lost calls.

To configure the recovery scenarios, `custom-mistral.conf` should be used.

```text
[recovery_job]
enabled = True
recovery_interval = 30
hang_interval = 600
idle_task_timeout = 120
waiting_task_timeout = 600
expired_subwf_task_timeout = 600
stucked_subwf_task_timeout = 600
```

|Name|Default|Description|
|---|---|---|
|enabled|True|Parameter for enabling the recovery job|
|recovery_interval|30|The recovery job is triggered with this interval|
|hang_interval|600|Timeout for scheduled calls to be in processing state|
|idle_task_timeout|120|Timeout for IDLE tasks to send run_task call again|
|waiting_task_timeout|600|Timeout for WAITING tasks to refresh its state again|
|expired_subwf_task_timeout|600|Timeout for subwf tasks without created subworkflow|
|stucked_subwf_task_timeout|600|Timeout for subwf tasks with completed subworkflow|

### Tests

The following HA tests have been created for Mistral.

10 executions and 100 tasks are executed in parallel. Mistral Engine or Mistral Executor fails in the middle of the tests. After some time, the executions and tasks state, number, output, etc. are verified.

Workflow example:

![Main Workflow](/custom_doc/img/main_workflow.PNG)

The main workflow consists of 30% of tasks of the nested workflow:

![Nested Workflow](/custom_doc/img/nested_workflow.PNG)

## Task Execution Duration

Calculating task execution duration as the difference between fields `created_at` and `updated_at` is incorrect.
It is important to understand that the lifecycle of the task consists of several states: `IDLE`, `WAITING`, `RUNNING`, `DELAYED`, `SUCCESS`. To find problems with performance, it is very important to know exactly the execution time of a task.
This time often coincides with the difference between `created_at` and `updated_at`, but it is important to understand that this does not always happen.
To solve this leak, fields `started_at` and `finished_at` have been added. So, to calculate task execution duration, you should use these fields.
Task execution duration follows simple rules:

* If the task has manual waiting `wait-before` or `wait-after`, this time should be included to the duration.
* Task retries should be included to duration.
* Task reruns should refresh duration.

These fields are available via Mistral's REST API `GET /v2/tasks`.

### Task Skip

There is an ability to skip tasks in the ERROR state.
The task is moved from ERROR state to SKIPPED state, variables from publish-on-skip section are published, and the workflow continues from tasks specified in on-skip section.
To do this, include the following attributes in the task definition:

* `on-skip` (required) - This parameter specifies which tasks should be started after skipping this task.
* `publish-on-skip` (optional) - This parameter specifies which variables should be published after skipping this task.

Skipping task without on-skip parameter is prohibited and can cause error "Only task with on-skip can be skipped."

To skip task, you should use Mistral REST API `PUT/v2/tasks/<id>`:

```
json
{
    "id": <id>,
    "task": {
        "state": "SKIPPED"
    }
}
```

### Read-Only Workflow Executions

You can put the workflow executions that are in `ERROR` state in to read-only status.
Workflow executions are moved to read-only status with all child workflow executions recursively. Any changes in the read-only workflow execution are prohibited. By default, read-only status is set for workflow executions in `SUCCESS` and `CANCELED` state.

To set a workflow execution to read-only status, use Mistral REST API `PUT/v2/executions/<id>`:

```
json
{
    "params": {
        "read_only": True
    }
}
```

## Safe Input

Mistral provides some mechanisms to perform rollback operations such as `on-error` task configuration. This helps "cleanup" work in case of task failure.
Task failure is the failure of its action or nested workflow. So, if a task fails because of input validation, the `on-error` branch of the workflow is not available.
This behavior is explained by the fact that input errors do not start actions or nested workflows, so there is nothing to "clean up."

Sometimes an input has a lot of variations, and it is hard to predict whether the input fails or not. Even in these cases, rollback mechanisms are very important, so there is a feature to enable Mistral's rollback mechanisms in case of input errors: `safe input`.

To enable `safe input`, define the `safe-input` field in the task definition.

For example:

```yaml
version: '2.0'
wf_1:
  tasks:
    t0:
      input:
        url: <% $.InvalidYaql %>
      action: std.http
      safe-input: true
      on-error: t1
    t1:
      action: std.noop
```

You can also configure this field using the `task-defaults` property.

## Filtering Execution by Fields

You can configure a list of fields to get by endpoint `${MISTRAL_URL}/v2/executions/{id}` by specifying the `fields` property in the `GET` method.
For example, `${MISTRAL_URL}/v2/executions/{id}?fields=state`, which returns only state of execution with specified id.

## Idempotent Creation of Workflow Executions

You can pass an execution ID that is used when creating a new execution object. If the object with this ID does not exist, then a new execution is created using this ID, and also the corresponding workflow starts normally. If the object exists, then the endpoint returns properties of this object in JSON without starting the workflow. If an execution
ID is not passed, then the endpoint works as before, so it is backwards compatible with the previous version.

A JSON example for creating an execution is as follows:

`POST /v2/executions`

```
json
{
	"workflow_name": "wf1",
	"id": "550e8400-e29b-41d4-a716-446655440000"
}
```

## Mistral Configuration Parameters Customization

OpenStack Mistral provides the capability to customize configuration parameters using the **.conf** file. However, such an approach is not convenient for cloud deployment as Mistral is deployed via Docker image.

To fix this, the capability to support Mistral configuration via OpenShift project ConfigMap was implemented. All Mistral parameters available for customization are stored in the **custom-mistral.conf** ConfigMap under the **custom-config** key. The format of its content are as follows:

```
bash
[parameters_group_1]
param_1=param_1_value
param_2=param_2_value
[parameters_group_2]
param_3=param_3_value
```

For example:

```
bash
[DEFAULT]
rpc_conn_pool_size=30
auth_type=mitreid
[database]
max_retries=120
```

The content of the **custom-mistral.conf** ConfigMap can be specified as the custom parameter `CUSTOM_CONFIG_PARAMS` of the deployment job, in multiline format and ending it by a semicolon:

```
bash
CUSTOM_CONFIG_PARAMS=[parameters_group_1]
param_1=param_1_value
param_2=param_2_value
[parameters_group_2]
param_3=param_3_value;
```

For example:

```
bash
CUSTOM_CONFIG_PARAMS=
[DEFAULT]
rpc_conn_pool_size=30
auth_type=mitreid
[database]
max_retries=120;
```

To apply new parameters from the ConfigMap, all Mistral deployments must be restarted.

For example:

```
bash
oc delete pod -l app=mistral
```

## RPC Implementations

There are two RPC, way to communicate between Mistral services, implementations:

* `oslo` - "at-most-once" delivery
* `kombu` - "at-least-once" message delivery

**Note**: `oslo` is enabled by default.

### Using kombu Implementation

Deploy Mistral with the following parameter:

```
bash
RPC_IMPLEMENTATION=kombu;
```

**Pay attention** to the `safe-rerun` policy:

`safe-rerun` a boolean value allowing a task to rerun if the executor dies during action execution. If set to `true`, the task may run twice. By default, it is set to `false`.

Consider the simple workflow:

```
yaml
version: '2.0'
not-safe-rerun:
  tasks:
    task1:
      action: std.sleep seconds=120
```

If the Mistral Executor dies during an action execution, then that message is re-delivered to another Mistral Executor. The action and task fails, because the `safe-rerun`
policy is set to `false` by default.

Consider the next workflow:

```
yaml
version: '2.0'
safe-rerun:
  tasks:
    task1:
      safe-rerun: true
      action: std.sleep seconds=120
```

Unlike the previous example, an action starts the second time. When a message is re-delivered to another Mistral Executor, the action starts the second time.

You can use the `safe-rerun` policy in the `task-defaults` section:

```
yaml
version: '2.0'
wf:
  task-defaults:
    safe-rerun: true
  tasks:
    task1:
      safe-rerun: false
      on-error:
        - task2
    task2:
      action: std.noop
```

## Mistral Deployment Configuration

You can choose to deploy Mistral in two possible configurations:

|Parameter|Description|
|---|---|
|main|Production setup (by default) - Each Mistral service runs in a separate pod.|
|lite|Develop setup - All Mistral services run in one pod excluding Monitoring.|

To choose a setup, specify the corresponding parameter in the `CUSTOM_PARAMETERS` section in the Deploy job.

Lite Mistral configuration also provides the possibility to deploy Mistral with RabbitMQ in same pod.
To enable this feature set the following parameters:

|Parameter|Description|
|---|---|
|INCLUDE_LOCAL_RMQ|By default, it is `False`. Set to `True` to include RabbitMQ container inside Mistral Lite pod.|
|RABBIT_IMAGE (not required)|By default, the value is `rabbitmq:master_latest`. Set image for RMQ container here.|
|RMQ_CPU (not required)|By default, the value is `300m`. Set the limit/request CPU for RMQ container.|
|RMQ_MEMORY (not required)|By default, the value is `300Mi`. Set the limit/request memory for RMQ container.|

To include/exclude RabbitMQ container to lite mistral deployment via DP_Deployer job you must use clean deployment method.

## Mechanism to Close Stuck Running Action Executions

It is possible that actions can be stuck in the `RUNNING` state, for example, if the assigned executor dies, or the message that signals the completion of the action is lost. This section describes a heartbeat-based solution to close these forgotten action executions. The related configuration options are `max_missed_heartbeats` and `evaluation_interval`.

**Note**: If either of these options are `0` then the feature **is not enabled**.

The default configuration is as follows:

```ini
[action_heartbeat]
max_missed_heartbeats = 15
evaluation_interval = 20
first_heartbeat_timeout = 3600
```

* `max_missed_heartbeats` - Defines the maximum amount of missed heartbeats to be allowed. If the number of missed heartbeats exceeds this number, then the related action execution state is changed to `ERROR` with the cause `Heartbeat wasn't received`.
* `evaluation_interval` - The interval between evaluations in seconds.
* `first_heartbeat_timeout` - The first heartbeat is handled differently, to provide a grace period in case there is no available executor to handle the action execution. For example, when first_heartbeat_timeout = 3600, wait 3600 seconds before closing the action executions that never received a heartbeat.

It is also possible to configure same mechanism for async actions. To include async action to heartbeat check rotation, you must mark it using `async-heartbeats-enabled` parameter.
Example:

```yaml
version: '2.0'
wf_with_async_heartbeats:
  tasks:
    t0:
      action: std.async_noop
      async-heartbeats-enabled: true
```

To update heartbeats of marked async actions send follow request:

```bash
curl -H 'Content-Type: application/json' -X PUT -d '{"action_ex_ids": ["b9d1ea4d-4a19-4487-bba5-f45c8c886106"]}' \
      http://localhost:8989/async_actions_heartbeats
```

## Mistral Disaster Recovery

The Mistral Disaster Recovery is explained below.

### RabbitMQ Configuration

Currently Mistral provides DR only with not persistent RabbitMQ.
For Mistral to correctly work, you need to install Mistral on default RabbitMQ virtual host("/") with RabbitMQ default admin credentials.

### Problem

Some Mistral Actions are not idempotent. Therefore after disaster recovery an operator should analyze their states and make a decision about changes in the VIM configuration, whether to resume executions or not.

To prevent automatic recovery/processing of delayed_calls or heartbeat mechanism, pause all the `RUNNING` executions.

### DR Script

Mistral DR script:

```text
Usage: $0 command

[--help] [--move-to-right] [--move-to-left] [--stop-left] [--stop-right] [--stop-left-mtnc] [--stop-right-mtnc] [--return-left] [--return-right]

Description commands:
    --help, -h         - show this help
    --move-to-right    - switchover to right site
    --move-to-left     - switchover to left side
    --stop-left        - failover to right site
    --stop-right       - failover to left site
    --stop-left-mtnc   - not implemented
    --stop-right-mtnc  - not implemented
    --return-left      - not implemented
    --return-right     - not implemented

    --activate         - remove "do-not-start" openshift selector and all Mistral pods
    --deactivate       - set "do-not-start" openshift selector

How to use commands:

+-------------------------------------+        +-------------------------------------+
|          INITIAL CONDITION          |        |           FINAL CONDITION           |
+------------------+------------------+--------+------------------+------------------+-----+-------------------+
| LEFT SITE        | RIGHT SITE       |  ===>  | LEFT SITE        | RIGHT SITE       |     | ALLOW COMMAND     |
+------------------+------------------+  ===>  +------------------+------------------+     +-------------------+
| MAIN             | DR               |  ===>  | DR               | MAIN             |  =  | --move-to-right   |
| failed           | DR               |  ===>  | stopped          | MAIN             |  =  | --stop-left       |
| DR               | MAIN             |  ===>  | MAIN             | DR               |  =  | --move-to-left    |
| DR               | failed           |  ===>  | MAIN             | stopped          |  =  | --stop-right      |
| stopped          | MAIN             |  ===>  | DR               | MAIN             |  =  | --return-left     |
| MAIN             | stopped          |  ===>  | MAIN             | DR               |  =  | --return-right    |
| MAIN             | DR               |  ===>  | MAIN             | graceful stopped |  =  | --stop-right-mtnc |
| MAIN             | graceful stopped |  ===>  | MAIN             | DR               |  =  | --return-right    |
| DR               | MAIN             |  ===>  | graceful stopped | MAIN             |  =  | --stop-left-mtnc  |
| graceful stopped | MAIN             |  ===>  | DR               | MAIN             |  =  | --return-left     |
+------------------+------------------+--------+------------------+------------------+-----+-------------------+
```

There are two stages:

* `activate` - Be launched after postgres
* `deactivate` - Be launched after config-prepare and before GlusterFS

### Switchover

The Switchover scenarios are specified below.

#### Mistral Deactivation

Mistral pauses all `RUNNING` executions before switchover. It is implemented on the project side.

Mistral sets the OpenShift selector to `do-not-start=true` during deactivation.

![dr-deactivate](/custom_doc/img/dr-deactivate.png)

#### Mistral Activation

Mistral DR script just removes the OpenShift selector and old pods during activate phase.

![dr-switchover](/custom_doc/img/dr-switchover.png)

### Failover

The failover scenarios are specified below.

#### Mistral Deactivation

Mistral sets the OpenShift selector to `do-not-start=true` during deactivation.

![dr-deactivate](/custom_doc/img/dr-deactivate.png)

#### Mistral Activation

It is necessary to execute a pause in the Mistral Docker container, because the Mistral sources and Python dependencies must pause workflow executions.
The OpenShift Job [https://docs.openshift.com/container-platform/3.5/dev_guide/jobs.html](https://docs.openshift.com/container-platform/3.5/dev_guide/jobs.html)
provides HA and timeout for the DR pod. It is implemented on the Mistral side during MANO activation.

In the Mistral DR pod, execute the following two commands:

* Get all `RUNNING` executions
* Pause all `RUNNING` workflow executions

In case of `--stop-left`, `--stop-right` commands in the Mistral DR script:

* Create Mistral OpenShift DR Job
* Wait for the job to finish
* Remove the OpenShift selector and all Mistral pods

![Failover](/custom_doc/img/dr-failover.png)

## Maintenance Mode

Mistral clusters has three states:

* `RUNNING` - The main Mistral state. There are no restrictions.
* `PAUSED` - All HTTP requests, **except for** `GET`, show a 423 exception. Mistral guarantees that all executions have a completed state or `PAUSED` state.
* `PAUSING` - All HTTP requests, **except for** `GET`, show a 423 exception. Mistral is pausing executions that have a `RUNNING` state.

To get a Mistral cluster state, execute the following command:

```bash
curl http://localhost:8989/maintenance
```

Response:

```json
{
  "status": "RUNNING"
}
```

To pause a Mistral cluster, execute the following command:

```bash
curl -H 'Content-Type: application/json' -X PUT -d '{"status": "PAUSED"}' \
      http://localhost:8989/maintenance
```

Response:

```json
{
  "status": "PAUSING"
}
```

Until a Mistral cluster has the `PAUSING` state, you can see how many tasks are left to pause:

```bash
curl http://localhost:8989/maintenance
```

Response:

```json
{
  "status": "PAUSING",
  "number_of_running_tasks": 5
}
```

To resume a Mistral cluster, execute the following command:

```bash
curl -H 'Content-Type: application/json' -X PUT -d '{"status": "RUNNING"}' \
      http://localhost:8989/maintenance
```

Response:

```json
{
  "status": "RUNNING"
}
```

You can resume a Mistral cluster in the `RUNNING` state. In this case, Mistral interrupts to pause executions.

Stub monitoring execution is disabled when Mistral cluster is in the `PAUSED` or `PAUSING` state.

You can cancel executions in the `PAUSED` mode using the following command:

```bash
curl -H 'Content-Type: application/json' -X PUT -d '{"state": "CANCELLED"}' \
      http://localhost:8989/v2/executions/4fec48bd-44a1-4b4e-8bcf-5b563a834e8a
```

Response:

```json
{
  "state_info": null,
  "created_at": "2018-07-04 12:57:38",
  "description": "",
  "state": "CANCELLED",
  "workflow_name": "safe-rerun",
  "task_execution_id": null,
  "updated_at": "2018-07-04 12:58:35",
  "workflow_id": "68d8442c-33bc-4fee-bdba-b37214998ed7",
  "params": "{\"namespace\": \"\", \"env\": {}}",
  "workflow_namespace": "",
  "output": "{\"result\": null}",
  "input": "{}",
  "id": "4fec48bd-44a1-4b4e-8bcf-5b563a834e8a"
}
```

## Dry-run

A new `dry-run` task policy is introduced. If the policy equals `True` then `test` method is executed instead of `run` method. The default value of `dry-run` policy is `False`.

### Workflow Examples

Echo action:

```python
class EchoAction(actions.Action):

    def __init__(self, output):
        self.output = output

    def run(self, context):
        return self.output

    def test(self, context):
        return 'Echo'
```

```yaml
version: '2.0'
wf:
  output:
    res: <% task(task1).result %>
  tasks:
    task1:
      dry-run: true
      action: std.echo output="run"
```

The execution result is an `Echo` since the value for `dry-run` is `True`.

```yaml
version: '2.0'
wf:
  output:
    res_test: <% task(task2).result %>
    res_run: <% task(task1).result %>
  task-defaults:
    dry-run: true
  tasks:
    task1:
      dry-run: false
      action: std.echo output="run"
    task2:
      action: std.echo output="run"
```

The execution output is `{"res_test": "Echo", "res_run": "run"}` because `dry-run` in the `task-defaults` section overrides a default value of task2 `dry-run`.

### OpenStack Actions

To create a test method for OpenStack you must create a Test Client.

For example, add a test method for OpenStack Base Action:

```python
class OpenStackAction(actions.Action):
    ...

    def test(self, context):
        method = self._get_client_method(self._create_test_client(context))

        return method(**self._kwargs_for_run)
```

A `_create_test_client` method is implemented inside child classes.
For example for `Nova` actions.

```python
class NovaAction(base.OpenStackAction, OpenStackActionGenerator):
    ...

    def _create_test_client(self, context):
        return test_actions.NovaTestClient()

```

You can choose a more generic way to create test client.

For example:

```python
# You can inherit from the Nova client class.
class NovaTestClient(object):

    def __init__(self, *args, **kwargs):
        # I just ignore them. But you can do anything with them.

        self.servers = Servers()

class Servers(object):

    def create(self, name, image, flavor, key_name, security_groups, nics):
        LOG.info(locals())

        return {
            'id': str(uuid.uuid4())
        }
```

Finally, write a worfklow consisting of invocation of a OpenStack actions:

```yaml
---
version: '2.0'

dry_run_openstack:
  input:
    - name
    - image_id
    - flavor_id
    - ssh_username: null
    - ssh_password: null

    # Name of previously created keypair to inject into the instance.
    # Either ssh credentials or keypair must be provided.
    - key_name: null

    # Security_groups: A list of security group names
    - security_groups: null

    # An ordered list of nics to be added to this server, with information about connected networks, fixed IPs, port etc.
    # Example: nics: [{"net-id": "27aa8c1c-d6b8-4474-b7f7-6cdcf63ac856"}]
    - nics: null

  output:
    id: <% $.vm_id %>

  task-defaults:
    dry-run: true

  tasks:
    create_vm:
      description: Initial request to create a VM.
      action: test_nova.servers_create name=<% $.name %> image=<% $.image_id %> flavor=<% $.flavor_id %>
      input:
        key_name: <% $.key_name %>
        security_groups: <% $.security_groups %>
        nics: <% $.nics %>
      publish:
        vm_id: <% task(create_vm).result.id %>
```

## Merge Type

When Mistral interacts with variables inside own context, it replaces one variable with another.

For example, consider the following workflow:

```yaml
version: '2.0'
wf:
  input:
    - aa:
        bb: wf_ex_input
        cc: wf_ex_input
        zz: wf_ex_input
  output:
    aa: <% $.aa %>
  tasks:
    task1:
      action: std.echo
      # emulate some action result
      input:
        output:
          cc: task1_res
          dd: task1_res
      on-success: [task2]
      publish:
        aa:
          cc: <% task().result["cc"] %>
          dd: <% task().result["dd"] %>
    task2:
      action: std.echo
      # emulate some action result
      input:
        output:
          bb: task2_res
      publish:
        aa:
          bb: <% task().result["bb"] %>
```

The result of execution is:

```json
{
  "aa": {
    "bb": "task2_res"
  }
}
```

To merge results of tasks, you must use flat data structure or the yaql merge function.

A new config option is merge_strategy is introduced.

The option has following values:

* `replace` - It is the default value. It is an old behavior when variable replace each other in context.
* `merge` - If you set this value, variable is merged with other context.

Consider `merge` strategy with the same workflow as above. The result is:

```json
{
  "aa" : {
    "bb": "task2_res",
    "cc": "task1_res",
    "dd": "task1_res",
    "zz": "wf_ex_input",
  }
}
```

## Logging Configuration

The default log format is compatible with Graylog, however, it is possible to configure the log format.

Mistral uses the library `oslo.log` for logging. For configuration information, refer to _Official oslo.log Configuration_ at [https://docs.openstack.org/oslo.log/latest/configuration/index.html](https://docs.openstack.org/oslo.log/latest/configuration/index.html).

You can use the `trace_uuid` variable to present `root_execution_id` as follows:

```logging_context_format_string = [%(asctime)s,%(msecs)03d][%(levelname)-5s][category=%(name)s][pid=%(process)d][trace_uuid=%(trace_uuid)s] %(message)s```

## HTTP Action Logging

By default Mistral logs information about requests in HTTP action. To hide request headers and endpoint response in logs apply configuration like following:

```text
[action_logging]
hide_response_body = true
hide_request_body = true
sensitive_headers = Header1, Header2
```
In this example all responses from endpoints and Header1 and Header2 in requests are hidden in logs.

## Termination of Workflow Execution to ERROR

You can terminate workflow execution to `ERROR` status.

To do this, send the folloving `PUT` request to `mistral_url/v2/executions/workflow_execution_id`:

With recursive terminate enabled:

```text
{"state": "ERROR", "params": {"recursive_terminate": "True"}}
```

With recursive terminate disabled:

```text
{"state": "ERROR"}
```

The `PUT` request returns the same workflow execution with `terminate_to_error` and `recursive_terminate` flags on it.
If recursive_terminate is disabled, Mistral waits until all child executions are complete.
If recursive_terminate is enabled, Mistral propagates flags to all child executions and tries to interrupt action executions
(action execution is interrupted if interrupt functionality is implemented in action).
All the upcoming tasks are created in `ERROR` state. You can continue execution by putting `ERROR` tasks in to the `RUNNING` state.

To implement interrupt logic, add the following code to the action:

```text
class SleepAction(actions.Action):
    def __init__(self):
        self.interrupted = False

    def run(self, context):
        ## action logic
        if self.interrupted:
            ## interrupt logic
        ## action logic
```

## Termination of Workflow Execution to CANCELLED

You can terminate workflow execution to `CANCELLED` status.

To do this, send the folloving `PUT` request to `mistral_url/v2/executions/workflow_execution_id`:

```text
{"state": "CANCELLED"}
```

Workflow cancelling is performed in async way: after this request, you'll see `cancelled: True` mark in workflow executions params.
From this moment, execution will wait all running tasks to be finished and no new task will be created.
If you have tasks with async actions, you have to complete them to complete execution cancelling.
When all tasks will be finished, execution will be moved in `CANCELLED` state.

To perform workflow cancel in sync way, send the following request:
```text
PUT /v2/executions/workflow_execution_id
{
  "state": "CANCELLED",
  "params": {
    "force_cancel": true
  }
}
```

After this request, workflow will change its state to `CANCELLED`, all running tasks will be moved to `ERROR` with state info `Task was failed due to workflow force cancel.` Only after these changes client will recieve a response with updated workflow state.

## Mechanism to Execute std noop Actions Inside Engine

By default, Mistral executes all the actions inside Executor, but to save some communication time, the `std.noop` actions are executed inside the Engine.

```text
[executor]
noop_execution = local
```

You can turn off this behavior.
To turn off this behavior and run the noop actions just as regular action using Executor, set the `noop_execution` value to `remote`.

```text
[executor]
noop_execution = remote
```

## Mistral Smoke Test

You can enable the Mistral smoke test with a simple workflow with noop action to check the basic Mistral functionality.
To enable it, use the following parameters in **custom-mistral.conf**:

```text
[monitoring]
e2e_smoke_enabled = True
e2e_smoke_interval = 60
e2e_smoke_threshold = 30
```

Where,

* `e2e_smoke_enabled` - Enables periodical execution of smoke workflow.
* `e2e_smoke_interval` - Specifies how often the smoke workflow should be executed.
* `e2e_smoke_threshold` - Specifies how many times the smoke workflow should be completed.

You can also see the smoke test results on the monitoring dashboard.

## Headers Propagation

Headers that were used in request to start execution, can be propagated into actions and notifications.
In actions, they will be available via action context:

```text
class TestHeadersAction(actions.Action):
    def __init__(self):
        self.headers = None

    def run(self, context):
        self.headers = context.execution.headers
```

In notifications, they will be sent with notification POST request.

You can filter target headers by setting specific regex template.

To configure this feature, you should define `headers_propagation` section in **custom-mistral.conf**:

```text
[headers_propagation]
enabled = True
template = your regex template
```

Be sure not to use `.*`, otherwise you can ruin your http actions (for example, by propagation 'Content-Length' header).

## Action Timeout

NC Mistral has different timeout implementation for simple tasks.

Action timeout before:

![Timeout Refactor 1](/custom_doc/img/timeout-refactor-1.png)

Previous implementation has 4 weak points:

![Timeout Refactor 2](/custom_doc/img/timeout-refactor-2.png)

The first and the second fails are incorrect at all instances since the action has not even started. Mistral can use action heartbeats to detect when an action was started to avoid these cases.
Unfortunately, Mistral cannot do anything with fails 3 and 4.
The executor has no access to the database to register that it started to process the action. The only channel between the Executor and Engine is Queue, which has delays and so on.

So a redesign is implemented for simple tasks (tasks with type action and without with-items):

![Timeout Refactor 3](/custom_doc/img/timeout-refactor-3.png)

This new implementation does not use the Scheduler, so Mistral is not affected by these 4 bad cases. Moreover, Mistral can now interrupt actions, if it hits its timeout.

## Workflow Definition Checksum

Workflow definition DTO stores it's checksum: md5 hash from definition string.
It automatically calculates after POST request and updates after each PUT request.
Example:

```text
{
    "id": "6a6e16e2-2d57-4764-9f3f-73c7b375f782",
    "name": "wf",
    "namespace": "",
    "input": "",
    "interface": "{\"input\": [], \"output\": []}",
    "definition": "some_definition_string",
    "checksum": "69d6c1f272dca3455474fbd468284efd",
    "tags": [],
    "scope": "private",
    "project_id": "<default-project>",
    "created_at": "2021-11-01 13:04:00",
    "updated_at": null
}
```

## Tasks statistic info of execution

The feature designed to enhance the visibility and management of tasks within workflow executions. The objective is to provide users with summary of task statuses, facilitating efficient monitoring and troubleshooting of workflow activities. It covers various task states, including running, successful, failed, idle, and paused tasks. Skipped state considers as
idle.

### Endpoint

```bash
curl http://<mistral-url>/v2/executions/<execution-id>/tasks_statistics?current_only=true
```
### Parameters

- `workflow_execution_id` (path parameter): UUID of the workflow execution for which statistics are being retrieved.
- `current_only` (query parameter): Optional, a boolean flag to specify whether to include tasks from nested sub-workflows. Set to `false` by default to include all tasks. Note, that all tasks can be fetched only for root workflow execution. For non-root one only tasks related to this workflow execution can be fetched, otherwise you'll get an error.

Example of output:
```text
{
    "TOTAL": 123,
    "RUNNING": 0,
    "SUCCESS": 121,
    "ERROR": 2,
    "IDLE": 0,
    "PAUSED": 0,
    "SKIPPED": 0
}
```

## With-items task statistics

This feature is designed to provide detailed insights into tasks that use the with-items pattern, which typically involve multiple sub-executions or actions. It aims to enhance monitoring and troubleshooting capabilities by offering a granular view of the state of each sub-task within a with-items task.

### Endpoint

```bash
curl http://<mistral-url>/v2/tasks/<task-id>/with_items_statistics
```
### Parameters

- `task_id` (path parameter): UUID of the task execution for which with-items statistics are being retrieved.

Example of output:
```text
{
    "TOTAL": 100,
    "RUNNING": 0,
    "SUCCESS": 100,
    "ERROR": 0,
    "IDLE": 0,
    "PAUSED": 0,
    "SKIPPED": 0
}
```

## Execution Errors Report

It is not very comfortable to use execution's state_info to assess problems:
it comes in not suitable for parsing form. To solve this problem, new endpoint was added to Mistral's execution object. New endpoint returns all errors that were **not** solved (for example, on-error clause) in linear JSON structure. Every error entity had id of it's parent object.

This error report is available via GET request to following endpoint:

```bash
curl http://<mistral-url>/v2/executions/<execution-id>/errors_report
```

Example of output:
```text
{
    "errors": [
        {
            "id": "efade488-2931-4aac-aa9b-ab92157832fc",
            "parent_id": null,
            "type": "WORKFLOW",
            "name": "error_wf",
            "error": "Failure caused by error in tasks: t_fail-on, t_failed-subwf, t_retries, t_timeout, t_with-items"
        },
        {
            "id": "2d8035cd-ec0a-461b-a7a4-4c48b94fb5d8",
            "parent_id": "efade488-2931-4aac-aa9b-ab92157832fc",
            "type": "TASK",
            "name": "t_fail-on",
            "error": "Failed by fail-on policy"
        },
        {
            "id": "39ee60da-dacf-4978-a023-aecef970d7f4",
            "parent_id": "efade488-2931-4aac-aa9b-ab92157832fc",
            "type": "TASK",
            "name": "t_timeout",
            "error": "The action raised an exception "
        },
        {
            "id": "cd1a25e9-7dbe-49ca-8319-043ef5b55da2",
            "parent_id": "39ee60da-dacf-4978-a023-aecef970d7f4",
            "type": "ACTION",
            "name": "std.sleep",
            "error": "Action timed out",
            "attributes": "{}",
            "params": "{'seconds': 10}",
            "idx": 0
        },
        {
            "id": "3a766902-2829-49bd-8b0c-17eea0b71fac",
            "parent_id": "efade488-2931-4aac-aa9b-ab92157832fc",
            "type": "TASK",
            "name": "t_failed-subwf",
            "error": "Failure caused by error in tasks: t0"
        },
        {
            "id": "de2a808a-2868-4a56-8061-2a9606bbfe67",
            "parent_id": "3a766902-2829-49bd-8b0c-17eea0b71fac",
            "type": "WORKFLOW",
            "name": "simple_error_wf",
            "error": "Failure caused by error in tasks: t0"
        },
        {
            "id": "e52bbe26-2f72-4dc2-b2e4-5207802df66a",
            "parent_id": "de2a808a-2868-4a56-8061-2a9606bbfe67",
            "type": "TASK",
            "name": "t0",
            "error": "The action raised an exception "
        },
        {
            "id": "dae14722-852f-4435-947c-ab2c6d050fd4",
            "parent_id": "e52bbe26-2f72-4dc2-b2e4-5207802df66a",
            "type": "ACTION",
            "name": "std.fail",
            "error": "Fail action expected exception.",
            "attributes": "{}",
            "params": "{}",
            "idx": 0
        },
        {
            "id": "bc128be7-be7e-479b-85a9-175945dbb9c3",
            "parent_id": "efade488-2931-4aac-aa9b-ab92157832fc",
            "type": "TASK",
            "name": "t_retries",
            "error": "The action raised an exception "
        },
        {
            "id": "cc4c0576-6332-4787-8348-66855d187525",
            "parent_id": "bc128be7-be7e-479b-85a9-175945dbb9c3",
            "type": "ACTION",
            "name": "std.fail",
            "error": "Fail action expected exception.",
            "attributes": "{}",
            "params": "{}",
            "idx": 0
        },
        {
            "id": "c2bb0f49-0cbe-4ed6-9335-53b1dfa97215",
            "parent_id": "bc128be7-be7e-479b-85a9-175945dbb9c3",
            "type": "ACTION",
            "name": "std.fail",
            "error": "Fail action expected exception.",
            "attributes": "{}",
            "params": "{}",
            "idx": 1
        },
        {
            "id": "fa213ad3-d4c0-4760-8066-cf5f26626998",
            "parent_id": "bc128be7-be7e-479b-85a9-175945dbb9c3",
            "type": "ACTION",
            "name": "std.fail",
            "error": "Fail action expected exception.",
            "attributes": "{}",
            "params": "{}",
            "idx": 2
        },
        {
            "id": "cad90948-1403-4d71-a1e2-e85beae780bf",
            "parent_id": "efade488-2931-4aac-aa9b-ab92157832fc",
            "type": "TASK",
            "name": "t_with-items",
            "error": "One or more actions had failed."
        },
        {
            "id": "b69ea91a-a890-4dc3-8a16-8213c3b7d127",
            "parent_id": "cad90948-1403-4d71-a1e2-e85beae780bf",
            "type": "ACTION",
            "name": "std.fail",
            "error": "Fail action expected exception.",
            "attributes": "{}",
            "params": "{}",
            "idx": 0
        },
        {
            "id": "0b0f8f27-f87c-4b87-904d-10b2c51fa6c0",
            "parent_id": "cad90948-1403-4d71-a1e2-e85beae780bf",
            "type": "ACTION",
            "name": "std.fail",
            "error": "Fail action expected exception.",
            "attributes": "{}",
            "params": "{}",
            "idx": 1
        },
        {
            "id": "3329a702-2a1f-45c9-adac-2b357e797873",
            "parent_id": "cad90948-1403-4d71-a1e2-e85beae780bf",
            "type": "ACTION",
            "name": "std.fail",
            "error": "Fail action expected exception.",
            "attributes": "{}",
            "params": "{}",
            "idx": 2
        },
        {
            "id": "ea073ef8-3081-4a70-8f2f-a47d6986f6cb",
            "parent_id": "cad90948-1403-4d71-a1e2-e85beae780bf",
            "type": "ACTION",
            "name": "std.fail",
            "error": "Fail action expected exception.",
            "attributes": "{}",
            "params": "{}",
            "idx": 3
        },
        {
            "id": "49c537c6-2f00-4128-bf80-7582477e0cad",
            "parent_id": "cad90948-1403-4d71-a1e2-e85beae780bf",
            "type": "ACTION",
            "name": "std.fail",
            "error": "Fail action expected exception.",
            "attributes": "{}",
            "params": "{}",
            "idx": 4
        }
    ]
}
```

## Total Amount of Objects in Collections

Mistral displays total amount of objects in collections. If collection has N objects, this number should be available via GET API:

Example:

```bash
curl http://localhost:8989/v2/executions
```

Response:

```json
{
  "executions": [...],
  "total": 100
}
```

Total should not be affected by request limits:

```bash
curl http://localhost:8989/v2/executions?limit=1
```

Response:

```json
{
  "executions": [...],
  "total": 100
}
```

But if some filters were passed, total could be changed:

```bash
curl http://localhost:8989/v2/executions?state=ERROR
```

Response:

```json
{
  "executions": [...],
  "total": 3
}
```

Field `total` is available for these collections:
* executions (/v2/executions)
* workflows (/v2/workflows)
* tasks (/v2/tasks & /v2/executions/<id>/tasks)

## Planned Workflow Execution Creation

The Planned Workflow Execution Creation feature introduces an optimized mechanism for creating workflow execution instances in Mistral. The actual execution of the workflow will be deferred and triggered through a scheduler. This allows for an instant retrieval of an object with an id and *'PLANNED'* state and, if necessary, performing further manipulations.

**Note**: The feature is recommended for use when creating workflow execution instances with a large number of tasks to optimize response time.

### Benefits

1. **Instant Response**: Immediate retrieval of the workflow execution identifier after creation.
2. **Resource Optimization**: Workflow execution initiation occurs through a scheduler, allowing for more efficient resource allocation.

### Configuration
The feature is *enabled* by default.
For disabling this feature `start_workflow_as_planned = False` had to be set in **api** section in **custom-mistral.conf**.

```bash
[api]
start_workflow_as_planned = False
```

#### Example Request:

```bash
curl -X POST http://example.com/mistral/api/v2/executions -d '{"workflow_name": "example_workflow"}'

```

#### Example Response:
```json
{
    "id": "9c99d30a-14e8-47d1-8373-b3d7046827c7",
    "workflow_id": "72b25e48-3ad7-41aa-8a33-d5dd9da1e315",
    "workflow_name": "example_workflow",
    "workflow_namespace": "",
    "description": "",
    "tags": [],
    "params": "{\"env\": {}, \"read_only\": false, \"terminate_to_error\": false, \"cancelled\": false}",
    "task_execution_id": null,
    "root_execution_id": null,
    "state": "PLANNED",
    "state_info": null,
    "input": "{}",
    "output": "{}",
    "created_at": "2023-12-05 10:58:05",
    "updated_at": "2023-12-05 10:58:05",
    "project_id": "<default-project>"
}
```
