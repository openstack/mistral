This chapter describes the prerequisites, best practices, parameters, and procedures used to install Mistral Operator.

<!-- #GFCFilterMarkerStart# -->
[[_TOC_]]
<!-- #GFCFilterMarkerEnd# -->

# Prerequisites

The prerequisites are as follows:

## Common

The prerequisites for deployment of Mistral using Operator are described in the following sections.

For successful Mistral installation, you need RabbitMQ and Postgres services up and running.

For Mistral lite with local RabbitMQ container, you need only the Postgres service.

## Kubernetes

If it is required to deploy two Mistral with different versions on one cloud, choose the CRD from Mistral with the highest version.

### Additional Prerequisites for Restricted Environment

If Mistral is installed to the cloud with security restrictions and/or a deploy user has no access to cluster wide resources, the following prerequisites must be met:

* CRD must be installed to the environment.
* Specific rules must be enabled in the Mistral namespace for the deploy user and can be done by applying the following templates:

  ```yaml
  kind: Role
  apiVersion: rbac.authorization.k8s.io/v1
  metadata:
    namespace: mistral-namespace
    name: deploy-user-role
  rules:
  - apiGroups:
    - qubership.org
    resources:
    - "*"
    verbs:
    - create
    - get
    - list
    - patch
    - update
    - watch
    - delete
  - apiGroups:
    - ""
    resources:
    - pods
    - services
    - events
    - configmaps
    - secrets
    - pods/exec
    - pods/portforward
    - pods/attach
    - pods/log
    - serviceaccounts
    - namespaces
    verbs:
    - create
    - get
    - list
    - patch
    - update
    - watch
    - delete
  - apiGroups:
    - apps
    - extensions
    resources:
    - deployments
    verbs:
    - create
    - get
    - list
    - patch
    - update
    - watch
    - delete
  - apiGroups:
    - apps.openshift.io
    resources:
    - deploymentconfigs
    verbs:
    - create
    - get
    - list
    - patch
    - update
    - watch
    - delete
  - apiGroups:
    - rbac.authorization.k8s.io
    resources:
    - rolebindings
    - roles
    verbs:
    - create
    - get
    - list
    - patch
    - update
    - watch
    - delete
  - apiGroups:
    - batch
    resources:
    - jobs
    verbs:
    - create
    - get
    - list
    - patch
    - update
    - watch
    - delete
  - apiGroups:
    - apps
    resources:
    - deployments/status
    - deployments/scale
    verbs:
    - create
    - get
    - list
    - patch
    - update
    - watch
    - delete
  - apiGroups:
    - networking.k8s.io
    resources:
    - ingresses
    verbs:
    - create
    - get
    - list
    - patch
    - update
    - watch
    - delete
  ```

  ```yaml
  kind: RoleBinding
  apiVersion: rbac.authorization.k8s.io/v1
  metadata:
      name: deploy-user-role-binding
      namespace: mistral-namespace
  subjects:
    - kind: User
      name: deploy-user
  roleRef:
      apiGroup: rbac.authorization.k8s.io
      name: deploy-user-role
      kind: Role
  ```

For integration with NC Monitoring, ensure that NC Monitoring is installed in the cluster and the cluster has monitoring entities defined CRDs for ServiceMonitor, PrometheusRule, and GrafanaDashboard. In this case, the rules are mentioned above the grant permissions for monitoring entities. However, permissions for monitoring entities can be added separately later if required. For example:

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: prometheus-monitored
rules:
- apiGroups:
  - monitoring.coreos.com
  resources:
  - servicemonitors
  - prometheusrules
  - podmonitors
  verbs:
  - create
  - get
  - list
  - patch
  - update
  - watch
  - delete
- apiGroups:
  - integreatly.org
  resources:
  - grafanadashboards
  verbs:
  - create
  - get
  - list
  - patch
  - update
  - watch
  - delete
```

and

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
    name: prometheus-monitored
    namespace: mistral-namespace
roleRef:
    apiGroup: rbac.authorization.k8s.io
    kind: Role
    name: prometheus-monitored
subjects:
- kind: User
  name: deploy-user
```

# Best Practices and Recommendations

The best practices and recommendations are given below.

## HWE

The hardware details are specified in the below sections.

### Small

Recommended for development purposes, PoC, and demos.

|Mistral service|CPU    |RAM, Gi|Replicas|
|---------------|-------|-------|--------|
|API            |0.5    |0.5    |1       |
|Engine         |1      |1      |1       |
|Executor       |0.5    |0.5    |1       |
|Notifier       |0.5    |0.5    |1       |
|Monitoring     |0.5    |0.5    |1       |
|**Total**      |**3**  |**3**  |        |

