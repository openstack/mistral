This guide covers the details about Workflow Service Installation.

It covers the following:

* [OpenShift Installation](#openshift-installation)
    * [Prerequisites](#prerequisites)
    * [Hardware Requirements](#hardware-requirements)
    * [Installation Process](#installation-process)
    * [Upgrade Mistral Database](#upgrade-mistral-database)

    <!-- #GFCFilterMarkerStart# -->    

    * [Manual Installation](#manual-installation)
    
    <!-- #GFCFilterMarkerEnd# -->

    * [DP Jobs](#dp-jobs)
    * [Tests](#tests)

<!-- #GFCFilterMarkerStart# -->
* [Local Installation](#local-installation)
    * [Required Software for Docker Compose](#required-software-for-docker-compose)
    * [Steps](#local-installation-steps)

<!-- #GFCFilterMarkerEnd# -->

# OpenShift Installation

The following sections provide OpenShift installation information. 

For more information about upgrade or install newer version instead of the older one, refer to [Mistral Service Upgrade](service_upgrade_guide.md).

## Prerequisites

Mistral service uses PostgreSQL database for persisting workflow state and message broker RabbitMQ for internal communication and external notification.
PostgreSQL and RabbitMQ shall be deployed and accessible in the cloud for successful Mistral service installation.

## Hardware Requirements

The minimum and recommended hardware requirements are given below.

### Minimum Hardware Requirements

The list of minimum hardware requirements is as follows:

|Mistral service|Limit main memory (MiB)|Limit CPU (millicores)|
|---|---|---|
|API|400|200|
|Engine|300|200|
|Executor|300|200|
|Notifier|300|100|
|Monitoring|300|100|

Mistral requires at least 1600 MiB of main memory and 1 core of CPU.

### Recommendations

The recommended hardware requirements are as follows:

|Mistral service|Limit main memory (MiB)|Limit CPU (millicores)|
|---|---|---|
|API|500|1000|
|Engine|500|1000|
|Executor|300|200|
|Notifier|300|200|
|Monitoring|300|100|

Mistral runs best with 1900 MiB of main memory and 2500 millicores of CPU.

Because of the Global Interpreter Lock mechanism used in Python, it is unnecessary to specify more than 1 CPU core per Mistral pod. It looks like workflows are still processed in one thread.

## Installation Process
    
This section describes the Mistral deployment process.

![Mistral Deploy Process](/custom_doc/img/mistral-deploy-process.png)

Log in to OpenShift. If there is an `OPENSHIFT_TOKEN` environment variable, then login is through the token. Otherwise, it uses the login and password.

Update or install from scratch - Determine whether to update or install from scratch. If the mistral-api DeploymentConfig is in an Openshift Project, then Mistral is updated. Otherwise, it is installed from scratch.

Create-Update PG and RabbitMQ secret - Remove the existing PostgreSQL and RabbitMQ secrets containing Mistral credentials.

<!-- #GFCFilterMarkerStart# -->
[Script](openshift/scripts/create_mistral_secrets.sh)
<!-- #GFCFilterMarkerEnd# -->
    
Update the Mistral Database - An OpenShift job for updating Mistral is deployed. 
Enter the PostgreSQL user and password. The database then tries to update schemas and tables.

<!-- #GFCFilterMarkerStart# -->
* [Deploy Update Job Script](openshift/scripts/update_db.sh)
* [Update Database OpenShift Job](openshift/template.update_db.json)

<!-- #GFCFilterMarkerEnd# -->

Deploy Mistral Services - Deploy the main Mistral services: API, Engine, and Executor.

<!-- #GFCFilterMarkerStart# -->
[Template of Mistral Services](openshift/template.json)
<!-- #GFCFilterMarkerEnd# -->

## Upgrade Mistral Database

The first step in deploying Mistral to OpenShift is to upgrade or create the database.

<!-- #GFCFilterMarkerStart# -->
[Source Script](config/upgrade_db.sh)
<!-- #GFCFilterMarkerEnd# -->

|Environment Variable Name|Description|
|---|---|
|PG_HOST|Postgres host|
|PG_PORT|Postgres port|
|PG_ADMIN_USER|User with the right to create databases|
|PG_ADMIN_PASSWORD|Password for user with the right to create databases|
|PG_USER|Mistral postgres user|
|PG_PASSWORD|Mistral postgres password|
|PG_DB_NAME|Mistral database name|

**Notes**:

* If the deployer job was launched with `DEPLOYMENT_MODE = clean` parameter, and Mistral multitenancy is disabled, Mistral database is cleared with `DROP DATABASE` statement.
* If the **$PG_DB_NAME** database does not exist, it is created automatically.
* If **$PG_USER** user does not exist, it is created. The created user only has login permissions.
* Set the database owner to the user.
* Upgrade the database to the latest version. For more information, refer to the _Official Mistral Documentation_ at [https://github.com/openstack/mistral/tree/master/mistral/db/sqlalchemy/migration/alembic_migrations](https://github.com/openstack/mistral/tree/master/mistral/db/sqlalchemy/migration/alembic_migrations).

<!-- #GFCFilterMarkerStart# -->  

## Manual Installation

The manual installation procedure is given below.

### Prerequisites

The prerequisites for manual installation are as follows:

* OpenShift CLI is installed
* PostgreSQL is deployed
* RabbitMQ is deployed

### Installation

Installation steps are as follows:

1. Override the Deploy parameters in the deployment script.
1. Execute the script.

[Deployment Script](deploy_manually.sh)

<!-- #GFCFilterMarkerEnd# -->


### Main Deploy Parameters

The following tables contain descriptions of deploy parameters.

**Note**: If you deploy Mistral in the same infrastructure (RabbitMQ, PostgreSQL) where there is the another Mistral, you must override the following parameters:

* `RABBIT_VHOST`
* `PG_DB_NAME`

To force redeploy the Mistral pods, add the `FORCE_REDEPLOY;` parameter in the `CUSTOM_PARAMS` section.

#### Deploy Configuration

The Deploy Configuration is as follows:

|Name|Default|Description|
|---|---|---|
|USE_PYPY|False|If it is set to `True`, then the API and engine works using PyPy.|
|DEPLOY_MISTRAL_UI|False|If it is set to `True`, then CloudFlow service is deployed.|
|DEPLOY_MODE|main|Deploy Mistral in `main` or `lite` mode.|
|INCLUDE_LOCAL_RMQ|False|If set to true `True`, then RabbitMQ in Mistral Lite pod is deployed.|
|MISTRAL_ROUTE_ENABLED|False|If set to `True`, then Route for Mistral Service will be created.|

<!-- #GFCFilterMarkerStart# -->
For more information, see [CloudFlow in User Guide](user.md#cloudflow) and [Mistral Deployment Configuration in User Guide](user.md#mistral-deployment-configuration).
<!-- #GFCFilterMarkerEnd# -->

#### Monitoring

The Monitoring details are as follows:

|Name|Required|Default|Description|
|---|---|---|---|
|MONITORING_ENABLED|No|False||
|MONITORING_EXECUTION_DELAY|No|600|How often monitoring execution occurs.|
|METRIC_COLLECTION_INTERVAL|No|30||

#### Mistral URLs

The Mistral URLs are as follows:

|Name|Default|Description|
|---|---|---|
|OS_MISTRAL_URL|```http://mistral.$(OPENSHIFT_WORKSPACE):8989/v2```|Internal Mistral URL|
|EXTERNAL_MISTRAL_URL|Default value is empty|External Mistral URL|

#### Authentication

Authentication details are as follows: 

|Name|Default|Description|
|---|---|---|
|SECURITY_PROFILE|dev|Security in actions: `dev` - disable, `prod` - enable|
|AUTH_ENABLE|False|Enable security in Mistral services|
|AUTH_TYPE|mitreid|`keystone`, `mitreid` or `keycloak-oidc`|
|IDP_SERVER| |Internal URL can be used to obtain a jwt token|
|IDP_EXTERNAL_SERVER| |External URL must be used to generate a client and secret|
|IDP_REGISTRATION_TOKEN| |Registration token|
|IDP_PROJECT| |IDP OpenShift project|

#### OpenShift

The OpenShift details are all optional.

|Name|Default|Description|
|---|---|---|
|OPENSHIFT_WORKSPACE|mistral|The OpenShift Project.|
|OPENSHIFT_LOGIN|admin|The OpenShift user.|
|OPENSHIFT_PASSWORD| |The OpenShift password.|
|OPENSHIFT_ACCOUNTSERVICE_TOKEN| |The service account token. If it is present, then the token is used instead of the login/password.|  

#### RabbitMQ

The RabbitMQ details are as follows:

|Name|Required|Default|Description|
|---|---|---|---|
|RABBIT_ADMIN_PASSWORD|Yes| |RabbitMQ admin password|
|RABBIT_ADMIN_USER|No|`guest`|RabbitMQ admin user|
|RABBIT_HOST|No|`rabbitmq.rabbitmq`|The RabbitMQ URL. Default value may be used if Mistral and RabbitMQ are deployed into one project 
|RABBIT_PORT|No|5672|The RabbitMQ port.|
|RABBIT_VHOST|No|`mistral_$(OPENSHIFT_WORKSPACE)`|The RabbitMQ vhost. **Important** With multiple Mistral installation on one RabbitMQ all Mistrals must be deployed to different vhosts|
|RABBIT_USER|No|`mistral_$(OPENSHIFT_WORKSPACE)_rabbit_user`|The RabbitMQ user is be generated if omitted.|
|RABBIT_PASSWORD|Yes| |The RabbitMQ password for RABBIT_USER.|
|QUEUE_NAME_PREFIX|No|Project name where Mistral was deployed|If two Mistral clusters have different `QUEUE_NAME_PREFIX`, they do not interact between each other.|

**Important** With multiple Mistral installation on one RabbitMQ all Mistrals must be deployed to different vhosts.

#### PostgreSQL

The PostgreSQL details are as follows:

|Name|Required|Default|Description|
|---|---|---|---|
|PG_ADMIN_PASSWORD|Yes|-|The PostgreSQL admin password that is used to create the Mistral database and the Mistral user.|
|PG_ADMIN_USER|No|`postgres`|The PostgreSQL admin user that is used to create the Mistral database and the Mistral user.|
|PG_HOST|No|`pg-common.postgres-service`|The PostgreSQL URL. Default value may be used if Mistral and PostgreSQL are deployed into one project.|
|PG_PORT|No|5432|The PostgreSQL port.|
|PG_DB_NAME|No|`mistral_$(OPENSHIFT_WORKSPACE)`|The PostgreSQL database that is used for Mistral services. Is generated if omitted.|
|PG_USER|No|`mistral_$(OPENSHIFT_WORKSPACE)_pg_user`|The PostgreSQL user that is used for Mistral services. Is generated if omitted.|
|PG_PASSWORD|Yes| |The PostgreSQL password for PG_USER.|

#### Configuration Limits for Main Deployment

The Configuration Limits are as follows:

|Name|Default|Description|
|---|---|---|
|ENGINE_CPU|200m|CPU limit for mistral-engine|
|ENGINE_MEMORY|300Mi|Memory limit for mistral-engine|
|ENGINE_REPLICAS|1|Default replicas for mistral-engine|
|EXECUTOR_CPU|200m|CPU limit for mistral-executor|
|EXECUTOR_MEMORY|300Mi|Memory limit for mistral-executor|
|EXECUTOR_REPLICAS|1|Default replicas for mistral-executor|
|API_CPU|200m|CPU limit for mistral-api|
|API_MEMORY|300Mi|Memory limit for mistral-api|
|API_REPLICAS|1|Default replicas for mistral-api|
|MONITORING_CPU|100m|CPU limit for mistral-monitoring|
|MONITORING_MEMORY|300Mi|Memory limit for mistral-monitoring|
|MONITORING_REPLICAS|1|Default replicas for mistral-monitoring|
|NOTIFIER_CPU|100m|CPU limit for mistral-notifier|
|NOTIFIER_MEMORY|300Mi|Memory limit for mistral-notifier|
|NOTIFIER_REPLICAS|1|Default replicas for mistral-notifier|
|DEFAULT_CPU|500|Default CPU limit for all configs|
|DEFAULT_MEMORY|600|Default memory limit for all configs|
|DEFAULT_REPLICAS|1|Default replicas for all configs|

#### Configuration Limits for Lite Deployment

The Configuration Limits are as follows:

|Name|Default|Description|
|---|---|---|
|LITE_CPU|300|CPU limit for a mistral container|
|LITE_MEMORY|300|Memory limit for a mistral container|
|RMQ_CPU|300|Memory limit for a RabbitMQ container|
|RMQ_MEMORY|300|Memory limit for a RabbitMQ container|

#### Recovery

The Recovery details are as follows:

|Name|Default|Description|
|---|---|---|
|RECOVERY_INTERVAL|30|The recovery job is triggered with this interval.|
|HANG_INTERVAL|300|Delayed calls are triggered updated with this interval.| 
|RECOVERY_ENABLED|True|If set to `True`, then recovery job is enabled.|
|RPC_IMPLEMENTATION|oslo|

#### Proxy

The Requests Python library proxy parameters could be configured as follows:

|Name|Default|Description|
|---|---|---|
|MISTRAL_HTTP_PROXY| |URL of HTTP proxy.|
|MISTRAL_HTTPS_PROXY| |URL of HTTPS proxy.| 
|MISTRAL_NO_PROXY| |List of URLs with which Requests library does not use proxy at all.|

For more information, refer to the Requests library docs.

#### Debug

The Debug details are as follows:

|Name|Default|Description|
|---|---|---|
|DEBUG_LOG|False|Enables debug logging.|

#### Pod Anti-Affinity

The Pod Affinity details are as follows:

|Name|Default|Description|
|---|---|---|
|TOPOLOGY_KEY|kubernetes.io/hostname|The key for the node label that the system uses to denote a topology domain.|
|POD_AFFINITY_TERM|preferred|Severity of the anti-affinity. The `required` value allows only one pod to be scheduled in one topology domain. The `preferred` value allows several pods to be scheduled in one topology domain.|

#### Kafka Notifications

Notifications based on Kafka could be configured as follows:

|Name|Default|Description|
|---|---|---|
|KAFKA_NOTIFICATIONS_ENABLED| False |If set to `True`, then Kafka notifications are enabled.|
|KAFKA_HOST| 0.0.0.0 |Kafka's host url.|
|KAFKA_TOPIC| mistral_notifications |Kafka's topic to store notifications.|
|KAFKA_TOPIC_PARTITIONS_COUNT| 2 |Kafka's topic partitions count.|
|KAFKA_CONSUMER_GROUP_ID| notification_consumer_group |Kafka's consumer group id.|
|KAFKA_SECURITY_ENABLED| False |If set to `True`, then Mistral will use credentials to connect to Kafka.|
|KAFKA_SASL_PLAIN_USERNAME| |Kafka's plain username.|
|KAFKA_SASL_PLAIN_PASSWORD| |Kafka's plain password.|

#### Custom init script

The custom init script details are as follows:

|Name|Default|Description|
|---|---|---|
|CUSTOM_INIT_SCRIPT_PATH| |Path to the custom init script.|

#### Custom init script

The custom init script details are as follows:

|Name|Default|Description|
|---|---|---|
|CUSTOM_INIT_SCRIPT_PATH| |Path to the custom init script.|

#### Common Custom Parameters

Common custom parameters could be configured as follows:

|Group|Name|Default|Description|
|---|---|---|---|
|DEFAULT|rpc_response_timeout|90|The RPC response timeout, specifies a waiting time for the RPC response
|engine|merge_strategy|replace|Merge strategy of data inside workflow execution
|engine|execution_field_size_limit_kb|1024|The default maximum size in KB of large text fields of runtime execution objects. Use -1 for no limit.

Common custom parameters should be placed in the `custom-mistral.conf` under the respective groups such as DEFAULT, engine, and so on.

`custom-mistral.conf` example:
<pre>
[DEFAULT]
rpc_response_timeout = 90

[engine]
merge_strategy = replace
execution_field_size_limit_kb = 1024
</pre>

**Important:** Parameters belonging to the same group should be placed under single group of parameters.

#### Minimal Set of Parameters

The minimal set of required parameters contains 4 elements which are passwords for infrastructure services (values are exemplary):

<pre>
RABBIT_ADMIN_PASSWORD=rabbit_password;
RABBIT_PASSWORD=mistral_rabbit_password;

PG_ADMIN_PASSWORD=postgres_password;
PG_PASSWORD=mistral_pg_password;
</pre>

RabbitMQ and PostgreSQL host names may be omitted. Default host names are used:
<pre>
RABBIT_HOST=rabbitmq.rabbitmq;
PG_HOST=pg-common.postgres-service;
</pre>

RabbitMQ and PostgreSQL admin users have default values but still may be overriden:
<pre>
RABBIT_ADMIN_USER=guest;
PG_ADMIN_USER=postgres;
</pre>

The following four parameters are generated if not specified before installation:
<pre>
RABBIT_USER=mistral_$(OPENSHIFT_WORKSPACE)_rabbit_user;
RABBIT_VHOST=mistral_$(OPENSHIFT_WORKSPACE);

PG_USER=mistral_$(OPENSHIFT_WORKSPACE)_pg_user;
PG_DB_NAME=mistral_$(OPENSHIFT_WORKSPACE);
</pre>

#### All Parameters

The list of all parameters with their exemplary values is as follows:

<pre>

RABBIT_ADMIN_USER=guest;
RABBIT_ADMIN_PASSWORD=guest;
RABBIT_USER=mistral-rabbit-user;
RABBIT_PASSWORD=mistral-rabbit-password;

RABBIT_VHOST=mistral_{!!e.g. project_name!!};
RABBIT_HOST=rabbitmq;
RABBIT_PORT=5672;

SECURITY_PROFILE=dev;
AUTH_ENABLE=False;
AUTH_TYPE=mitreid;
IDP_SERVER=```http://idp.security-services```;
IDP_EXTERNAL_SERVER=```http://idp.security-services.openshift.com```;
IDP_REGISTRATION_TOKEN=default_client_registration_secret;
IDP_PROJECT=security-services;

PG_ADMIN_USER=postgres;
PG_ADMIN_PASSWORD=postgres;
PG_USER=mistral_test_user;
PG_PASSWORD=mistral_test_password;

PG_DB_NAME=mistral_{!!e.g. project_name!!};
PG_HOST=pg-common.pg-service;
PG_PORT=5432;

MONITORING_ENABLED=False;
MONITORING_EXECUTION_DELAY=100;
METRIC_COLLECTION_INTERVAL=30;

RECOVERY_INTERVAL=30;
HANG_INTERVAL=300;
RECOVERY_ENABLED=True;

ENGINE_CPU=200m;
ENGINE_MEMORY=300Mi;
ENGINE_REPLICAS=1;
EXECUTOR_CPU=200m;
EXECUTOR_MEMORY=300Mi;
EXECUTOR_REPLICAS=1;
API_CPU=200m;
API_MEMORY=300Mi;
API_REPLICAS=1;
MONITORING_CPU=100m;
MONITORING_MEMORY=300Mi;
MONITORING_REPLICAS=1;
NOTIFIER_CPU=100m;
NOTIFIER_MEMORY=300Mi;
NOTIFIER_REPLICAS=1;
DEFAULT_CPU=500m;
DEFAULT_MEMORY=500Mi;
DEFAULT_REPLICAS=1;
LITE_CPU=300m;
LITE_MEMORY=300Mi;
INCLUDE_LOCAL_RMQ=false;
RMQ_CPU=300m;
RMQ_MEMORY=300Mi;
RABBIT_IMAGE=rabbit_image:latest;

DEBUG_LOG=False;
USE_PYPY=False;
DEPLOY_MISTRAL_UI=False;
DEPLOY_MODE=main;
RPC_IMPLEMENTATION=oslo;

OS_MISTRAL_URL=;
EXTERNAL_MISTRAL_URL=;

KAFKA_NOTIFICATIONS_ENABLED=False;
KAFKA_HOST=0.0.0.0;
KAFKA_TOPIC=mistral_notifications;
KAFKA_CONSUMER_GROUP_ID=notification_consumer_group;
KAFKA_SECURITY_ENABLED=False;
KAFKA_SASL_PLAIN_USERNAME=username;
KAFKA_SASL_PLAIN_PASSWORD=password;

TOPOLOGY_KEY=kubernetes.io/hostname;
POD_AFFINITY_TERM=preferred;

CERTIFICATE_STORE=```http://certificate-store```;
RETRIEVER_PORT=8777;
LOGGING_PROXY_ADMIN_URL=``;
</pre>

#### Tests

# Local Installation

The Local Installation details are given below.

## Required Software for Docker Compose

Virtual machine with Docker, Docker Compose.

OR

Docker for Windows. For more information, refer to the _Official Docker Documentation_, "Docker for Windows" [https://docs.docker.com/docker-for-windows](https://docs.docker.com/docker-for-windows).

## Local Installation Steps

The necessary steps for local installation are as follows:

* Clone Mistral from the Git repository [https://github.com/Netcracker/qubership-mistral](https://github.com/Netcracker/qubership-mistral).
* Move to the Mistral root directory. For example, **cd Mistral**.
* Select the correct branch.
* Build the Mistral Docker image: `docker build --network host -t dp-mistral .`. The first attempt might take some time.
* To launch Mistral, execute the following command: `docker-compose -f tools/docker-compose/docker-compose-all-in-one.yaml up -d`.
* To stop Mistral, execute the following: `docker-compose -f tools/docker-compose/docker-compose-all-in-one.yaml down`.
