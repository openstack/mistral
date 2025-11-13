The section provides information about Disaster Recovery in Mistral service.

## Common Information

The Disaster Recovery scheme implies two separate Mistral clusters, one of which is in the `active` mode, and the other is in the `standby` mode.
The `active` Mistral cluster has running pods. The `standby` Mistral cluster has no running pods. When disaster recovery mode
is switched on `standby`/`active` the Mistral pods are up/down. In case of `standby` -> `active` transition Mistral switches its maintenance mode to `PAUSED`, with pausing all active executions.

## Configuration

The Disaster Recovery (DR) configuration requires two separate Mistral clusters installed on two Kubernetes/OpenShift clusters.
Each Mistral cluster must be deployed with `mode` parameter. 

For example, for `active` side:

  ```
  disasterRecovery:
    mode: "active"
  ```

For example, for `standby` side:

  ```
  disasterRecovery:
    mode: "standby"
  ```

Mistral has dependencies on Postgres Service and RabbitMQ Service (in some cases including Kafka Service): Mistral should perform switchover only after these services. 
This could be configured by `afterServices` property. This propetry should contain names of SiteManager' CR from their namespaces.

For example, if SiteManager's CR name in Postgres Service namespace is `postgres-site-manager` and SiteManager's CR name in RabbitMQ Service namespace is `rabbitmq-site-manager`, configuration is as follows:

  ```
  disasterRecovery:
    mode: "active"
    siteManagerEnabled: true
    afterServices: ["postgres-site-manager", "rabbitmq-site-manager"]
  ```

If Mistral is installed in the disaster recovery mode and authentication on disaster recovery server is enabled, cluster role binding for `system:auth-delegator` role must be created:

```yaml
kind: ClusterRoleBinding
apiVersion: rbac.authorization.k8s.io/v1
metadata:
  name: token-review-crb-NAMESPACE
subjects:
  - kind: ServiceAccount
    name: mistral-operator
    namespace: NAMESPACE
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: system:auth-delegator
```

Where:
* `NAMESPACE` is name of Kubernetes namespace in which Mistral operator is installed.

## Configuration Example

If you want to install Mistral service in Disaster Recovery scheme, the configuration for `active` Mistral cluster is as follows:

```yaml
disasterRecovery:
  image: ghcr.io/netcracker/disaster-recovery-daemon:main
  httpAuth:
    enabled: false
    smNamespace: "site-manager"
    smServiceAccountName: "sm-auth-sa"
    restrictedEnvironment: false
  mode: "active"
  siteManagerEnabled: false
  afterServices: []
  resources:
    limits:
      cpu: 32m
      memory: 32Mi
    requests:
      cpu: 10m
      memory: 10Mi
```

The configuration for `standby` Mistral cluster is as follows:

```yaml
disasterRecovery:
  image: ghcr.io/netcracker/disaster-recovery-daemon:main
  httpAuth:
    enabled: false
    smNamespace: "site-manager"
    smServiceAccountName: "sm-auth-sa"
    restrictedEnvironment: false
  mode: "standby"
  siteManagerEnabled: false
  afterServices: []
  resources:
    limits:
      cpu: 32m
      memory: 32Mi
    requests:
      cpu: 10m
      memory: 10Mi
```

## Switchover

You can perform the switchover using the `SiteManager` functionality or Mistral disaster recovery REST server API.

If you want to perform a switchover manually, you need to switch `active` Mistral cluster to `standby` mode and then switch `standby` Mistral cluster to `active` mode. You need to run the following command from within any Mistral pod on the `active` side:

```
curl -XPOST -H "Content-Type: application/json" mistral-disaster-recovery.<NAMESPACE>:8068/sitemanager -d '{"mode":"standby"}'
```

Then, run the following command from within any Mistral pod on the `standby` side:

```
curl -XPOST -H "Content-Type: application/json" mistral-disaster-recovery.<NAMESPACE>:8068/sitemanager -d '{"mode":"active"}'
```

Where, `<NAMESPACE>` is the OpenShift/Kubernetes project/namespace of the Mistral cluster side. For example, `mistral-service`.