### Medium

Recommended for deployments with average load. For example, if you have a lot of small parallel running executions.

|Mistral service|CPU    |RAM, Gi|Replicas|
|---------------|-------|-------|--------|
|API            |0.5    |0.5    |2       |
|Engine         |1      |1      |2       |
|Executor       |0.5    |0.5    |2       |
|Notifier       |0.5    |0.5    |2       |
|Monitoring     |0.5    |0.5    |1       |
|**Total**      |**6**  |**6**  |        |

### Large

Recommended for deployments with high workload and a large amount of data. For example, if you have heavy and huge workflows.

|Mistral service|CPU    |RAM, Gi|Replicas|
|---------------|-------|-------|--------|
|API            |1      |1      |2       |
|Engine         |1      |2      |4       |
|Executor       |1      |1      |4       |
|Notifier       |0.5    |0.5    |4       |
|Monitoring     |0.5    |0.5    |1       |
|**Total**      |**6**  |**6**  |        |

# Parameters

The different parameteres are described below.

## General Parameters

The general parameters used for the configurations are specified in the following table.

|Parameter   |Type  |Mandatory| Default value                 |Description                                                        |
|------------|------|---------|-------------------------------|-------------------------------------------------------------------|
|mistral.dockerImage     |string|yes      |                               |This parameter specifies the Mistral image.|
|mistralCommonParams.debugLog|bool|no| 'False'                       |This parameter specifies whether the debug log is enabled.|
|mistralCommonParams.postgres.host|string|yes| 'pg-patroni.postgres-service' |This parameter specifies the Postrges host.|
|mistralCommonParams.postgres.port|int|yes| 5432                          |This parameter specifies the Postgres port.|
|mistralCommonParams.postgres.dbName|string|yes| 'mistral'                     |This parameter specifies the Postgres database name.|
|mistralCommonParams.postgres.idleTimeout|string|yes| '30s'                         | This parameter specifies the timeout for queries in state idle in transaction session. Use '0' as value to disable the timeout. |
|secrets.pgAdminPassword|string|yes| ''                            |This parameter specifies the Postgres admin password.|
|secrets.pgAdminUser|string|yes| 'postgres'                    |This parameter specifies the Postgres admin user.|
|secrets.pgPassword|string|yes| 'mistral_password'            |This parameter specifies the Postgres password.|
|secrets.pgUser|string|yes| 'mistral_user'                |This parameter specifies the Postgres user.|
|mistralCommonParams.rabbit.host|string|yes| 'rabbitmq.rabbitmq'           |This parameter specifies the RabbitMQ host.|
|mistralCommonParams.rabbit.port|int|yes| 5672                          |This parameter specifies the RabbitMQ port.|
|mistralCommonParams.rabbit.vhost|string|yes| '/'                           |This parameter specifies the RabbitMQ virtual host.|
|mistralCommonParams.queueNamePrefix|string|no| 'mistral'                     |This parameter specifies the RabbitMQ queue name prefix.|
|secrets.rabbitAdminPassword|string|yes| 'admin'                       |This parameter specifies the RabbitMQ admin password.|
|secrets.rabbitAdminUser|string|yes| 'admin'                       |This parameter specifies the RabbitMQ admin user.|
|secrets.rabbitPassword|string|yes| 'mistral_password'            |This parameter specifies the RabbitMQ password.|
|secrets.rabbitUser|string|yes| 'mistral_user'                |This parameter specifies the RabbitMQ user.|
|mistralCommonParams.securityProfile|string|no| prod                          |This parameter specifies the security profile.|
|mistralCommonParams.cleanup|bool|no| ''                            |This Parameter Allows deploy Mistral with cleaning up DB, Kafka topic and Rabbit|
|mistralCustomParams|string|no| ''                            |This parameter specifies the Mistral custom parameters config map (**custom-mistral.conf**).|
|mistralCustomApiParams|string|no| ''                            |This parameter specifies the Mistral API custom parameters config map (**custom-mistral.conf**).|
|mistralCustomEngineParams |string|no| ''                            |This parameter specifies the Mistral Engine custom parameters config map (**custom-mistral.conf**).|
|mistralCustomExecutorParams |string|no| ''                            |This parameter specifies the Mistral Executor custom parameters config map (**custom-mistral.conf**).|
|mistralCustomNotifierParams |string|no| ''                            |This parameter specifies the Mistral Notifier custom parameters config map (**custom-mistral.conf**).|
|mistral.disruptionBudget.enabled       |bool   |no       | false                         |Enable PodDisruptionBudget for Mistral pods.                             |
|mistral.disruptionBudget.maxUnavailable|int    |no       | 0                             |The maximal number of pods that can be unavailable after the eviction.    |
|mistral.disruptionBudget.minAvailable  |int    |no       | 0                             |The minimal number of pods that must be available after the eviction.     |

