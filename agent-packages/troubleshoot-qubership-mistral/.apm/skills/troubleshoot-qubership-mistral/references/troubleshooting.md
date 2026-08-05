Topics covered in this section are as follows:

* [Mistral Workflow has Error Status](#mistral-workflow-has-error-status)
* [Mistral API is Not Responding](#mistral-api-is-not-responding)
* [Execution of Workflow is Stuck](#execution-of-workflow-is-stuck)
* [Mistral Service was not Deployed](#mistral-service-was-not-deployed)
* [Request on Execution Creation is Stuck](#request-on-execution-creation-is-stuck)
* [Different IDP Tenants](#different-idp-tenants)
* [RabbitMQ Collects a Lot of Messages](#rabbitmq-collects-a-lot-of-messages)
* [Mistral Cannot Deploy Because of Active Connections to DB](#mistral-cannot-deploy-because-of-active-connections-to-db)
* [How to Clean Mistral Database](#how-to-clean-mistral-database)

# Mistral Workflow has Error Status

If the Mistral workflow has the "error" status, you can find the _output_ or _state_info_ in a Mistral entity as follows:

* Execution: ```http://_mistral_url_/v2/executions/_execution_id_```
* Task: ```http://_mistral_url_/v2/executions/_execution_id_/tasks```
* Action: ```http://_mistral_url_/v2/action_executions/_action_id_```

# Mistral API is Not Responding

If the Mistral API service is not responding, or the response takes a long time, it is due to a lack of resources.

To address this problem, perform the following steps:

1. Navigate through the Mistral API deployment config to the **Logs** tab or Kibana.
1. If there is a line "Child _XXX_ killed by signal 9" in the logs, you have to increase the main memory or limit the number of requested objects.
The following table shows the approximate memory overhead numbers for **/v2/workflows**. It is calculated on a local DEV environment:

|Number of Requested Objects|Approximate Memory Overhead, Mb|
|---|---|
|1000|15|
|2000|24|
|4000|42|
|5000|50|
|7000|70|
|10000|100|

# Execution of Workflow is Stuck

To address this problem, perform the following steps:

1. Navigate through the Mistral Engine and Executor deployment config to the **Logs** tab or Graylog.
1. If there is a line "Killed by" in logs, you need to increase the main memory.
1. If any Mistral pod was recently redeployed, it could be the cause.

# Mistral Service was not Deployed

To address this problem, perform the following steps:

1. Navigate through the Mistral service deployment config to the **Logs** tab or Graylog.
1. If there is a problem with the PostgreSQL and RabbitMQ connection, check these services.

# Request on Execution Creation is Stuck

## Problem

The HTTP request when creating an execution or action is stuck or failed by timeout.

## Solution

Check a Mistral RabbitMQ host.

```bash
RABBIT_HOST=$(oc get cm mistral-common-params -o=jsonpath='{.data.rabbit-host}')
oc rsh dc/mistral-api curl http://$RABBIT_HOST:15672
```

If the command fails, you must set the correct RabbitMQ host.

If the command returns some HTML code, check the Mistral logs.
When `mistral-engine` does not contain the `Engine server started.` record, then you probably have a short format of RabbitMQ host, for example, `rabbitmq.rabbitmq`.
If this is the case, you should convert the RabbitMQ host to full DNS format: `<service>.<namespace>.svc.<zone>.`, for example `rabbitmq.rabbitmq.svc.cluster.local`. A short DNS name does not resolve in some OpenShift environments.

**Note**: After changing the host, it is necessary to restart the pods:

```bash
oc delete pods -l app=mistral
```

You can check that Mistral works properly using the following commands in a Mistral API pod:

```bash
$ bash
$ source ./envs.sh
$ mistral run-action std.noop
{"result": null}
```

# Different IDP Tenants

## Problem

You can observe the following problems:

* Unable to get Mistral entities using the Mistral API.
* The message `ERROR oslo_messaging.rpc.server DBEntityNotFoundError: Workflow not found [workflow_identifier=
some_workflow, namespace=]` appears in the logs during an execution creation.

## Solution

First of all, you must make sure that the problematic entities are actually present in the databases table.

|Entity Name|Table Name|SQL Query|
|---|---|---|
|Workflow|workflow_definitions_v2|`SELECT * FROM workflow_definitions_v2 where id = 'your_id';`|
|Workflow execution|workflow_executions_v2|`SELECT * FROM workflow_executions_v2 where id = 'your_id';`|
|Task|task_executions_v2|`SELECT * FROM task_executions_v2 where id = 'your_id';`|
|Action definition|action_definitions_v2|`SELECT * FROM action_definitions_v2 where id = 'your_id';`|
|Action execution|action_executions_v2|`SELECT * FROM action_executions_v2 where id = 'your_id';`|

Then, compare the `project_id` from the SQL result with the `tenant-id` of your token.

To extract a tenant from the token, you can use the following website: [https://jwt.io/](https://jwt.io/).
Your payload data should look like this:

```json
{
  "sub": "4b24c5b3-5bcc-41ef-9d2a-f3c7e05e409d",
  "realm_access": {
    "roles": []
  },
  "azp": "4b24c5b3-5bcc-41ef-9d2a-f3c7e05e409d",
  "scope": "profile",
  "iss": "http://idm.idm",
  "typ": "Bearer",
  "exp": 1537172655,
  "iat": 1537169055,
  "jti": "f728a5ae-357f-4ad2-93cd-fe81b41162b6",
  "tenant-id": "default"
}
```

If `project_id` differs from `tenant-id`, then there are two possible situations:

* The Mistral entity was created using one `tenant-id`, but you get the entity using another `tenant-id`.
* The Mistral entity was created when Mistral security turned off, and you try to get the entity after security is turned on.

When Mistral security is switched on using the `AUTH_ENABLE=True` parameter, Mistral enables multitenancy. It is the reason 
why you cannot access the specific Mistral entities using the different tenants.

# RabbitMQ Collects a Lot of Messages

## Problem

If some Mistral service is down, RabbitMQ collects messages for this service until it is up again.
This huge message flow could kill the Mistral service because of resources limits.

## Solution

To solve this problem, you can either clear this message queue, or limit the message count that the Mistral service can handle at one time.

### Clearing RabbitMQ Queue

The following steps should be done in the RabbitMQ pod:

First, before cleaning the queue, you need to check that there are no unacked messages.

You can check this on the RabbitMQ's user interface in the **Channels** tab:

![Channels List](/custom_doc/img/rabbitmq_channels.png)

* If you have some, you need to close the connection associated with this channel, so all unacked messages will be returned to the queue.
* Check the name of the channel with these unacked messages through RabbitMQ's user interface:  

![Channel](/custom_doc/img/rabbitmq_channel.png)

* Get pid of these connection via terminal: `# rabbitmqctl list_connections pid name`. For example:

![Connections List](/custom_doc/img/rabbitmq_list_connections.png)

* Remove this connection via terminal: `# rabbitmqctl close_connection '<YOUR_CONNECTION_PID>' 'STR_EXPLANATION'`. For example:

![Remove Connection](/custom_doc/img/rabbitmq_close_connection.png)

Second, remove all the messages from your queues with lots of messages:

* Check the name of the queue that collects a lot of messages in RabbitMQ's UI in the **Queues** tab:  

![Queues List](/custom_doc/img/rabbitmq_queues.png)

* Purge this queue via terminal: `# rabbitmqctl purge_queue [-p VHOST] 'QUEUE_NAME'`. For example:

![Purge Queue](/custom_doc/img/rabbitmq_purge_queue.png)

* Check that all the messages were successfully deleted:

![After Purge](/custom_doc/img/rabbitmq_after_purge.png)

### Limit Message Count

To limit the message count Mistral can handle at one time, you need to deploy the Mistral service with this custom-config:  

```
[oslo_messaging_rabbit]
rabbit_qos_prefetch_count = 20
```

There is no common way to choose the correct value of this parameter, but you should keep in mind your resource limitations, 
message size, message count, and current load to your service.

# Mistral Cannot Deploy Because of Active Connections to DB

## Problem

If someone else is using Mistral's database while you are deploying it with the `clean` flag, this deploy will fail.

## Solution

In this case, you can view the active connections in the deploy logs.

*Example of logs:*

```
2018-11-29 14:29:06.669 17779 INFO mistral.nc_upgrade [-] Try to drop 'postgres' database
2018-11-29 14:29:06.675 17779 INFO mistral.nc_upgrade [-] There are active connections to this database.
2018-11-29 14:29:06.676 17779 INFO mistral.nc_upgrade [-] PID: 13727; User: postgres (127.0.0.1:52230); Connected: 2018-11-29 11:27:42.638437+00:00
2018-11-29 14:29:06.676 17779 INFO mistral.nc_upgrade [-] PID: 13728; User: postgres (127.0.0.1:52232); Connected: 2018-11-29 11:27:42.651267+00:00
2018-11-29 14:29:06.676 17779 INFO mistral.nc_upgrade [-] PID: 13732; User: postgres (127.0.0.1:52236); Connected: 2018-11-29 11:29:06.670453+00:00

```

To resolve the problem, perfrom the following steps:

1. Check who is connected to the database right now. 
2. Make sure that you still want to clean this database.
3. To prevent the reconnects after dropping them down, use:   
`UPDATE pg_database SET datallowconn = false WHERE datname = 'DB_NAME';`
4. To drop these connections, use:   
`SELECT pg_terminate_backend(pg_stat_activity.pid) FROM pg_stat_activity WHERE pg_stat_activity.datname = 'DB_NAME' AND pid <> pg_backend_pid();`

# How to Clean Mistral Database

The below seb-sections provide infromation on how you can clean the mistral database.

## Full Cleanup

To perform the full cleanup, use the following SQL commands:
```
DELETE FROM workflow_executions_v2;
DELETE FROM task_executions_v2;
DELETE FROM action_executions_v2;

DELETE FROM delayed_calls_v2;
```

## Partial Cleanup

Sometimes, it is required to delete only old entities. To perform it, use the following command:

```
DELETE FROM workflow_executions_v2 WHERE updated_at<'2022-05-31 11:19:25';
```

## Trigger Postgres To Clean Disk Space

To ensure that the disc space was cleaned immidiately, you can trigger VACUUM command:

```
VACUUM FULL action_executions_v2;
VACUUM FULL task_executions_v2;
VACUUM FULL workflow_executions_v2;
```

# Monitoring Alarms Description

This section describes the different monitoring alarms in detail.

|Alarm|Possible Reasons|
|---|---|
|Mistral {service} down|All pods of mistral api/monitoring/engine/executor/notifier is down (0 available replicas).|

**Solution**:

All pods of mistral {service} are unavailable or scaled down (0 available replicas).

To resolve this alarm, perform the following steps:

1. Check if pods of mistral {service} is available and not scaled to 0.
2. Find and collect the logs from unavailable pods to see the root-cause of the problem.
3. Check if this problem is described in this guide.

|Alarm|Possible Reasons|
|---|---|
|Mistral {service} use 90% of CPU limit|Mean CPU usage of mistral pods is more than 90% of limit.|

**Solution**:

Mistral uses almost all CPU resources. This warning means that with a further increase in the load, delays in the work of the mistral are possible due to waiting for the CPU.
A possible solution may be to increase the number of replicas or increase the resources allocated to Mistral (CPU limit).

|Alarm|Possible Reasons|
|---|---|
|Mistral {service} use 90% of memory limit|Mean memory usage of mistral pods is more than 90% of limit.|

**Solution**:

Mistral used almost all the free memory, with a further increase in load, the work of the mistral can be slowed down due to lack of memory.
A possible solution could be to increase the number of replicas, or to increase the memory limit.

|Alarm|Possible Reasons|
|---|---|
|RabbitMQ connections down|RabbitMQ service is down or Mistral cannot establish connection to RabbitMQ.|

**Solution**:

To fix problems related to RabbitMQ, refer to the **RabbitMQ Troubleshooting** section in the _Cloud Platform Troubleshooting Guide_.