For more information about Mistral disaster recovery REST server API, see [REST API](#rest-api).

## REST API

Mistral disaster recovery REST server provides three methods of interaction:

* `GET` `healthz` method allows finding out the state of the current Mistral cluster side. In both cases `standby` or `disable`, this endpoint checks status of all 5 Mistral deployments.

  ```
  curl -XGET mistral-disaster-recovery.<NAMESPACE>:8068/healthz
  ```

  Where `<NAMESPACE>` is the OpenShift/Kubernetes project/namespace of the Mistral cluster side. For example, `mistral-service`.

  All Mistral disaster recovery REST server endpoints can be secured via Kubernetes JWT Service Account Tokens. To enable disaster recovery REST server authentication the `disasterRecovery.httpAuth.enabled` deployment parameter must be `true`.
  The example for secured `healthz` endpoint is following:

  ```
  curl -XGET -H "Authorization: Bearer <TOKEN>" mistral-disaster-recovery.<NAMESPACE>:8068/healthz
  ```

 Where, `TOKEN` is Site Manager Kubernetes JWT Service Account Token. The verification service account name and namespace are specified in `disasterRecovery.httpAuth.smServiceAccountName` and `disasterRecovery.httpAuth.smNamespace` deploy parameters.

  The response to such a request is as follows:

  ```json
  {"status":"up"}
  ```

  Where:
  * `status` is the current state of the Mistral cluster side. The four possible status values are as follows:
    * `up` - Each of 5 Mistral deployments are ready.
    * `degraded` - Some of 5 Mistral deployments are not ready.
    * `down` - None of 5 Mistral deployments is ready.
    * `disable` - Each of 5 Mistral deployments are scaled down.

* `GET` `sitemanager` method allows finding out the mode of the current Mistral cluster side and the actual state of the switchover procedure. You can run this method from within any Mistral pod as follows:

  ```
  curl -XGET mistral-disaster-recovery.<NAMESPACE>:8068/sitemanager
  ```

  Where, `<NAMESPACE>` is the OpenShift/Kubernetes project/namespace of the Mistral cluster side. For example, `mistral-service`.

  All Mistral disaster recovery REST server endpoints can be secured via Kubernetes JWT Service Account Tokens. To enable the disaster recovery REST server authentication, the `disasterRecovery.httpAuth.enabled` deployment parameter must be `true`.
  The example for secured `sitemanager` GET endpoint is following:

  ```
  curl -XGET -H "Authorization: Bearer <TOKEN>" mistral-disaster-recovery.<NAMESPACE>:8068/sitemanager
  ```

  Where, `TOKEN` is Site Manager Kubernetes JWT Service Account Token. The verification service account name and namespace are specified in `disasterRecovery.httpAuth.smServiceAccountName` and `disasterRecovery.httpAuth.smNamespace` deploy parameters.

  The response to such a request is as follows:

  ```json
  {"mode":"standby","status":"done"}
  ```

  Where:
  * `mode` is the mode in which the Mistral cluster side is deployed. The possible mode values are as follows:
    * `active` - Mistral accepts external requests from clients.
    * `standby` - Mistral does not accept external requests from clients.
    * `disable` - Mistral does not accept external requests from clients.
  * `status` is the current state of switchover for the Mistral cluster side. The three possible status values are as follows:
    * `running` - The switchover is in progress.
    * `done` - The switchover is successful.
    * `failed` - Something went wrong during the switchover.
  * `message` is the message which contains a detailed description of the problem.

* `POST` `sitemanager` method allows switching mode for the current side of Mistral cluster. You can run this method from within any Mistral pod as follows:

  ```
  curl -XPOST -H "Content-Type: application/json" mistral-disaster-recovery.<NAMESPACE>:8068/sitemanager -d '{"mode":"<MODE>"}'
  ```

  Where:
  * `<NAMESPACE>` is the OpenShift/Kubernetes project/namespace of the Mistral cluster side. For example, `mistral-service`.
  * `<MODE>` is the mode to be applied to the Mistral cluster side. The possible mode values are as follows:
    * `active` - Mistral accepts external requests from clients.
    * `standby` - Mistral does not accept external requests from clients.
    * `disable` - Mistral does not accept external requests from clients.

  All Mistral disaster recovery REST server endpoints can be secured via Kubernetes JWT Service Account Tokens. To enable the disaster recovery REST server authentication, the `disasterRecovery.httpAuth.enabled` deployment parameter must be `true`.
  The example for secured `sitemanager` POST endpoint is following:

  ```
  curl -XPOST -H "Content-Type: application/json, Authorization: Bearer <TOKEN>" mistral-disaster-recovery.<NAMESPACE>:8068/sitemanager
  ```

  Where, `TOKEN` is Site Manager Kubernetes JWT Service Account Token. The verification service account name and namespace are specified in `disasterRecovery.httpAuth.smServiceAccountName` and `disasterRecovery.httpAuth.smNamespace` deploy parameters.

  The response to such a request is as follows:

  ```json
  {"mode":"standby"}
  ```

  Where:
  * `mode` is the mode which is applied to the Mistral cluster side. The possible values are `active`, `standby` and `disable`.
  * `status` is the state of the request on the REST server. The only possible value is `failed`, when something goes wrong while processing the request.
  * `message` is the message which contains a detailed description of the problem.

## Troubleshooting

If switchover or any other DR operation failed you can try to execute it again for this service only. 
The DR feature supports retry if operation has not been finished successfully.
You can do it with SiteManager Client or [REST API](#rest-api) described above. 
You need to execute it in the sequence `active -> standby` first, `standby -> active` then.