**Note**: If you want to deploy Mistral's manifest and use a different Mistral's docker image, use `mistralImage` instead of `mistral.dockerImage`.

## Mistral Ingress Parameters

The Mistral Ingress parameters used for the configurations are specified in the following table.

|Parameter   |Type  |Mandatory|Default value|Description                                                        |
|------------|------|---------|-------------|-------------------------------------------------------------------|
|mistral.ingress.enabled|bool|no|'False'|This parameter enables Mistral ingress creation.|
|mistral.ingress.host|string|no|""|This parameter specifies the name of the external Mistral host. It must be complex and unique enough not to intersect with other possible external host names. For example, to generate the value for this parameter, use the OpenShift/Kubernetes host: If the URL to OpenShift/Kubernetes is https://example.com:8443 and the namespace is mistral-service, the host name for Mistral can be mistral-mistral-service.example.com. After the deployment is completed, you can access Mistral using the https://mistral-mistral-service.example.com URL.|

## Mistral Authentication Parameters

The Mistral Authentication parameters used for the configurations are specified in the following table.

|Parameter   |Type  |Mandatory|Default value|Description                                                        |
|------------|------|---------|-------------|-------------------------------------------------------------------|
|mistralCommonParams.auth.enable|bool|no|'False'|This parameter specifies whether authentication is enabled.|
|mistralCommonParams.auth.type|string|no|'mitreid'|This parameter specifies the authentication type.|
|mistralCommonParams.auth.certs|string|no|''|This parameter specifies the certificate to verify idpExternalServer.|
|mistralCommonParams.idpServer|string|no|''|This parameter specifies the IDP server.|
|mistralCommonParams.idpExternalServer|string|no|''|This parameter specifies the IDP external server.|
|mistralCommonParams.idpUserPrecreated|bool|no|'False'|This parameter specifies whether Mistral should use a precreated user with credentials stored in a specific secret, `idp-precreated-user`, with the `idp-client-id` and `idp-client-secret` fields.|
|secrets.idpRegistrationToken|string|no|'null'|This parameter specifies the IDP registration token.|
|secrets.idpClientId|string|no|'null'|This parameter specifies the IDP client ID.|
|secrets.idpClientSecret|string|no|'null'|This parameter specifies the IDP client secret.|
|secrets.idpJwkExp|string|no|'null'|This parameter specifies IDP JWK exp.|
|secrets.idpJwkMod|string|no|'null'|This parameter specifies IDP JWK mod.|

## Kafka Notification Parameters

The Kafka Notification parameters used for the configurations are specified in the following table.

|Parameter   |Type  |Mandatory|Default value|Description                                                        |
|------------|------|---------|-------------|-------------------------------------------------------------------|
|mistralCommonParams.kafkaNotifications.enabled|bool|no|False|This parameter enables notifications through Kafka.|
|mistralCommonParams.kafkaNotifications.host|string|no|'0.0.0.0'|This parameter specifies the Kafka URL.|
|mistralCommonParams.kafkaNotifications.topic|string|no|`mistral_notifications`|This parameter specifies the Kafka topic name.|
|mistralCommonParams.kafkaNotifications.topicPartitionsCount|int|no|2|This parameter specifies the Kafka topic partitions' count.|
|mistralCommonParams.kafkaNotifications.consumerGroupId|string|no|`notification_consumer_group`|This parameter specifies the Kafka consumer group ID.|
|mistralCommonParams.kafkaNotifications.securityEnabled|bool|no|`False`|This parameter specifies the connection to Kafka with enabled security.|
|secrets.kafkaSaslPlainUsername|string|no|'username'|This parameter specifies the Kafka username.|
|secrets.kafkaSaslPlainPassword|string|no|'password'|This parameter specifies the Kafka password.|

## Horizontal Pod Autoscalers Parameters

The Horizontal Pod Autoscalers parameters are as follows:

**Note**: API metrics need to be installed on k8s cluster.

