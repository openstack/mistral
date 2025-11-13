This section provides information about manual deployment of Mistral service with an operator. For this deployment, only Mistral configurations without a guaranteed notifier are supported.
Overall, the Mistral configuration is similar to the Mistral deployment with the OpenShift deployer, except for the OpenShift route is not created when deployment is done using an operator.

To deploy Mistral with an operator in OpenShift/Kubernetes:

1. Download the following operator deploy directory: [https://github.com/Netcracker/qubership-mistral-operator/tree/main/deploy](https://github.com/Netcracker/qubership-mistral-operator/tree/main/deploy).
1. Replace the `REPLACE_IMAGE` value in the **/deploy/operator.yaml** file with the required operator image. To replace the image use the following command:

   ```
   sed -i 's|REPLACE_IMAGE|ghcr.io/netcracker/qubership-mistral-operator:main|g' deploy/operator.yaml
   ```

   You can also specify the `LOGLEVEL` environment variable in order to set the logging level of the operator in the **/deploy/operator.yaml** file. Another available environment variable is `OPERATOR_DELETE_RESOURCES`, which specifies whether the operator should delete all Mistral resources, services, and deployments when the Mistral Custom Resource is deleted. When not specified, the value is `False`.
   
   **Warning**: If `OPERATOR_DELETE_RESOURCES` is set to `True`, the Mistral operator must be up and working when you are deleting the CR. Otherwise, the delete operation may be stuck for an unlimited time, and may stop you from deleting the namespace.
   
1. Set the required Mistral configuration in the **/deploy/cr.yaml** file. For more information, refer to [Configuration](#configuration).
1. Create a Mistral secret in the project/namespace.

    In OpenShift, use the following command:

    ```
    oc create secret generic mistral-secret --from-literal=idp-client-id="" --from-literal=idp-client-secret="" --from-literal=idp-jwk-exp="" --from-literal=idp-jwk-mod="" --from-literal=pg-admin-user="" --from-literal=pg-admin-password="" --from-literal=pg-password="" --from-literal=pg-user="" --from-literal=rabbit-password="" --from-literal=rabbit-user="" --from-literal=rabbit-admin-user="" --from-literal=rabbit-admin-password=""
    ```

    In Kubernetes, use the following command:

    ```
    kubectl create secret generic mistral-secret --from-literal=idp-client-id="" --from-literal=idp-client-secret="" --from-literal=idp-jwk-exp="" --from-literal=idp-jwk-mod="" --from-literal=pg-admin-user="" --from-literal=pg-admin-password="" --from-literal=pg-password="" --from-literal=pg-user="" --from-literal=rabbit-password="" --from-literal=rabbit-user="" --from-literal=rabbit-admin-user="" --from-literal=rabbit-admin-password="" --namespace=MISTRAL_NAMESPACE
    ```
    
    To deploy lite Mistral with RabbitMQ container inside Mistral pod you also need to create a RabbitMQ secret in the project/namespace.

    In OpenShift, use the following command:

    ```
     oc create secret generic rabbitmq-default-secret --from-literal=user="${RABBIT_ADMIN_USER}" --from-literal=password="${RABBIT_ADMIN_PASSWORD}" --from-literal=rmqcookie="secretcookie"
    ```

    In Kubernetes, use the following command:

    ```
    kubectl create secret generic rabbitmq-default-secret --from-literal=user="${RABBIT_ADMIN_USER}" --from-literal=password="${RABBIT_ADMIN_PASSWORD}" --from-literal=rmqcookie="secretcookie" --namespace=MISTRAL_NAMESPACE
    ```
    For lite Mistral with RabbitMQ container inside Mistral pod, `RABBIT_ADMIN_USER` must be same as `RABBIT_USER` and `RABBIT_ADMIN_PASSWORD` must be same as `RABBIT_PASSWORD`.
    
1. Apply the files from the **operator** directory using the following commands:

   ```
   kubectl apply -f deploy/role.yaml
   kubectl apply -f deploy/service_account.yaml
   kubectl apply -f deploy/role_binding.yaml
   kubectl apply -f deploy/crd.yaml
   kubectl apply -f deploy/operator.yaml
   ```
   **Note**: If you need to deploy Mistral to Kubernetes, add `--namespace=MISTRAL_NAMESPACE` to all the above commands.
   
   For lite Mistral with RabbitMQ container inside Mistral pod also apply the following:
   
   ```
   kubectl apply -f deploy/rabbit_roles.yaml
   ```

**Note**: To apply CRD, ensure that you have cluster-admin privileges.

When the operator pod is up and running, you can deploy Mistral using the `kubectl apply -f /deploy/cr.yaml` command.

# Configuration

For more information about the list of configuration parameters, see [Installation Parameters](docs/installation.md#installation-parameters).

## Upgrade

Mistral can be upgraded with the operator. To apply the new configuration, all Mistral pods are restarted.
For lite Mistral deployment, upgrade procedure includes recreation of Mistral deployment. All information is lost during this procedure.