|Parameter   |Type  |Mandatory|Default value|Description                                                        |
|------------|------|---------|-------------|-------------------------------------------------------------------|
|HPA_ENABLED|bool|no|False|Boolean value to enable or disable HPA.|
|HPA_MIN_REPLICAS|int|no|1|Minimum number of replicas the deployment should scale down to.|
|HPA_MAX_REPLICAS|int|no|3|Maximum number of replicas the deployment should scale up to.|
|HPA_AVG_CPU_UTILIZATION|int|no|85|Target average CPU utilization (percentage) across all pods.|
|HPA_SCALING_UP_PERCENT|int|no|95|Percentage increase in the number of replicas when scaling up.|
|HPA_SCALING_UP_INTERVAL|int|no|120|Time interval (in seconds) for stabilization when scaling up.|
|HPA_SCALING_DOWN_PERCENT|int|no|25|Percentage decrease in the number of replicas when scaling down.|
|HPA_SCALING_DOWN_INTERVAL|int|no|300|Time interval (in seconds) for stabilization when scaling down.|

## Mistral API Parameters

The Mistral API parameters are specified below.

|Parameter   |Type  |Mandatory|Default value|Description                                                        |
|------------|------|---------|-------------|-------------------------------------------------------------------|
|mistralApi.replicas|int|no|1|This parameter specifies the number of Mistral-api replicas.|
|mistralApi.resources.requests.cpu|string|no|500m|This parameter specifies the requested CPU for Mistral-api.|
|mistralApi.resources.requests.memory|string|no|500Mi|This parameter specifies the requested memory for Mistral-api.|
|mistralApi.resources.limits.cpu|string|no|500m|This parameter specifies the CPU limit for Mistral-api.|
|mistralApi.resources.limits.memory|string|no|500Mi|This parameter specifies the memory limit for Mistral-api.|
|mistralApi.affinity|json|no||(**Optional**) This parameters specifies the affinity scheduling rules.|
|mistralApi.priorityClassName|string|no|""|The priority class to be used to assign priority to Mistral Api pod. Priority class should be created beforehand. For more information, refer to https://kubernetes.io/docs/concepts/configuration/pod-priority-preemption/.|

## Mistral Monitoring Parameters

The Mistral Monitoring parameters are specified below.

|Parameter   |Type  |Mandatory|Default value|Description                                                        |
|------------|------|---------|-------------|-------------------------------------------------------------------|
|mistralMonitoring.replicas|int|no|1|This parameter specifies the number of Mistral-monitoring replicas.|
|mistralMonitoring.resources.requests.cpu|string|no|500m|This parameter specifies the requested CPU for Mistral-monitoring.|
|mistralMonitoring.resources.requests.memory|string|no|500Mi|This parameter specifies the requested memory for Mistral-monitoring.|
|mistralMonitoring.resources.limits.cpu|string|no|500m|This parameter specifies the CPU limit for Mistral-monitoring.|
|mistralMonitoring.resources.limits.memory|string|no|500Mi|This parameter specifies the memory limit for Mistral-monitoring.|
|mistralMonitoring.affinity|json|no||(**Optional**) This parameter specifies the affinity scheduling rules.|
|mistralMonitoring.recoveryInterval|int|no|'30'|This parameter specifies the monitoring recovery interval.|
|mistralMonitoring.hangInterval|int|no|'300'|This parameter specifies the monitoring hang interval.|
|mistralMonitoring.recoveryEnabled|bool|no|'True'|This parameter specifies whether monitoring recovery is enabled.|
|mistralMonitoring.monitoringExecutionDelay|int|no|'600'|This parameter specifies the monitoring execution delay.|
|mistralMonitoring.prometheusEnabled|bool|no|false|This parameter specifies whether Prometheus monitoring is enabled.|
|mistralMonitoring.metricCollectionInterval|int|no|'30'|This parameter specifies the metric collection interval.|
|mistralMonitoring.priorityClassName|string|no|""|The priority class to be used to assign priority to Mistral Monitoring pod. Priority class should be created beforehand. For more information, refer to https://kubernetes.io/docs/concepts/configuration/pod-priority-preemption/.|

## Mistral Executor Parameters

The Mistral Executor parameters are specified below.

|Parameter   |Type  |Mandatory|Default value|Description                                                        |
|------------|------|---------|-------------|-------------------------------------------------------------------|
|mistralExecutor.replicas|int|no|1|This parameter specifies the number of Mistral-executor replicas.|
|mistralExecutor.resources.requests.cpu|string|no|500m|This parameter specifies the requested CPU for Mistral-executor.|
|mistralExecutor.resources.requests.memory|string|no|500Mi|This parameter specifies the requested memory for Mistral-executor.|
|mistralExecutor.resources.limits.cpu|string|no|500m|This parameter specifies the CPU limit for Mistral-executor.|
|mistralExecutor.resources.limits.memory|string|no|500Mi|This parameter specifies the memory limit for Mistral-executor.|
|mistralExecutor.affinity|json|no||(**Optional**) This parameter specifies the affinity scheduling rules.|
|mistralExecutor.loggingProxyAdminUrl|string|no|''|This parameter specifies the executor logging proxy admin URL.|
|mistralExecutor.certificateStore|string|no|```http://certificate-store:8080```|This parameter specifies the executor certificate store.|
|mistralExecutor.retrieverPort|int|no|'8777'|This parameter specifies the executor retriever port.|
|mistralExecutor.httpProxy|string|no|''|This parameter specifies the HTTP proxy.|
|mistralExecutor.httpsProxy|string|no|''|This parameter specifies the HTTPS proxy.|
|mistralExecutor.noProxy|string|no|''|This parameter specifies that no proxy should be used.|
|mistralExecutor.priorityClassName|string|no|""|The priority class to be used to assign priority to Mistral Executor pod. Priority class should be created beforehand. For more information, refer to https://kubernetes.io/docs/concepts/configuration/pod-priority-preemption/.|

## Mistral Engine Parameters

The Mistral Engine parameters are specified below.

|Parameter   |Type  |Mandatory|Default value|Description                                                        |
|------------|------|---------|-------------|-------------------------------------------------------------------|
|mistralEngine.replicas|int|no|1|This parameter specifies the number of Mistral-engine replicas.|
|mistralEngine.resources.requests.cpu|string|no|1|This parameter specifies the requested CPU for Mistral-engine.|
|mistralEngine.resources.requests.memory|string|no|1Gi|This parameter specifies the requested memory for Mistral-engine.|
|mistralEngine.resources.limits.cpu|string|no|1|This parameter specifies the CPU limit for Mistral-engine.|
|mistralEngine.resources.limits.memory|string|no|1Gi|This parameter specifies the memory limit for Mistral-engine.|
|mistralEngine.affinity|json|no||(**Optional**) This parameter specifies the affinity scheduling rules.|
|mistralEngine.priorityClassName|string|no|""|The priority class to be used to assign priority to Mistral Engine pod. Priority class should be created beforehand. For more information, refer to https://kubernetes.io/docs/concepts/configuration/pod-priority-preemption/.|

## Mistral Notifier Parameters

The Mistral Notifier parameters are specified below.

|Parameter   |Type  |Mandatory|Default value|Description                                                        |
|------------|------|---------|-------------|-------------------------------------------------------------------|
|mistralNotifier.replicas|int|no|1|This parameter specifies the number of Mistral-notifier replicas.|
|mistralNotifier.resources.requests.cpu|string|no|500m|This parameter specifies the requested CPU for Mistral-notifier.|
|mistralNotifier.resources.requests.memory|string|no|500Mi|This parameter specifies the requested memory for Mistral-notifier.|
|mistralNotifier.resources.limits.cpu|string|no|500m|This parameter specifies the CPU limit for Mistral-notifier.|
|mistralNotifier.resources.limits.memory|string|no|500Mi|This parameter specifies the memory limit for Mistral-notifier.|
|mistralNotifier.affinity|json|no||(**Optional**) This parameter specifies the affinity scheduling rules.|
|mistralNotifier.priorityClassName|string|no|""|The priority class to be used to assign priority to Mistral Notifier pod. Priority class should be created beforehand. For more information, refer to https://kubernetes.io/docs/concepts/configuration/pod-priority-preemption/.|

## Mistral UpdateDB Pod parameters

The Mistral UpdateDB Pod parameters are specified below.

|Parameter   |Type  |Mandatory|Default value|Description                                                        |
|------------|------|---------|-------------|-------------------------------------------------------------------|
|mistralUpdateDbPod.memoryLimit|string|no|300Mi|This parameter specifies the update-db pod memory limit.|
|mistralUpdateDbPod.mountConfigsHome|string|no|'/opt/mistral/mount_configs'|This parameter specifies the mount configs home.|
|mistralUpdateDbPod.args|string|no|'./upgrade_db.sh'|This parameter specifies the db-pod args.|
|mistralUpdateDbPod.priorityClassName|string|no|""|The priority class to be used to assign priority to Mistral Upgrade DB pod. Priority class should be created beforehand. For more information, refer to https://kubernetes.io/docs/concepts/configuration/pod-priority-preemption/.|

## Mistral Lite Parameters

The Mistral Lite parameters are specified below.

|Parameter   |Type  |Mandatory|Default value|Description                                                        |
|------------|------|---------|-------------|-------------------------------------------------------------------|
|mistral.liteEnabled|bool|no|false|This parameter specifies whether lite deployment is enabled.|
|mistralLite.includeLocalRmq|bool|no|false|This parameter specifies whether RabbitMQ inside Mistral pod is enabled.|
|mistralLite.resources.requests.cpu|string|no|500m|This parameter specifies the requested CPU for Mistral-lite.|
|mistralLite.resources.requests.memory|string|no|500Mi|This parameter specifies the requested memory for Mistral-lite.|
|mistralLite.resources.limits.cpu|string|no|500m|This parameter specifies the CPU limit for Mistral-lite.|
|mistralLite.resources.limits.memory|string|no|500Mi|This parameter specifies the memory limit for Mistral-lite.|
|mistralLite.rabbitmq.dockerImage|string|no|"ghcr.io/netcracker/qubership-rabbitmq"|This parameter specifies the RabbitMQ docker image.|
|mistralLite.rabbitmq.resources.cpu|string|no|300m|This parameter specifies the RabbitMQ CPU.|
|mistralLite.rabbitmq.resources.memory|string|no|300Mi|This parameter specifies the RabbitMQ memory.|
|mistralLite.rabbitmq.fsGroup|int|no||This parameter specifies the configuration of security context for a pod.|
|mistralLite.rabbitmq.runAsUser|int|no||This parameter specifies user IDs to run processes in a pod.|
|mistralLite.priorityClassName|string|no|""|The priority class to be used to assign priority to Mistral pod when mistal lite is enabled. Priority class should be created beforehand. For more information, refer to https://kubernetes.io/docs/concepts/configuration/pod-priority-preemption/.|

## Mistral Operator Parameters

The Mistral Operator parameters are as follows:

|Parameter   | Type   |Mandatory|Default value|Description                                                        |
|------------|--------|---------|-----------|-------------------------------------------------------------------|
|operatorImage| string |yes|image included in the manifest|This parameter specifies the Mistral Operator image.|
|operator.imagePullPolicy| string |no|IfNotPresent|This parameter specifies the operator imagePullPolicy.|
|operator.resources.requests.cpu| string |no|100m|This parameter specifies the requested CPU for operator.|
|operator.resources.requests.memory| string |no|100Mi|This parameter specifies the requested memory for the operator.|
|operator.resources.limits.cpu| string |no|100m|This parameter specifies the CPU limit for the operator.|
|operator.resources.limits.memory| string |no|300Mi|This parameter specifies the memory limit for the operator.|
|operator.affinity    | json    |no||(**Optional**) This parameter specifies affinity rules for the operator.|
|operator.priorityClassName| string |no|""|The priority class to be used to assign priority to Mistral Operator pod. Priority class should be created beforehand. For more information, refer to https://kubernetes.io/docs/concepts/configuration/pod-priority-preemption/.|
|labels| yaml   |no|''|This parameter specifies additional labels for all pods, including mistral operator.|

## Disaster Recovery Parameters

The Disaster Recovery parameters are as follows:

| Parameter                                        | Type    | Mandatory | Default value            | Description                                                                                                                                                                                                                                                                                                          |
|--------------------------------------------------|---------|-----------|--------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| disasterRecovery.image                           | string  | no        | Calculates automatically | The Disaster Recovery Mistral operator container image.                                                                                                                                                                                                                                                        |
| disasterRecovery.siteManagerEnabled              | boolean | no        | true                     | Whether to use Site Manager.                                                                                                                                                                                                                                                                                         |
| disasterRecovery.timeout                         | int     | no        | 360                      | Specifies the fallback timeout permissible for services to come up when switching between active and stand-by deployment.                                                                                                                                                                                     |
| disasterRecovery.httpAuth.enabled                | boolean | no        | false                    | Specifies if authentication should be enabled or not                                                                                                                                                                                                                                                                 |
| disasterRecovery.httpAuth.smSecureAuth           | boolean | no        | false                    | Whether the `smSecureAuth` mode is enabled for Site Manager or not.                                                                                                                                                                                                                                                  |
| disasterRecovery.httpAuth.smNamespace            | string  | no        | site-manager             | The name of Kubernetes Namespace from which site manager API calls will be done.                                                                                                                                                                                                                                     |
| disasterRecovery.httpAuth.smServiceAccountName   | string  | no        | sm-auth-sa               | The name of Kubernetes Service Account under which site manager API calls will be done.                                                                                                                                                                                                                              |
| disasterRecovery.httpAuth.customAudience         | string  | no        | sm-services              | The name of custom audience for rest api token, that is used to connect with services. It is necessary if Site Manager installed with `smSecureAuth=true` and has applied custom audience (`sm-services` by default). It is considered if `disasterRecovery.httpAuth.smSecureAuth` parameter is set to `true` |
| disasterRecovery.httpAuth.restrictedEnvironment  | boolean | no        | false                    | If the parameter is `true` the `system:auth-delegator` cluster role will be bound to Misral operator service account. The cluster role will be not bound if the disaster recovery mode is disabled, or the disaster recovery server authentication is disabled.                                               |
| disasterRecovery.mode                            | string  | no        | ""                       | Specifies whether the current side is active during service installation in Disaster Recovery mode. If you do not specify this parameter, the service is deployed in a regular mode, not Disaster Recovery mode.                                                                                                     |
| disasterRecovery.afterServices                   | list    | no        | []                       | The list of `SiteManager` names for services after which the Mistral switchover is to be run.                                                                                                                                                                                                                  |
| disasterRecovery.resources.requests.cpu          | string  | no        | 10m                      | The minimum number of CPUs the container should use.                                                                                                                                                                                                                                                                 |
| disasterRecovery.resources.requests.memory       | string  | no        | 10Mi                     | The minimum amount of memory the container should use. The value can be specified with SI suffixes (E, P, T, G, M, K, m) or their power-of-two-equivalents (Ei, Pi, Ti, Gi, Mi, Ki).                                                                                                                                 |
| disasterRecovery.resources.limits.cpu            | string  | no        | 32m                      | The maximum number of CPUs the container can use.                                                                                                                                                                                                                                                                    |
| disasterRecovery.resources.limits.memory         | string  | no        | 32Mi                     | The maximum amount of memory the container can use. The value can be specified with SI suffixes (E, P, T, G, M, K, m) or their power-of-two-equivalents (Ei, Pi, Ti, Gi, Mi, Ki).                                                                                                                                    |

## Integration Tests Parameters

The Integration Tests parameters are as follows:

|Parameter   |Type  |Mandatory|Default value|Description                                                        |
|------------|------|---------|-------------|-------------------------------------------------------------------|
|integrationTests.enabled|bool|no|False|This parameter specifies whether integration tests are enabled.|
|integrationTests.dockerImage|string|yes|image included in the manifest|This parameter specifies the robot tests' image.|
|integrationTests.runTestsOnly|bool|no|False|This parameter specifies whether only integration tests should be run instead of update.|
|integrationTests.runBenchmarks|bool|no|False|This parameter specifies whether Benchmark Tests should be run.|
|integrationTests.waitTestResultOnJob|bool|no|False|This parameter specifies whether to wait for the integration tests' result on the job.|
|integrationTests.waitTestResultTimeout|int|no|900|This parameter specifies the waiting time for integration tests' results.|
|integrationTests.mistralReadyTimeout|int|no|90|This parameter specifies the waiting time for mistral to be ready before starting tests.|
|integrationTests.fsGroup|int|no||This parameter specifies a specific fsGroup.|
|integrationTests.runAsUser|int|no||This parameter specifies a specific user.|
|integrationTests.priorityClassName|string|no|""|The priority class to be used to assign priority to Mistral Tests pod. Priority class should be created beforehand. For more information, refer to https://kubernetes.io/docs/concepts/configuration/pod-priority-preemption/.|
|secrets.idpUserRobot|string|no|'null'|This parameter specifies the IDP user for testing.|
|secrets.idpPasswordRobot|string|no|'null'|This parameter specifies the IDP password for testing.|

# Installation

The installation process is described below.

## Before You Begin

Before you begin, follow these steps:

* Make sure there is enough space for Mistral deployment.
* Make sure that the services Mistral relies on (database, messaging broker, and so on) are up and running.

### Helm

For Mistral installation, preinstall [Helm 3](https://github.com/helm/helm/releases/tag/v3.0.0), download helm chart from the [deployments/charts/mistral-operator](/deployments/charts/mistral-operator) folder and configure the [values.yaml](/deployments/charts/mistral-operator/values.yaml) file. After you configure the [values.yaml](/deployments/charts/mistral-operator/values.yaml) file parameters, you can deploy Mistral using the following command:

```
$ helm install mistral-service <path_to_helm_chart_folder> --namespace <mistral_namespace> --kubeconfig <path_to_kubeconfig>
```

**Note**: The installation requires cluster-admin permissions to create [CRD](/deployments/charts/mistral-operator/crds/crd.yaml). You can create a CRD manually and then install Mistral using the the `--skip-crds` flag. In this case, Helm does not require the cluster-admin permissions.

**Note**: Images for **values.yaml** can been found in the [tags](https://github.com/Netcracker/qubership-mistral-operator/tags) pages.

## Clean up

Mistral allows cleaning up Database, Rabbit and Kafka if it's needed during deployment
- **Helm** : set  `mistralCommonParams.cleanup=True`

This feature will clean up the existing data first and then Mistral will be installed.

## On-Prem

### HA Scheme

The minimal template for HA scheme is as follows.

```
name: {service_name/namespace} # mistral-service

mistralCommonParams:
  postgres:
    dbName: 'mistral_service'
    host: 'pg-patroni.postgresql'
    port: '5432'
    idleTimeout: '30s'
  queueNamePrefix: 'mistral'
  rabbit:
    host: 'rabbitmq.rabbitmq'
    port: '5672'
    vhost: 'mistral_service'

mistralApi:
  replicas: 2
mistralEngine:
  replicas: 2
mistralExecutor:
  replicas: 2
mistralNotifier:
  replicas: 2
mistralMonitoring:
  replicas: 2

```

### DR Scheme

For more information about the Disaster Recovery scheme, refer to [Mistral Operator Disaster Recovery](/docs/disaster-recovery.md) in the _Cloud Platform Disaster Recovery Guide_.

### Non-HA Scheme

**Note**: For development purposes only.

The minimal template for the non-HA scheme is as follows.

```
name: {service_name/namespace} # mistral-service

mistralCommonParams:
  postgres:
    dbName: 'mistral_service'
    host: 'pg-patroni.postgresql'
    port: '5432'
    idleTimeout: '30s'
  queueNamePrefix: 'mistral'
  rabbit:
    host: 'rabbitmq.rabbitmq'
    port: '5672'
    vhost: 'mistral_service'

mistralApi:
  replicas: 1
mistralEngine:
  replicas: 1
mistralExecutor:
  replicas: 1
mistralNotifier:
  replicas: 1
mistralMonitoring:
  replicas: 1
```

# Upgrade

This section provides information about upgrade procedures for Mistral.


## Upgrade Mistral Using Helm

You can also update the Mistral deployment with Helm.

Update the **values.yaml** file with the required parameter values, and then update Mistral using the following command:

```
$ helm upgrade mistral-service . --kubeconfig config.yaml --namespace mistralnamespace
```

## Migration From Non-Helm to Helm Version

To update Mistral from DVM to Helm on the OpenShift environment, install the Mistral service using Helm to a project with a non-Helm version.
All deployment secrets, users, roles, and rolebindings are deleted automatically before the installation.

**Note**: To perform an upgrade from the non-Helm to Helm version, you should firstly upgrade to the latest non-Helm version of Mistral.

If the installation failed or you need to delete these entities manually, implement the following steps:

1. Apply CRD; requires cluster admin rights.

2. Delete mistral-secret using the following command:

   ```
   oc delete secret mistral-secret
   ```

3. Delete all Mistral deployment configs with the following command:

   ```
   oc delete dc mistral-api
   oc delete dc mistral-engine
   oc delete dc mistral-monitoring
   oc delete dc mistral-executor
   oc delete dc mistral-notifier
   ```

4. Install Mistral service using Helm to a project with a non-Helm version.

**Important**: It is recommended to not change the deploy parameters.

## Migration From CRD Without Versioning to CRD With Versioning

Ensure you have cluster admin rights.

To upgrade Mistral:

1. Replace the old CRD with the new CRD.

   **Note**: Replacing the old CRD with the new CRD must be done manually, even if the deployer has cluster-admin permissions.

2. If the current Mistral CR version is the same as the new CR version, no additional steps are required, else follow step 2 from [Upgrade Mistral With CRD Versioning](#upgrade-mistral-with-crd-versioning).

## Upgrade Mistral With CRD Versioning

Ensure you have cluster admin rights.

To upgrade Mistral:

1. Replace the old CRD with the new CRD.

   **Note**: Replacing the old CRD with the new CRD must be done manually, even if the deployer has cluster-admin permissions.

2. Use Helm, [Upgrade Mistral with DP Helm Deployer](#upgrade-mistral-with-dp-helm-deployer) or [Upgrade Mistral with Groovy Deployer](#upgrade-mistral-with-groovy-deployer) to upgrade Mistral service. The `name` parameter must not be different from the old Mistral version.

# Uninstall

This section provides information about uninstall procedures for Mistral.

## Uninstall Mistral Using Helm

You can uninstall the Mistral deployment with Helm.

The following command removes all the resources created in *mistral-namespace* during the Mistral installation process.

```
$ helm uninstall mistral-service --namespace <mistral-namespace> --kubeconfig <path-to-kubeconfig>
```

## Uninstall Mistral by Deleting CR

You can also uninstall Mistral by manually deleting CR (Custom Resource object for Mistral Service).

**Note**: This uninstall procedure removes all the Mistral resources created by the Mistral operator. Mistral can be re-installed by creating the CR again.

<!-- #GFCFilterMarkerStart# -->
# Rollback
TBD
# Frequently Asked Questions
TBD
<!-- #GFCFilterMarkerEnd# -->
