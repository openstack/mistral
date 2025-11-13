"""
Module to handle all the kubernetes operations
"""
from time import sleep
from datetime import datetime
from datetime import timezone

import logging
import base64
import kopf
import random
import re
import requests
from threading import Thread

from kubernetes import client
from kubernetes.client import V1ObjectMeta, V1EnvVar, V1Container, V1PodSpec, \
    V1PodTemplateSpec, V1ContainerPort, \
    V1EnvVarSource, V1ObjectFieldSelector, V1VolumeMount, \
    V1ResourceRequirements, V1SecretKeySelector, \
    V1Volume, V1ConfigMapVolumeSource, V1KeyToPath, V1ConfigMap, \
    V1Service, V1ServiceSpec, V1ServicePort, V1ConfigMapKeySelector, \
    V1ResourceFieldSelector, V1LabelSelector, V1Job, V1JobSpec, \
    V1DeleteOptions, V1ComponentCondition, V1ComponentStatus, V1SecurityContext, \
    V1Capabilities, V1SeccompProfile, V1SecretVolumeSource

import mistral_constants as MC
from rabbitmq_helper import RabbitMQHelper

logging.basicConfig(
    filename='/proc/1/fd/1',
    filemode='w',
    level=MC.LOGLEVEL,
    format='[%(asctiivsh0819me)s][%(levelname)-5s]'
           '[category=%(name)s] %(message)s',
    datefmt='%Y-%m-%dT%H:%M:%S'
)
logger = logging.getLogger(__name__)


class FakeKubeResponse:
    def __init__(self, obj):
        import json
        self.data = json.dumps(obj)


class KubernetesHelper:
    SA_NAMESPACE_PATH = '/var/run/secrets/kubernetes.io/' \
                        'serviceaccount/namespace'

    def __init__(self, spec):
        self._api_client = client.ApiClient()
        with open(self.SA_NAMESPACE_PATH, encoding='utf-8') as file:
            self._workspace = file.read()
        self._apps_api = client.AppsV1Api(self._api_client)
        self._v1_apps_api = client.CoreV1Api(self._api_client)
        self._batch_v1_api = client.BatchV1Api(self._api_client)
        self._spec = spec
        self._custom_objects_api = client.CustomObjectsApi(self._api_client)
        self.spec_hash = ''
        logger.info("configuration is: %s", str(spec))

    def get_container_security_context(self):
        return V1SecurityContext(allow_privilege_escalation=False,
                                 capabilities=V1Capabilities(drop=["ALL"]))

    def get_priority_class_name(self, name):
        return self._spec[name].get('priorityClassName') or ""

    def get_security_context(self, name):
        sec_context_base = self._spec[name].get('securityContext') or {}

        def camelback2snake(name):
            return re.sub(r'[A-Z]', lambda x: '_' + x.group(0).lower(), name)

        sec_context = {camelback2snake(k): v for k, v in sec_context_base.items()}
        if not sec_context.get("run_as_non_root"):
            sec_context["run_as_non_root"] = True

        if sec_context.get("seccomp_profile"):
            profile = sec_context.get("seccomp_profile").get("type")
            sec_context["seccomp_profile"] = V1SeccompProfile(type=profile)
        else:
            sec_context["seccomp_profile"] = V1SeccompProfile(type="RuntimeDefault")

        return client.V1PodSecurityContext(**sec_context)

    def apply_deployment_config(self, name, server_name):
        dcbody = self.generate_deployment_config_body(name, server_name)
        kopf.adopt(dcbody)
        self._apps_api.create_namespaced_deployment(self._workspace, dcbody)

    def apply_lite_deployment_config(self, name):
        dcbody = self.generate_lite_deployment_config_body(name)
        kopf.adopt(dcbody)
        self._apps_api.create_namespaced_deployment(self._workspace, dcbody)

    def get_job_status(self, job_name):
        job_status = None
        job_doc = self._batch_v1_api.read_namespaced_job(
            name=job_name, namespace=self._workspace
        )
        if job_doc.status.succeeded == 1:
            job_status = MC.Status.SUCCESSFUL
        if job_doc.status.failed == 3:
            job_status = MC.Status.FAILED
        return job_status, job_doc

    def get_job_logs(self, job_doc):
        job_logs = ""
        labels = getattr(job_doc.spec.selector, "match_labels", {}) or {}
        ctrl_uid = labels.get("controller-uid")
        if not ctrl_uid:
            return "No controller-uid label on Job selector; cannot fetch pod logs."
        pod_label_selector = "controller-uid=" + ctrl_uid
        pods_list = self._v1_apps_api.list_namespaced_pod(
            namespace=self._workspace, label_selector=pod_label_selector, timeout_seconds=10
        )
        pods_list = [pod.metadata.name for pod in pods_list.items]
        if not pods_list:
            job_logs = "Exception while get_job_logs: No active container found for job"
            return job_logs
        try:
            for pod_name in pods_list:
                pod_log_response = self._v1_apps_api.read_namespaced_pod_log(
                    name=pod_name, namespace=self._workspace,
                    _return_http_data_only=True, _preload_content=False
                )
                pod_logs = pod_log_response.data.decode("utf-8")
                job_logs += f"\n\n Logs for Job pod - {pod_name} \n"
                job_logs += pod_logs
        except client.rest.ApiException as exc:
            job_logs += f"Exception when calling CoreV1Api->read_namespaced_pod_log: {exc}"
        return job_logs

    def apply_update_db_job(self):
        attempts = 36
        sleep_between_iterations = 20
        jobbody = self.generate_update_db_job_body()
        kopf.adopt(jobbody)
        self._batch_v1_api.create_namespaced_job(self._workspace, jobbody)
        while attempts > 0:
            sleep(sleep_between_iterations)
            update_db_job_status, update_db_job_doc = self.get_job_status(job_name=MC.UPDATE_DB_JOB)
            if update_db_job_status:
                break
            attempts = attempts - 1
        if attempts == 0 or update_db_job_status == MC.Status.FAILED:
            job_logs = self.get_job_logs(job_doc=update_db_job_doc)
            logger.error(
                "Error with Mistral update db job. Following are failure logs"
                " from Mistral update db job %s", job_logs
            )
            self.update_status(
                MC.Status.FAILED,
                "Error",
                "Error with Mistral update db job. Following are failure logs"
                " from Mistral update db job %s" % job_logs
            )
            sleep(5)
            raise kopf.PermanentError("Error with Mistral update db job.")

    def generate_update_db_job_body(self):
        update_db_pod_params = self._spec['mistralUpdateDbPod']
        container_resources = \
            V1ResourceRequirements(limits={'cpu': '250m',
                                           'memory':
                                               update_db_pod_params[
                                                   'memoryLimit']},
                                   requests={
                                       'cpu': '150m',
                                       'memory': '256Mi'})

        volumes = [
            V1Volume(
                name=MC.MISTRAL_CUSTOM_CONFIG_VOLUME,
                config_map=V1ConfigMapVolumeSource(
                    name=MC.CUSTOM_CONFIGMAP,
                    items=[V1KeyToPath(key=MC.CUSTOM_CONFIG, path=MC.CUSTOM_CONFIG_FILE_PATH)],
                )
            ),
            V1Volume(
                secret=V1SecretVolumeSource(
                    secret_name=MC.MISTRAL_TLS_SECRET,
                    default_mode=416
                ),
                name=MC.MISTRAL_TLS_CONFIG_VOLUME
            )
        ]
        mounth_path = update_db_pod_params['mountConfigsHome'] + '/custom'
        volume_mounts = \
            [V1VolumeMount(name=MC.MISTRAL_CUSTOM_CONFIG_VOLUME,
                           mount_path=mounth_path)]
        if self.is_secret_present("mistral-tls-secret"):
            volume_mounts.append(
                V1VolumeMount(
                    mount_path='/opt/mistral/mount_configs/tls',
                    name=MC.MISTRAL_TLS_CONFIG_VOLUME,
                    read_only=True
                )
            )

        envs = [
            V1EnvVar(
                name='PG_USER',
                value_from=V1EnvVarSource(
                    secret_key_ref=V1SecretKeySelector(
                        key='pg-user',
                        name=MC.MISTRAL_SECRET))),
            V1EnvVar(
                name='PG_PASSWORD',
                value_from=V1EnvVarSource(
                    secret_key_ref=V1SecretKeySelector(
                        key='pg-password',
                        name=MC.MISTRAL_SECRET))),
            V1EnvVar(
                name='PG_DB_NAME',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='pg-db-name',
                        name=MC.COMMON_CONFIGMAP))),
            V1EnvVar(
                name='PG_HOST',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='pg-host',
                        name=MC.COMMON_CONFIGMAP))),
            V1EnvVar(
                name='PG_PORT',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='pg-port',
                        name=MC.COMMON_CONFIGMAP))),
            V1EnvVar(
                name='PG_ADMIN_USER',
                value_from=V1EnvVarSource(
                    secret_key_ref=V1SecretKeySelector(
                        key='pg-admin-user',
                        name=MC.MISTRAL_SECRET))),
            V1EnvVar(
                name='PG_ADMIN_PASSWORD',
                value_from=V1EnvVarSource(
                    secret_key_ref=V1SecretKeySelector(
                        key='pg-admin-password',
                        name=MC.MISTRAL_SECRET))),
            V1EnvVar(
                name='PG_IDLE_TIMEOUT',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='pg-idle-timeout',
                        name=MC.COMMON_CONFIGMAP))),
            V1EnvVar(
                name='RABBIT_USER',
                value_from=V1EnvVarSource(
                    secret_key_ref=V1SecretKeySelector(
                        key='rabbit-user',
                        name=MC.MISTRAL_SECRET))),
            V1EnvVar(
                name='RABBIT_ADMIN_USER',
                value_from=V1EnvVarSource(
                    secret_key_ref=V1SecretKeySelector(
                        key='rabbit-admin-user',
                        name=MC.MISTRAL_SECRET))),
            V1EnvVar(
                name='RABBIT_PASSWORD',
                value_from=V1EnvVarSource(
                    secret_key_ref=V1SecretKeySelector(
                        key='rabbit-password',
                        name=MC.MISTRAL_SECRET))),
            V1EnvVar(
                name='RABBIT_ADMIN_PASSWORD',
                value_from=V1EnvVarSource(
                    secret_key_ref=V1SecretKeySelector(
                        key='rabbit-admin-password',
                        name=MC.MISTRAL_SECRET))),
            V1EnvVar(
                name='RABBIT_HOST',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='rabbit-host',
                        name=MC.COMMON_CONFIGMAP))),
            V1EnvVar(
                name='RABBIT_PORT',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='rabbit-port',
                        name=MC.COMMON_CONFIGMAP))),
            V1EnvVar(
                name='RABBIT_VHOST',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='rabbit-vhost',
                        name=MC.COMMON_CONFIGMAP))),
            V1EnvVar(
                name='KAFKA_NOTIFICATIONS_ENABLED',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='kafka-notifications-enabled',
                        name=MC.COMMON_CONFIGMAP))),
            V1EnvVar(
                name='KAFKA_HOST',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='kafka-host',
                        name=MC.COMMON_CONFIGMAP))),
            V1EnvVar(
                name='KAFKA_TOPIC',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='kafka-topic',
                        name=MC.COMMON_CONFIGMAP))),
            V1EnvVar(
                name='KAFKA_CONSUMER_GROUP_ID',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='kafka-consumer-group-id',
                        name=MC.COMMON_CONFIGMAP))),
            V1EnvVar(
                name='KAFKA_TOPIC_PARTITIONS_COUNT',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='kafka-topic-partitions-count',
                        name=MC.COMMON_CONFIGMAP))),
            V1EnvVar(
                name='KAFKA_SECURITY_ENABLED',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='kafka-security-enabled',
                        name=MC.COMMON_CONFIGMAP))),
            V1EnvVar(
                name='KAFKA_SASL_PLAIN_USERNAME',
                value_from=V1EnvVarSource(
                    secret_key_ref=V1SecretKeySelector(
                        key='kafka-sasl-plain-username',
                        name=MC.MISTRAL_SECRET))),
            V1EnvVar(
                name='KAFKA_SASL_PLAIN_PASSWORD',
                value_from=V1EnvVarSource(
                    secret_key_ref=V1SecretKeySelector(
                        key='kafka-sasl-plain-password',
                        name=MC.MISTRAL_SECRET))),
            V1EnvVar(
                name='GUARANTEED_NOTIFIER_ENABLED',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='guaranteed-notifier-enabled',
                        name=MC.COMMON_CONFIGMAP))),
            V1EnvVar(
                name='MULTITENANCY_ENABLED',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='multitenancy-enabled',
                        name=MC.COMMON_CONFIGMAP))),
            V1EnvVar(
                name='QUEUE_NAME_PREFIX',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='queue-name-prefix',
                        name=MC.COMMON_CONFIGMAP))),
        ]

        if self.tls_enabled():
            envs.extend(self.get_tls_envs())

        job_pod_spec = V1PodSpec(
            containers=[
                V1Container(
                    name=MC.UPDATE_DB_JOB,
                    image=self._spec['mistral']['dockerImage'],
                    env=envs,
                    args=[update_db_pod_params['args']],
                    resources=container_resources,
                    image_pull_policy='Always',
                    volume_mounts=volume_mounts,
                    security_context=self.get_container_security_context()
                )
            ],
            volumes=volumes,
            restart_policy='Never',
            security_context=self.get_security_context("mistralUpdateDbPod"),
            priority_class_name=self.get_priority_class_name("mistralUpdateDbPod")
        )
        job_pod_template = V1PodTemplateSpec(
            metadata=V1ObjectMeta(
                name=MC.UPDATE_DB_JOB,
                labels=self.get_labels(
                    {
                        'job-name': MC.UPDATE_DB_JOB,
                        'app': MC.UPDATE_DB_JOB
                    }, kubernetes_prefix="mistralUpdateDbJob"
                ),
                annotations={
                    "argocd.argoproj.io/hook": "PostSync",
                    "argocd.argoproj.io/hook-delete-policy": "HookSucceeded",
                    "helm.sh/hook-delete-policy": "before-hook-creation",
                    "helm.sh/hook": "post-install,post-upgrade",
                    "helm.sh/hook-weight": "10"}
            ),
            spec=job_pod_spec)

        job_spec = V1JobSpec(active_deadline_seconds=720,
                             ttl_seconds_after_finished=420,
                             backoff_limit=2,
                             template=job_pod_template)
        job_template = V1Job(api_version='batch/v1',
                             metadata=V1ObjectMeta(
                                 name=MC.UPDATE_DB_JOB,
                                 labels=self.get_labels({'app': MC.UPDATE_DB_JOB}),
                                 annotations={
                                     "argocd.argoproj.io/hook": "PostSync",
                                     "argocd.argoproj.io/hook-delete-policy": "HookSucceeded",
                                     "helm.sh/hook-delete-policy": "before-hook-creation",
                                     "helm.sh/hook": "post-install,post-upgrade",
                                     "helm.sh/hook-weight": "10"}
                             ),
                             kind='Job', spec=job_spec)
        return job_template

    def generate_mistral_dr_job_body(self):
        container_resources = V1ResourceRequirements(
            limits={'cpu': '300m', 'memory': '300Mi'},
            requests={'cpu': '300m', 'memory': '300Mi'}
        )

        volumes = [
            V1Volume(
                name=MC.MISTRAL_CUSTOM_CONFIG_VOLUME,
                config_map=V1ConfigMapVolumeSource(
                    name=MC.CUSTOM_CONFIGMAP,
                    items=[V1KeyToPath(key=MC.CUSTOM_CONFIG, path=MC.CUSTOM_CONFIG_FILE_PATH)]
                )
            )
        ]
        mounth_path = '/opt/mistral/mount_configs/custom'
        volume_mounts = \
            [V1VolumeMount(name=MC.MISTRAL_CUSTOM_CONFIG_VOLUME,
                           mount_path=mounth_path)]
        job_pod_spec = V1PodSpec(
            containers=[
                V1Container(
                    name=MC.MISTRAL_DR_JOB,
                    image=self._spec['mistral']['dockerImage'],
                    env=[
                        V1EnvVar(
                            name='DEBUG_LOG',
                            value='True'),
                        V1EnvVar(
                            name='NOTIFIER_DISABLED',
                            value='True'),
                        V1EnvVar(
                            name='PG_USER',
                            value_from=V1EnvVarSource(
                                secret_key_ref=V1SecretKeySelector(
                                    key='pg-user',
                                    name=MC.MISTRAL_SECRET))),
                        V1EnvVar(
                            name='PG_PASSWORD',
                            value_from=V1EnvVarSource(
                                secret_key_ref=V1SecretKeySelector(
                                    key='pg-password',
                                    name=MC.MISTRAL_SECRET))),
                        V1EnvVar(
                            name='PG_DB_NAME',
                            value_from=V1EnvVarSource(
                                config_map_key_ref=V1ConfigMapKeySelector(
                                    key='pg-db-name',
                                    name=MC.COMMON_CONFIGMAP))),
                        V1EnvVar(
                            name='PG_HOST',
                            value_from=V1EnvVarSource(
                                config_map_key_ref=V1ConfigMapKeySelector(
                                    key='pg-host',
                                    name=MC.COMMON_CONFIGMAP))),
                        V1EnvVar(
                            name='PG_PORT',
                            value_from=V1EnvVarSource(
                                config_map_key_ref=V1ConfigMapKeySelector(
                                    key='pg-port',
                                    name=MC.COMMON_CONFIGMAP))),
                        V1EnvVar(
                            name='PG_IDLE_TIMEOUT',
                            value_from=V1EnvVarSource(
                                config_map_key_ref=V1ConfigMapKeySelector(
                                    key='pg-idle-timeout',
                                    name=MC.COMMON_CONFIGMAP))),
                        V1EnvVar(
                            name='PG_ADMIN_USER',
                            value_from=V1EnvVarSource(
                                secret_key_ref=V1SecretKeySelector(
                                    key='pg-admin-user',
                                    name=MC.MISTRAL_SECRET))),
                        V1EnvVar(
                            name='PG_ADMIN_PASSWORD',
                            value_from=V1EnvVarSource(
                                secret_key_ref=V1SecretKeySelector(
                                    key='pg-admin-password',
                                    name=MC.MISTRAL_SECRET)))
                    ],
                    args=['./dr.sh'],
                    resources=container_resources,
                    image_pull_policy='Always',
                    volume_mounts=volume_mounts,
                    security_context=self.get_container_security_context()
                )
            ],
            volumes=volumes, restart_policy='Never',
            termination_grace_period_seconds=30,
            security_context=self.get_security_context('disasterRecovery'),
            priority_class_name=self.get_priority_class_name('disasterRecovery')
        )

        job_pod_template = V1PodTemplateSpec(
            metadata=V1ObjectMeta(
                name=MC.MISTRAL_DR_JOB,
                labels=self.get_labels(
                    {
                        'job-name': MC.MISTRAL_DR_JOB,
                        'app': MC.MISTRAL_DR_JOB
                    }, kubernetes_prefix="mistralDrJob"
                )
            ),
            spec=job_pod_spec)
        job_spec = V1JobSpec(active_deadline_seconds=720,
                             ttl_seconds_after_finished=420,
                             backoff_limit=2,
                             template=job_pod_template)
        job_template = V1Job(
            api_version='batch/v1',
            metadata=V1ObjectMeta(
                name=MC.MISTRAL_DR_JOB,
                labels=self.get_labels({'app': MC.MISTRAL_DR_JOB})
            ),
            kind='Job', spec=job_spec
        )
        return job_template

    def apply_mistral_dr_job(self):
        attempts = 36
        sleep_between_iterations = 20
        jobbody = self.generate_mistral_dr_job_body()
        kopf.adopt(jobbody)
        self._batch_v1_api.create_namespaced_job(self._workspace, jobbody)
        while attempts > 0:
            mistral_dr_job_status, mistral_dr_job_doc = self.get_job_status(
                job_name=MC.MISTRAL_DR_JOB
            )
            if mistral_dr_job_status:
                break
            attempts = attempts - 1
            sleep(sleep_between_iterations)
        if attempts == 0 or mistral_dr_job_status == MC.Status.FAILED:
            job_logs = self.get_job_logs(mistral_dr_job_doc)
            logger.info("Error with Mistral DR job. logs: \n %s", job_logs)
            self.update_status(
                MC.Status.FAILED,
                "Error",
                f"Error with Mistral DR job. logs: \n {job_logs}"
            )
            sleep(5)
            raise kopf.PermanentError("Error with Mistral DR job.")

    def is_mistral_dr_job_present(self):
        jobs = self._batch_v1_api.list_namespaced_job(
            namespace=self._workspace)
        exists = list(
            filter(lambda x: x.metadata.name == MC.MISTRAL_DR_JOB,
                   jobs.items))
        return len(exists) != 0

    def mistral_dr_job(self):
        delopt = V1DeleteOptions(propagation_policy='Background',
                                 grace_period_seconds=0)
        if self.is_mistral_dr_job_present():
            logger.info("Deleting old Mistral DR job")
            self._batch_v1_api.delete_namespaced_job(
                namespace=self._workspace,
                name=MC.MISTRAL_DR_JOB,
                body=delopt
            )
        while self.is_mistral_dr_job_present():
            logger.info("Waiting until old Mistral DR job deleted")
            sleep(3)
        self.apply_mistral_dr_job()

    def generate_deployment_config_body(self, name, server_name):
        livenessprobe = MC.LIVENESS_PROBE
        readinessprobe = MC.READINESS_PROBE
        server = 'mistral' + server_name
        mistral_replicas = self._spec[server]['replicas']
        mistral_resources = self._spec[server]['resources']
        logger.debug("resources:" + str(mistral_resources))
        meta = V1ObjectMeta(labels=self.get_labels(
            {
                'app': MC.MISTRAL_LABEL,
                'name': name
            }, kubernetes_prefix=server), name=name, namespace=self._workspace)
        mistral_image = self._spec['mistral']['dockerImage']
        image_pull_policy = 'Always' if 'latest' in mistral_image.lower() \
            else self._spec['mistral']['imagePullPolicy']

        container_resources = \
            V1ResourceRequirements(
                limits={
                    'cpu': mistral_resources['limits'][
                        'cpu'],
                    'memory':
                        mistral_resources['limits'][
                            'memory']},
                requests={'cpu': mistral_resources['requests']['cpu'],
                          'memory': mistral_resources['requests']['memory']})

        container_envs = [
            V1EnvVar(
                name='QUEUE_NAME_PREFIX',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='queue-name-prefix',
                        name=MC.COMMON_CONFIGMAP))),
            V1EnvVar(
                name='OS_MISTRAL_URL',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='os-mistral-url',
                        name=MC.COMMON_CONFIGMAP))),
            V1EnvVar(
                name='USE_PYPY',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='use-pypy',
                        name=MC.COMMON_CONFIGMAP))),
            V1EnvVar(
                name='GUARANTEED_NOTIFIER_ENABLED',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='guaranteed-notifier-enabled',
                        name=MC.COMMON_CONFIGMAP))),
            V1EnvVar(
                name='IDP_SERVER',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='idp-server',
                        name=MC.COMMON_CONFIGMAP))),
            V1EnvVar(
                name='IDP_JWK_EXP',
                value_from=V1EnvVarSource(
                    secret_key_ref=V1SecretKeySelector(
                        key='idp-jwk-exp',
                        name=MC.MISTRAL_SECRET))),
            V1EnvVar(
                name='IDP_JWK_MOD',
                value_from=V1EnvVarSource(
                    secret_key_ref=V1SecretKeySelector(
                        key='idp-jwk-mod',
                        name=MC.MISTRAL_SECRET))),
            V1EnvVar(
                name='RABBIT_USER',
                value_from=V1EnvVarSource(
                    secret_key_ref=V1SecretKeySelector(
                        key='rabbit-user',
                        name=MC.MISTRAL_SECRET))),
            V1EnvVar(
                name='RABBIT_PASSWORD',
                value_from=V1EnvVarSource(
                    secret_key_ref=V1SecretKeySelector(
                        key='rabbit-password',
                        name=MC.MISTRAL_SECRET))),
            V1EnvVar(
                name='RABBIT_HOST',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='rabbit-host',
                        name=MC.COMMON_CONFIGMAP))),
            V1EnvVar(
                name='RABBIT_PORT',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='rabbit-port',
                        name=MC.COMMON_CONFIGMAP))),
            V1EnvVar(
                name='RABBIT_VHOST',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='rabbit-vhost',
                        name=MC.COMMON_CONFIGMAP))),
            V1EnvVar(
                name='PG_USER',
                value_from=V1EnvVarSource(
                    secret_key_ref=V1SecretKeySelector(
                        key='pg-user',
                        name=MC.MISTRAL_SECRET))),
            V1EnvVar(
                name='PG_PASSWORD',
                value_from=V1EnvVarSource(
                    secret_key_ref=V1SecretKeySelector(
                        key='pg-password',
                        name=MC.MISTRAL_SECRET))),
            V1EnvVar(
                name='PG_DB_NAME',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='pg-db-name',
                        name=MC.COMMON_CONFIGMAP))),
            V1EnvVar(
                name='PG_HOST',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='pg-host',
                        name=MC.COMMON_CONFIGMAP))),
            V1EnvVar(
                name='PG_PORT',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='pg-port',
                        name=MC.COMMON_CONFIGMAP))),
            V1EnvVar(
                name='PG_IDLE_TIMEOUT',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='pg-idle-timeout',
                        name=MC.COMMON_CONFIGMAP))),
            V1EnvVar(
                name='KAFKA_NOTIFICATIONS_ENABLED',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='kafka-notifications-enabled',
                        name=MC.COMMON_CONFIGMAP))),
            V1EnvVar(
                name='KAFKA_HOST',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='kafka-host',
                        name=MC.COMMON_CONFIGMAP))),
            V1EnvVar(
                name='KAFKA_TOPIC',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='kafka-topic',
                        name=MC.COMMON_CONFIGMAP))),
            V1EnvVar(
                name='KAFKA_CONSUMER_GROUP_ID',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='kafka-consumer-group-id',
                        name=MC.COMMON_CONFIGMAP))),
            V1EnvVar(
                name='KAFKA_TOPIC_PARTITIONS_COUNT',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='kafka-topic-partitions-count',
                        name=MC.COMMON_CONFIGMAP))),
            V1EnvVar(
                name='KAFKA_SECURITY_ENABLED',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='kafka-security-enabled',
                        name=MC.COMMON_CONFIGMAP))),
            V1EnvVar(
                name='KAFKA_SASL_PLAIN_USERNAME',
                value_from=V1EnvVarSource(
                    secret_key_ref=V1SecretKeySelector(
                        key='kafka-sasl-plain-username',
                        name=MC.MISTRAL_SECRET))),
            V1EnvVar(
                name='KAFKA_SASL_PLAIN_PASSWORD',
                value_from=V1EnvVarSource(
                    secret_key_ref=V1SecretKeySelector(
                        key='kafka-sasl-plain-password',
                        name=MC.MISTRAL_SECRET))),
            V1EnvVar(
                name='AUTH_ENABLE',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='auth-enable',
                        name=MC.COMMON_CONFIGMAP))),
            V1EnvVar(
                name='SECURITY_PROFILE',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='security-profile',
                        name=MC.COMMON_CONFIGMAP))),
            V1EnvVar(
                name='SERVER',
                value=server_name.lower()),
            V1EnvVar(
                name='DEBUG_LOG',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='debug-log',
                        name=MC.COMMON_CONFIGMAP))),
            V1EnvVar(
                name='RPC_IMPLEMENTATION',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='rpc-implementation',
                        name=MC.COMMON_CONFIGMAP))),
            V1EnvVar(
                name='MEM_LIMIT',
                value_from=V1EnvVarSource(
                    resource_field_ref=V1ResourceFieldSelector(
                        resource="limits.memory",
                        container_name=name,
                        divisor=0))),
            V1EnvVar(
                name='DBAAS_AGENT_URL',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='dbaas-agent-url',
                        name=MC.COMMON_CONFIGMAP))),
            V1EnvVar(
                name='MULTITENANCY_ENABLED',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='multitenancy-enabled',
                        name=MC.COMMON_CONFIGMAP))),
            V1EnvVar(
                name='NAMESPACE',
                value_from=V1EnvVarSource(
                    field_ref=V1ObjectFieldSelector(
                        field_path='metadata.namespace'))),
            V1EnvVar(
                name='AUTH_TYPE',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='auth-type',
                        name=MC.COMMON_CONFIGMAP))),
            V1EnvVar(
                name='CLEANUP',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='cleanup',
                        name=MC.COMMON_CONFIGMAP))),
        ]

        if self.tls_enabled():
            container_envs.extend(self.get_tls_envs())

        if self.is_cloud_core_integration_enabled():
            container_envs.extend(
                [
                    V1EnvVar(
                        name='IDP_CLIENT_ID',
                        value_from=V1EnvVarSource(
                            secret_key_ref=V1SecretKeySelector(
                                key='username',
                                name='mistral-client-credentials'))),
                    V1EnvVar(
                        name='IDP_CLIENT_SECRET',
                        value_from=V1EnvVarSource(
                            secret_key_ref=V1SecretKeySelector(
                                key='password',
                                name='mistral-client-credentials')))
                ]
            )
        elif self.is_auth_enabled() and self.is_idp_user_precreated():
            container_envs.extend(
                [
                    V1EnvVar(
                        name='IDP_CLIENT_ID',
                        value_from=V1EnvVarSource(
                            secret_key_ref=V1SecretKeySelector(
                                key='idp-client-id',
                                name='idp-precreated-user'))),
                    V1EnvVar(
                        name='IDP_CLIENT_SECRET',
                        value_from=V1EnvVarSource(
                            secret_key_ref=V1SecretKeySelector(
                                key='idp-client-secret',
                                name='idp-precreated-user')))
                ]
            )
        else:
            container_envs.extend(
                [
                    V1EnvVar(
                        name='IDP_CLIENT_ID',
                        value_from=V1EnvVarSource(
                            secret_key_ref=V1SecretKeySelector(
                                key='idp-client-id',
                                name=MC.MISTRAL_SECRET))),
                    V1EnvVar(
                        name='IDP_CLIENT_SECRET',
                        value_from=V1EnvVarSource(
                            secret_key_ref=V1SecretKeySelector(
                                key='idp-client-secret',
                                name=MC.MISTRAL_SECRET)))
                ]
            )

        affinity = None

        if 'affinity' in self._spec[server]:
            affinity = self._api_client.deserialize(
                FakeKubeResponse(self._spec[server]['affinity']),
                'V1Affinity'
            )

        mounts = [
            V1VolumeMount(
                mount_path='/opt/mistral/mount_configs/custom',
                name=MC.MISTRAL_CUSTOM_CONFIG_VOLUME
            )
        ]

        if self.is_secret_present("mistral-tls-secret"):
            mounts.append(
                V1VolumeMount(
                    mount_path='/opt/mistral/mount_configs/tls',
                    name=MC.MISTRAL_TLS_CONFIG_VOLUME,
                    read_only=True
                )
            )

        pod_template_spec = V1PodTemplateSpec(
            metadata=V1ObjectMeta(
                labels=self.get_labels(
                    {
                        'app': MC.MISTRAL_LABEL,
                        'deploymentconfig': name,
                        'name': name
                    }, kubernetes_prefix=server
                )
            ),
            spec=V1PodSpec(containers=[V1Container(
                image=mistral_image,
                name=name,
                resources=container_resources,
                env=container_envs,
                volume_mounts=mounts,
                ports=[V1ContainerPort(
                    container_port=8989,
                    protocol='TCP')],
                image_pull_policy=image_pull_policy,
                readiness_probe=readinessprobe,
                liveness_probe=livenessprobe,
                security_context=self.get_container_security_context()
            )],
                volumes=None,
                affinity=affinity,
                security_context=self.get_security_context(server),
                priority_class_name = None
            )
        )

        mistral_volume_items = [
            V1KeyToPath(key=MC.CUSTOM_CONFIG, path=MC.CUSTOM_CONFIG_FILE_PATH)
        ]

        tls_enabled = self._spec['mistral']['tls']['enabled']
        tls_api_enabled = self._spec['mistral']['tls']['services']['api']['enabled'] and tls_enabled
        tls_monitoring_enabled = self._spec['mistral']['tls']['services']['monitoring']['enabled'] and tls_enabled
        api_scheme = 'HTTPS' if tls_api_enabled else 'HTTP'
        monitoring_scheme = 'HTTPS' if tls_monitoring_enabled else 'HTTP'

        if server_name.lower() == 'api':
            pod_template_spec.spec.containers[0].readiness_probe = \
                MC.get_readiness_probe_api(api_scheme)
            pod_template_spec.spec.containers[0].liveness_probe = \
                MC.LIVENESS_PROBE_API
            pod_template_spec.spec.priority_class_name = self.get_priority_class_name("mistralApi")
            mistral_volume_items.append(
                V1KeyToPath(
                    key=MC.CUSTOM_CONFIG_API, path=MC.ADDITIONAL_CONFIGS_FILE_PATH
                )
            )

        if server_name.lower() == 'executor':
            executor_params = self._spec['mistralExecutor']
            pod_template_spec.spec.containers[0].env.extend(
                [
                    V1EnvVar(
                        name='EXTERNAL_MISTRAL_URL',
                        value_from=V1EnvVarSource(
                            config_map_key_ref=V1ConfigMapKeySelector(
                                key='external-mistral-url',
                                name=MC.COMMON_CONFIGMAP))
                    ),
                    V1EnvVar(
                        name='LOGGING_PROXY_ADMIN_URL',
                        value=None
                        if executor_params.get('loggingProxyAdminUrl') is None
                        else str(executor_params.get('loggingProxyAdminUrl'))
                    ),
                    V1EnvVar(
                        name='CERTIFICATE_STORE',
                        value=str(executor_params.get('certificateStore'))),
                    V1EnvVar(
                        name='RETRIEVER_PORT',
                        value=str(executor_params.get('retrieverPort'))),
                    V1EnvVar(name='HTTP_PROXY',
                             value=None if executor_params.get('httpProxy') is None else
                             str(executor_params.get('httpProxy'))),
                    V1EnvVar(name='HTTPS_PROXY',
                             value=None if executor_params.get('httpsProxy') is None else
                             str(executor_params.get('httpsProxy'))),
                    V1EnvVar(name='NO_PROXY',
                             value=None if executor_params.get('noProxy') is None else
                             str(executor_params.get('noProxy'))),
                ]
            )
            pod_template_spec.metadata.labels['isHttpsClient'] = "true"
            pod_template_spec.metadata.annotations = {
                'certReloadPort': str(executor_params.get('retrieverPort'))}
            pod_template_spec.spec.priority_class_name = self.get_priority_class_name("mistralExecutor")

            mistral_volume_items.append(
                V1KeyToPath(
                    key=MC.CUSTOM_CONFIG_EXECUTOR, path=MC.ADDITIONAL_CONFIGS_FILE_PATH
                )
            )

        if server_name.lower() == 'engine':
            mistral_volume_items.append(
                V1KeyToPath(
                    key=MC.CUSTOM_CONFIG_ENGINE, path=MC.ADDITIONAL_CONFIGS_FILE_PATH
                )
            )
            pod_template_spec.spec.priority_class_name = self.get_priority_class_name("mistralEngine")

        if server_name.lower() == 'notifier':
            kafka_enabled = self._spec['mistralCommonParams']['kafkaNotifications']['enabled']
            if kafka_enabled:
                liveness_probe = MC.get_liveness_probe_kafka()
                pod_template_spec.spec.containers[0].liveness_probe = \
                    liveness_probe
            mistral_volume_items.append(
                V1KeyToPath(
                    key=MC.CUSTOM_CONFIG_NOTIFIER, path=MC.ADDITIONAL_CONFIGS_FILE_PATH
                )
            )
            pod_template_spec.spec.priority_class_name = self.get_priority_class_name("mistralNotifier")

        if server_name.lower() == 'monitoring':
            pod_template_spec.spec.containers[0].readiness_probe = \
                MC.get_readiness_probe_monitoring(monitoring_scheme)
            pod_template_spec.spec.containers[0].liveness_probe = \
                MC.get_readiness_probe_monitoring(monitoring_scheme)
            monitoring_params = self._spec['mistralMonitoring']
            pod_template_spec.spec.containers[0].ports.extend([
                V1ContainerPort(
                    container_port=9090,
                    protocol='TCP'
                )
            ])
            pod_template_spec.spec.containers[0].env.extend(
                [
                    V1EnvVar(
                        name='RECOVERY_INTERVAL',
                        value=str(monitoring_params['recoveryInterval'])),
                    V1EnvVar(
                        name='HANG_INTERVAL',
                        value=str(monitoring_params['hangInterval'])),
                    V1EnvVar(
                        name='RECOVERY_ENABLED',
                        value=str(monitoring_params['recoveryEnabled'])),
                    V1EnvVar(
                        name='MONITORING_EXECUTION_DELAY',
                        value=str(
                            monitoring_params['monitoringExecutionDelay'])
                    ),
                    V1EnvVar(
                        name='MONITORING_ENABLED',
                        value=str(monitoring_params['monitoringEnabled'])),
                    V1EnvVar(
                        name='METRIC_COLLECTION_INTERVAL',
                        value=str(
                            monitoring_params['metricCollectionInterval'])
                    )
                ]
            )
            pod_template_spec.spec.service_account = MC.SERVICE_ACCOUNT
            pod_template_spec.spec.service_account_name = MC.SERVICE_ACCOUNT
            pod_template_spec.spec.priority_class_name = self.get_priority_class_name("mistralMonitoring")

        pod_template_spec.spec.volumes = [
            V1Volume(config_map=V1ConfigMapVolumeSource(
                name=MC.CUSTOM_CONFIGMAP,
                items=mistral_volume_items,
                default_mode=420),
                name=MC.MISTRAL_CUSTOM_CONFIG_VOLUME),
            V1Volume(
                secret=V1SecretVolumeSource(
                    secret_name=MC.MISTRAL_TLS_SECRET,
                    default_mode=416
                ),
                name=MC.MISTRAL_TLS_CONFIG_VOLUME
            )
        ]

        spec = client.V1DeploymentSpec(
            replicas=mistral_replicas,
            revision_history_limit=10,
            selector=V1LabelSelector(match_labels={'app': MC.MISTRAL_LABEL,
                                                   'deploymentconfig': name,
                                                   'name': name}),
            template=pod_template_spec
        )
        body = client.V1Deployment(metadata=meta, spec=spec)
        logger.debug("DC body: " + str(body))
        return body

    def generate_lite_deployment_config_body(self, name):
        livenessprobe = MC.LIVENESS_PROBE_API
        readinessprobe = MC.READINESS_PROBE_API
        readinessprobe.initial_delay_seconds = 120
        livenessprobe.initial_delay_seconds = 120
        livenessprobe.failure_threshold = 45
        readinessprobe.failure_threshold = 45
        mistral_lite_replicas = 1
        ex_params = self._spec['mistralExecutor']
        mistral_resources = self._spec['mistralLite']['resources']
        logger.debug("resources: %s", str(mistral_resources))
        meta = V1ObjectMeta(labels=self.get_labels({'app': MC.MISTRAL_LABEL}),
                            name=name, namespace=self._workspace)
        mistral_image = self._spec['mistral']['dockerImage']

        image_pull_policy = 'Always' if 'latest' in mistral_image.lower() \
            else 'IfNotPresent'

        http_proxy = ex_params['httpProxy'] if 'httpProxy' in ex_params \
            else None
        https_proxy = ex_params['httpsProxy'] if 'httpsProxy' in ex_params \
            else None
        no_proxy = ex_params['noProxy'] if 'noProxy' in ex_params \
            else None

        container_resources = \
            V1ResourceRequirements(
                limits={
                    'cpu': mistral_resources['limits'][
                        'cpu'],
                    'memory':
                        mistral_resources['limits'][
                            'memory']},
                requests={'cpu': mistral_resources['requests']['cpu'],
                          'memory': mistral_resources['requests']['memory']})

        container_envs = [
            V1EnvVar(
                name='QUEUE_NAME_PREFIX',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='queue-name-prefix',
                        name=MC.COMMON_CONFIGMAP))),
            V1EnvVar(
                name='OS_MISTRAL_URL',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='os-mistral-url',
                        name=MC.COMMON_CONFIGMAP))),
            V1EnvVar(
                name='USE_PYPY',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='use-pypy',
                        name=MC.COMMON_CONFIGMAP))),
            V1EnvVar(
                name='GUARANTEED_NOTIFIER_ENABLED',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='guaranteed-notifier-enabled',
                        name=MC.COMMON_CONFIGMAP))),
            V1EnvVar(
                name='IDP_SERVER',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='idp-server',
                        name=MC.COMMON_CONFIGMAP))),
            V1EnvVar(
                name='IDP_CLIENT_ID',
                value_from=V1EnvVarSource(
                    secret_key_ref=V1SecretKeySelector(
                        key='idp-client-id',
                        name=MC.MISTRAL_SECRET))),
            V1EnvVar(
                name='IDP_CLIENT_SECRET',
                value_from=V1EnvVarSource(
                    secret_key_ref=V1SecretKeySelector(
                        key='idp-client-secret',
                        name=MC.MISTRAL_SECRET))),
            V1EnvVar(
                name='IDP_JWK_EXP',
                value_from=V1EnvVarSource(
                    secret_key_ref=V1SecretKeySelector(
                        key='idp-jwk-exp',
                        name=MC.MISTRAL_SECRET))),
            V1EnvVar(
                name='IDP_JWK_MOD',
                value_from=V1EnvVarSource(
                    secret_key_ref=V1SecretKeySelector(
                        key='idp-jwk-mod',
                        name=MC.MISTRAL_SECRET))),
            V1EnvVar(
                name='PG_ADMIN_USER',
                value_from=V1EnvVarSource(
                    secret_key_ref=V1SecretKeySelector(
                        key='pg-admin-user',
                        name=MC.MISTRAL_SECRET))),
            V1EnvVar(
                name='PG_ADMIN_PASSWORD',
                value_from=V1EnvVarSource(
                    secret_key_ref=V1SecretKeySelector(
                        key='pg-admin-password',
                        name=MC.MISTRAL_SECRET))),
            V1EnvVar(
                name='PG_USER',
                value_from=V1EnvVarSource(
                    secret_key_ref=V1SecretKeySelector(
                        key='pg-user',
                        name=MC.MISTRAL_SECRET))),
            V1EnvVar(
                name='PG_PASSWORD',
                value_from=V1EnvVarSource(
                    secret_key_ref=V1SecretKeySelector(
                        key='pg-password',
                        name=MC.MISTRAL_SECRET))),
            V1EnvVar(
                name='KAFKA_NOTIFICATIONS_ENABLED',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='kafka-notifications-enabled',
                        name=MC.COMMON_CONFIGMAP))),
            V1EnvVar(
                name='KAFKA_HOST',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='kafka-host',
                        name=MC.COMMON_CONFIGMAP))),
            V1EnvVar(
                name='KAFKA_TOPIC',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='kafka-topic',
                        name=MC.COMMON_CONFIGMAP))),
            V1EnvVar(
                name='KAFKA_CONSUMER_GROUP_ID',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='kafka-consumer-group-id',
                        name=MC.COMMON_CONFIGMAP))),
            V1EnvVar(
                name='KAFKA_SECURITY_ENABLED',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='kafka-security-enabled',
                        name=MC.COMMON_CONFIGMAP))),
            V1EnvVar(
                name='KAFKA_SASL_PLAIN_USERNAME',
                value_from=V1EnvVarSource(
                    secret_key_ref=V1SecretKeySelector(
                        key='kafka-sasl-plain-username',
                        name=MC.MISTRAL_SECRET))),
            V1EnvVar(
                name='KAFKA_SASL_PLAIN_PASSWORD',
                value_from=V1EnvVarSource(
                    secret_key_ref=V1SecretKeySelector(
                        key='kafka-sasl-plain-password',
                        name=MC.MISTRAL_SECRET))),
            V1EnvVar(
                name='RABBIT_USER',
                value_from=V1EnvVarSource(
                    secret_key_ref=V1SecretKeySelector(
                        key='rabbit-user',
                        name=MC.MISTRAL_SECRET))),
            V1EnvVar(
                name='RABBIT_ADMIN_USER',
                value_from=V1EnvVarSource(
                    secret_key_ref=V1SecretKeySelector(
                        key='rabbit-admin-user',
                        name=MC.MISTRAL_SECRET))),
            V1EnvVar(
                name='RABBIT_PASSWORD',
                value_from=V1EnvVarSource(
                    secret_key_ref=V1SecretKeySelector(
                        key='rabbit-password',
                        name=MC.MISTRAL_SECRET))),
            V1EnvVar(
                name='RABBIT_ADMIN_PASSWORD',
                value_from=V1EnvVarSource(
                    secret_key_ref=V1SecretKeySelector(
                        key='rabbit-admin-password',
                        name=MC.MISTRAL_SECRET))),
            V1EnvVar(
                name='RABBIT_HOST',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='rabbit-host',
                        name=MC.COMMON_CONFIGMAP))),
            V1EnvVar(
                name='RABBIT_PORT',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='rabbit-port',
                        name=MC.COMMON_CONFIGMAP))),
            V1EnvVar(
                name='RABBIT_VHOST',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='rabbit-vhost',
                        name=MC.COMMON_CONFIGMAP))),
            V1EnvVar(
                name='PG_DB_NAME',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='pg-db-name',
                        name=MC.COMMON_CONFIGMAP))),
            V1EnvVar(
                name='PG_HOST',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='pg-host',
                        name=MC.COMMON_CONFIGMAP))),
            V1EnvVar(
                name='PG_PORT',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='pg-port',
                        name=MC.COMMON_CONFIGMAP))),
            V1EnvVar(
                name='PG_IDLE_TIMEOUT',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='pg-idle-timeout',
                        name=MC.COMMON_CONFIGMAP))),
            V1EnvVar(
                name='AUTH_ENABLE',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='auth-enable',
                        name=MC.COMMON_CONFIGMAP))),
            V1EnvVar(
                name='SECURITY_PROFILE',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='security-profile',
                        name=MC.COMMON_CONFIGMAP))),
            V1EnvVar(
                name='SERVER',
                value='api,engine,executor,notifier'),
            V1EnvVar(
                name='DEBUG_LOG',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='debug-log',
                        name=MC.COMMON_CONFIGMAP))),
            V1EnvVar(
                name='RPC_IMPLEMENTATION',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='rpc-implementation',
                        name=MC.COMMON_CONFIGMAP))),
            V1EnvVar(
                name='DBAAS_AGENT_URL',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='dbaas-agent-url',
                        name=MC.COMMON_CONFIGMAP))),
            V1EnvVar(
                name='MULTITENANCY_ENABLED',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='multitenancy-enabled',
                        name=MC.COMMON_CONFIGMAP))),
            V1EnvVar(
                name='NAMESPACE',
                value_from=V1EnvVarSource(
                    field_ref=V1ObjectFieldSelector(
                        field_path='metadata.namespace'))),
            V1EnvVar(
                name='AUTH_TYPE',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='auth-type',
                        name=MC.COMMON_CONFIGMAP))),
            V1EnvVar(
                name='EXTERNAL_MISTRAL_URL',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='external-mistral-url',
                        name=MC.COMMON_CONFIGMAP))
            ),
            V1EnvVar(
                name='CERTIFICATE_STORE',
                value=str(ex_params['certificateStore'])),
            V1EnvVar(
                name='RETRIEVER_PORT',
                value=str(ex_params['retrieverPort'])),
            V1EnvVar(name='HTTP_PROXY',
                     value=None if http_proxy is None else str(http_proxy)),
            V1EnvVar(name='HTTPS_PROXY',
                     value=None if https_proxy is None else str(https_proxy)),
            V1EnvVar(name='NO_PROXY',
                     value=None if no_proxy is None else str(no_proxy)),
            V1EnvVar(name='SKIP_RABBIT_USER_CREATION',
                     value='True'),
        ]

        if self.tls_enabled():
            container_envs.extend(self.get_tls_envs())

        volumes = [V1Volume(config_map=V1ConfigMapVolumeSource(
            name=MC.CUSTOM_CONFIGMAP,
            items=[V1KeyToPath(key=MC.CUSTOM_CONFIG, path=MC.CUSTOM_CONFIG_FILE_PATH)],
            default_mode=420),
            name=MC.MISTRAL_CUSTOM_CONFIG_VOLUME)]

        pod_template_spec = V1PodTemplateSpec(
            metadata=V1ObjectMeta(
                labels=self.get_labels(
                    {
                        'app': MC.MISTRAL_LABEL,
                        'deploymentconfig': name,
                        'name': name,
                        'app.kubernetes.io/name': name,
                        'app.kubernetes.io/instance': name + '-' + self._workspace,
                        'app.kubernetes.io/component': name
                    }
                )
            ),
            spec=V1PodSpec(containers=[V1Container(
                image=mistral_image,
                name=name,
                args=['./upgrade_db_and_start.sh'],
                resources=container_resources,
                env=container_envs,
                volume_mounts=[V1VolumeMount(
                    mount_path='/opt/mistral/mount_configs/custom',
                    name=MC.MISTRAL_CUSTOM_CONFIG_VOLUME
                )],
                ports=[V1ContainerPort(
                    container_port=8989,
                    protocol='TCP')],
                image_pull_policy=image_pull_policy,
                readiness_probe=readinessprobe,
                liveness_probe=livenessprobe,
                security_context=self.get_container_security_context()
            )],
                volumes=volumes,
                security_context=self.get_security_context('mistralLite'),
                priority_class_name=self.get_priority_class_name('mistralLite')
            )
        )

        if self.is_local_rmq():
            self.add_rmq_container_to_deployment(pod_template_spec)

        spec = client.V1DeploymentSpec(
            replicas=mistral_lite_replicas,
            revision_history_limit=10,
            selector=V1LabelSelector(match_labels={'app': MC.MISTRAL_LABEL,
                                                   'deploymentconfig': name,
                                                   'name': name}),
            template=pod_template_spec
        )
        body = client.V1Deployment(metadata=meta, spec=spec)
        logger.debug("DC body: " + str(body))
        return body

    def generate_idp_params(self):
        def get_client_creds(registration_token, client_name,
                             idp_external_server):
            headers = {"Authorization": "Bearer " + registration_token}
            json = {
                "client_name": client_name,
                "grant_types": ["client_credentials", "redelegate"],
                "scope": "profile"
            }

            res = requests.post(
                idp_external_server + "/register",
                headers=headers,
                json=json,
                verify=MC.IDP_CERT_FILE_PATH
            ).json()

            return res['client_id'], res['client_secret']

        def get_jwk(auth_type, idp_external_server):
            if auth_type == "keycloak-oidc":
                res = requests.get(
                    idp_external_server +
                    "/auth/realms/cloud-common/protocol/openid-connect/certs",
                    verify=MC.IDP_CERT_FILE_PATH
                ).json()
            else:
                res = requests.get(
                    idp_external_server + "/jwk",
                    verify=MC.IDP_CERT_FILE_PATH
                ).json()

            return res['keys'][0]['e'], res['keys'][0]['n']

        auth_enabled = self.is_auth_enabled()
        auth_type = self._spec['mistralCommonParams']['auth']['type']

        if not auth_enabled:
            logger.info("Auth is not enabled.")
            return

        idp_server = self._spec['mistralCommonParams'].get('idpServer')
        idp_external_server = self._spec['mistralCommonParams'].get('idpExternalServer')

        if not idp_server:
            logger.error("IDP server was not provided.")
            self.update_status(
                MC.Status.FAILED,
                "Error",
                "IDP server was not provided"
            )
            sleep(5)
            raise kopf.PermanentError("IDP server was not provided.")

        if not idp_external_server:
            logger.info("IDP external server was not provided, "
                        "using idp server instead.")
            idp_external_server = idp_server

        secret = self._v1_apps_api.read_namespaced_secret(
            name=MC.MISTRAL_SECRET,
            namespace=self._workspace
        )

        secret_data = secret.data

        idp_jwk_exp_enc = secret_data.get("idp-jwk-exp")
        if idp_jwk_exp_enc:
            idp_jwk_exp = self.decode_secret(idp_jwk_exp_enc)
        else:
            idp_jwk_exp = None

        idp_jwk_mod_enc = secret_data.get("idp-jwk-mod")
        if idp_jwk_mod_enc:
            idp_jwk_mod = self.decode_secret(idp_jwk_mod_enc)
        else:
            idp_jwk_mod = None

        if idp_jwk_exp and idp_jwk_mod and \
                idp_jwk_exp != 'null' and idp_jwk_mod != 'null':
            logger.info("JWK was already passed. Skipping generation.")
        else:
            logger.info("JWK values were not provided. "
                        "Generating JWK.")
            idp_jwk_exp, idp_jwk_mod = get_jwk(
                auth_type,
                idp_external_server
            )

            logger.info("Patching secret with JWK values.")

            self._v1_apps_api.patch_namespaced_secret(
                name=MC.MISTRAL_SECRET,
                namespace=self._workspace,
                body={
                    'data': {
                        'idp-jwk-exp': base64.b64encode(
                            idp_jwk_exp.encode('utf-8')
                        ).decode('utf-8'),
                        'idp-jwk-mod': base64.b64encode(
                            idp_jwk_mod.encode('utf-8')
                        ).decode('utf-8')
                    }
                }
            )

        if self.is_cloud_core_integration_enabled():
            username_changed = False
            if self.is_secret_present(MC.CLOUD_CORE_SECRET):
                secret = self._v1_apps_api.read_namespaced_secret(
                    name=MC.CLOUD_CORE_SECRET,
                    namespace=self._workspace
                )
                secret_data = secret.data

                current_username = self.decode_secret(secret_data['username'])
                new_username = self.get_cloudcore_username()
                if current_username != new_username:
                    logger.info(
                        'New cloudcore username was found, '
                        'deleting old secret...'
                    )
                    self._v1_apps_api.delete_namespaced_secret(
                        name=MC.CLOUD_CORE_SECRET,
                        namespace=self._workspace
                    )
                    username_changed = True

            if not self.is_secret_present(MC.CLOUD_CORE_SECRET):
                logger.info("Secret not found, generating...")

                username = self.get_cloudcore_username()
                password = ''.join(random.choice(MC.ALPH) for _ in range(64))

                data = {
                    'name': base64.b64encode(
                        MC.MISTRAL_SERVICE.encode('utf-8')
                    ).decode('utf-8'),
                    'username': base64.b64encode(
                        username.encode('utf-8')
                    ).decode('utf-8'),
                    'password': base64.b64encode(
                        password.encode('utf-8')
                    ).decode('utf-8')
                }

                body = client.V1Secret(
                    metadata=V1ObjectMeta(
                        name=MC.CLOUD_CORE_SECRET,
                        labels={f'core.{MC.IDP_SECRET_API_GROUP}/secret-type': 'm2m'}
                    )
                )
                body.api_version = 'v1'
                body.data = data
                body.kind = 'Secret'
                body.type = 'Opaque'
                kopf.adopt(body)
                self._v1_apps_api.create_namespaced_secret(self._workspace, body)
            return username_changed

        if self.is_idp_user_precreated():
            logger.info("IDP user precreated, "
                        "skipping client generation.")
            return

        idp_client_id_enc = secret_data.get("idp-client-id")
        if idp_client_id_enc:
            idp_client_id = self.decode_secret(idp_client_id_enc)
        else:
            idp_client_id = None

        idp_client_secret_enc = secret_data.get("idp-client-secret")
        if idp_client_secret_enc:
            idp_client_secret = self.decode_secret(idp_client_secret_enc)
        else:
            idp_client_secret = None

        if idp_client_id and idp_client_secret and \
                idp_client_id != 'null' and idp_client_secret != 'null':
            logger.info("IDP client ID and client secret were set. "
                        "Skipping generation.")
        else:
            logger.info("IDP client ID or client secret were not set."
                        "Generating using IDP registration token.")

            idp_registration_token = base64.b64decode(
                secret_data["idp-registration-token"]
            ).decode("utf-8")

            if not idp_registration_token or idp_registration_token == 'null':
                logger.error("Could not generate IDP params:"
                             "idp registration token was not provided.")
                self.update_status(
                    MC.Status.FAILED,
                    "Error",
                    "IDP registration token was not provided"
                )
                sleep(5)
                raise kopf.PermanentError("IDP registration token "
                                          "was not provided.")

            idp_client_id, idp_client_secret = get_client_creds(
                idp_registration_token,
                'mistral_' + self._workspace,
                idp_external_server
            )

            logger.info("Patching secret with IDP values.")

            self._v1_apps_api.patch_namespaced_secret(
                name=MC.MISTRAL_SECRET,
                namespace=self._workspace,
                body={
                    'data': {
                        'idp-client-id': base64.b64encode(
                            idp_client_id.encode('utf-8')
                        ).decode('utf-8'),
                        'idp-client-secret': base64.b64encode(
                            idp_client_secret.encode('utf-8')
                        ).decode('utf-8')
                    }
                }
            )

    def add_rmq_container_to_deployment(self, pod_template_spec):
        rmq_image = self._spec['mistralLite']['rabbitmq']['dockerImage']
        rmq_resources = self._spec['mistralLite']['rabbitmq']['resources']
        rmq_livenessprobe = MC.LIVENESS_PROBE_RMQ
        rmq_readinessprobe = MC.READINESS_PROBE_RMQ

        image_pull_policy = 'Always' if 'latest' in rmq_image.lower() \
            else 'IfNotPresent'

        rmq_volume = [
            V1Volume(name='config-volume',
                     config_map=V1ConfigMapVolumeSource(
                         name=MC.RABBIT_CONFIGMAP,
                         default_mode=420,
                         items=[
                             V1KeyToPath(key='rabbitmq.conf',
                                         path='rabbitmq.conf'),
                             V1KeyToPath(key='enabled_plugins',
                                         path='enabled_plugins'),
                             V1KeyToPath(key='advanced.config',
                                         path='advanced.config')
                         ]))
        ]

        rmq_container_envs = [
            V1EnvVar(name='AUTOCLUSTER_DELAY', value='2000'),
            V1EnvVar(name='MY_NODE_NAME', value_from=V1EnvVarSource(
                field_ref=V1ObjectFieldSelector(field_path='spec.nodeName'))),
            V1EnvVar(name='MY_POD_NAME', value_from=V1EnvVarSource(
                field_ref=V1ObjectFieldSelector(field_path='metadata.name'))),
            V1EnvVar(name='MY_POD_NAMESPACE', value_from=V1EnvVarSource(
                field_ref=V1ObjectFieldSelector(
                    field_path='metadata.namespace'))),
            V1EnvVar(name='MY_POD_IP', value_from=V1EnvVarSource(
                field_ref=V1ObjectFieldSelector(field_path='status.podIP'))),
            V1EnvVar(name='MY_POD_SERVICE_ACCOUNT', value_from=V1EnvVarSource(
                field_ref=V1ObjectFieldSelector(
                    field_path='spec.serviceAccountName'))),
            V1EnvVar(name='RABBITMQ_USE_LONGNAME', value='true'),
            V1EnvVar(name='RABBITMQ_NODENAME',
                     value='rabbit@rmqlocal.subdomain.'
                           '$(MY_POD_NAMESPACE).svc.cluster.local'),
            V1EnvVar(name='RABBITMQ_DEFAULT_USER', value_from=V1EnvVarSource(
                secret_key_ref=V1SecretKeySelector(key='user',
                                                   name='rabbitmq-'
                                                        'default-secret'))),
            V1EnvVar(name='RABBITMQ_DEFAULT_PASS', value_from=V1EnvVarSource(
                secret_key_ref=V1SecretKeySelector(key='password',
                                                   name='rabbitmq-'
                                                        'default-secret'))),
            V1EnvVar(name='RABBITMQ_ERLANG_COOKIE', value_from=V1EnvVarSource(
                secret_key_ref=V1SecretKeySelector(key='rmqcookie',
                                                   name='rabbitmq-'
                                                        'default-secret'))),
            V1EnvVar(name='RABBITMQ_ENABLE_IPV6', value='false')
        ]

        rmq_ports = [
            V1ContainerPort(container_port=15672, protocol='TCP'),
            V1ContainerPort(container_port=4369, protocol='TCP'),
            V1ContainerPort(container_port=5671, protocol='TCP'),
            V1ContainerPort(container_port=5672, protocol='TCP'),
            V1ContainerPort(container_port=15671, protocol='TCP'),
            V1ContainerPort(container_port=25672, protocol='TCP'),
            V1ContainerPort(container_port=443, protocol='TCP'),
            V1ContainerPort(container_port=15692, protocol='TCP')
        ]

        rmq_container_resources = \
            V1ResourceRequirements(limits={'cpu': rmq_resources['cpu'],
                                           'memory': rmq_resources['memory']},
                                   requests={'cpu': rmq_resources['cpu'],
                                             'memory':
                                                 rmq_resources['memory']})

        rmq_container_volumemounts = [
            V1VolumeMount(name='config-volume', mount_path='/configmap')
        ]

        rmq_container = V1Container(
            image=rmq_image,
            name='rabbitmq',
            image_pull_policy=image_pull_policy,
            env=rmq_container_envs,
            liveness_probe=rmq_livenessprobe,
            readiness_probe=rmq_readinessprobe,
            ports=rmq_ports,
            resources=rmq_container_resources,
            volume_mounts=rmq_container_volumemounts,
            security_context=self.get_container_security_context()
        )

        pod_template_spec.spec.containers.extend([rmq_container])
        pod_template_spec.spec.volumes.extend(rmq_volume)
        pod_template_spec.spec.hostname = "rmqlocal"
        pod_template_spec.spec.subdomain = "subdomain"
        pod_template_spec.spec.service_account = "rabbitmq"
        pod_template_spec.spec.service_account_name = "rabbitmq"
        pod_template_spec.spec.security_context = self.get_security_context(
            'mistralLite')

    def is_local_rmq(self):
        return self._spec['mistralLite']['includeLocalRmq']

    def is_mistral_lite(self):
        return self._spec['mistral']['liteEnabled']

    def is_auth_enabled(self):
        return self._spec['mistralCommonParams']['auth']['enable']

    def is_cloud_core_integration_enabled(self):
        return self._spec['mistral']['cloudCoreIntegrationEnabled']

    def get_cloudcore_username(self):
        auth_params = self._spec['mistralCommonParams']['auth']
        default_name = f"{self._workspace}_{MC.MISTRAL_SERVICE}"
        if 'cloudCoreUsername' not in auth_params:
            return default_name
        name = self._spec['mistralCommonParams']['auth']['cloudCoreUsername']
        return name if name else default_name

    def is_idp_user_precreated(self):
        return self._spec['mistralCommonParams']['idpUserPrecreated']

    def get_labels(self, current_labels: dict, kubernetes_prefix=""):
        labels = {}
        labels.update(current_labels)

        if kubernetes_prefix and kubernetes_prefix in self._spec['kubernetesLabels']:
            labels['app.kubernetes.io/name'] = self._spec['kubernetesLabels'][kubernetes_prefix]['name']
            labels['app.kubernetes.io/component'] = self._spec['kubernetesLabels'][kubernetes_prefix]['component']
            labels['app.kubernetes.io/instance'] = self._spec['kubernetesLabels'][kubernetes_prefix]['instance']
            labels['app.kubernetes.io/version'] = self._spec['kubernetesLabels'][kubernetes_prefix]['version']
            labels['app.kubernetes.io/part-of'] = self._spec['kubernetesLabels'][kubernetes_prefix]['partOf']
            labels['app.kubernetes.io/managed-by'] = self._spec['kubernetesLabels'][kubernetes_prefix]['managedBy']
            labels['app.kubernetes.io/technology'] = 'python'
        if 'labels' in self._spec:
            labels.update(self._spec['labels'])
        session_id = self._spec.get('deploymentSessionId')
        if session_id:
            labels['deployment.netcracker.com/session-id'] = session_id

        return labels

    def is_secret_present(self, name):
        secrets = self._v1_apps_api.list_namespaced_secret(
            namespace=self._workspace)
        exists = list(
            filter(lambda x: x.metadata.name == name, secrets.items))
        return len(exists) != 0

    def is_secret_updated(self, name, time_delta=180):
        secret = self._v1_apps_api.read_namespaced_secret(
            name, namespace=self._workspace)

        if not secret:
            return False

        last_updated_time = secret.metadata.managed_fields[-1].time
        current_time = datetime.now(timezone.utc)
        update_time_delta = current_time - last_updated_time
        if update_time_delta.seconds <= time_delta:
            return True
        else:
            return False

    def is_configmap_present(self, name):
        config = self._v1_apps_api.list_namespaced_config_map(
            namespace=self._workspace)
        exists = list(
            filter(lambda x: x.metadata.name == name, config.items))
        return len(exists) != 0

    def check_if_tests_are_failed(self, max_timeout=900):
        time = 0
        result = False
        test_status = None
        test_status_summary = None
        ready_replicas = 0
        expected_replicas = 1
        # Wait till mistral integration tests are started successfully
        while ready_replicas != expected_replicas and time < max_timeout:
            deployment = self._apps_api.read_namespaced_deployment(
                name=MC.MISTRAL_TESTS,
                namespace=self._workspace
            )
            ready_replicas = deployment.status.ready_replicas
            sleep(5)
            time = time + 5

        while test_status in (None, "In Progress") and time < max_timeout:
            sleep(5)
            deployment_status = self._apps_api.read_namespaced_deployment_status(
                MC.MISTRAL_OPERATOR, self._workspace)
            status_conditions = deployment_status.status.conditions
            for condition in status_conditions:
                if condition.reason == "IntegrationTestsExecutionStatus":
                    test_status = condition.type
                    test_status_summary = condition.message
                    break
            time = time + 5

        if time >= max_timeout:
            result = True
            logger.info("Operator reached maximum waiting time to receive integration tests"
                        " result, please check mistral-tests logs for more information.")
            return result

        if test_status == "Failed":
            result = True

        logger.info("Robot Tests result Summary: %s", test_status_summary)
        return result

    def generate_mistral_common_configmap_body(self):
        metadata = client.V1ObjectMeta(
            name=MC.COMMON_CONFIGMAP,
            namespace=self._workspace,
        )
        configmap = self._spec['mistralCommonParams']
        configmapdata = {
            'auth-enable': str(configmap['auth']['enable']),
            'auth-type': str(configmap['auth']['type']),
            'dbaas-agent-url': str(configmap['dbaas']['agentUrl']),
            'dbaas-aggregator-url': str(configmap['dbaas'].get('aggregatorUrl')),
            'debug-log': str(configmap['debugLog']),
            'external-mistral-url': str(configmap.get('externalMistralUrl')),
            'guaranteed-notifier-enabled':
                str(configmap['guaranteedNotifierEnabled']),
            'idp-server': str(configmap.get('idpServer', '')),
            'idp-external-server':
                str(configmap.get('idpExternalServer', '')),
            'multitenancy-enabled': str(configmap['multitenancyEnabled']),
            'os-mistral-url': str(configmap['osMistralUrl']),
            'pg-db-name': str(configmap['postgres']['dbName']),
            'pg-host': str(configmap['postgres']['host']),
            'pg-port': str(configmap['postgres']['port']),
            'pg-idle-timeout': str(configmap['postgres']['idleTimeout']),
            'queue-name-prefix': str(configmap['queueNamePrefix']),
            'rabbit-host': str(configmap['rabbit']['host']),
            'rabbit-port': str(configmap['rabbit']['port']),
            'rabbit-vhost': str(configmap['rabbit']['vhost']),
            'rpc-implementation': str(configmap['rpcImplementation']),
            'security-profile': str(configmap['securityProfile']),
            'use-pypy': str(configmap['usePypy']),
            'kafka-notifications-enabled': str(configmap['kafkaNotifications']['enabled']),
            'kafka-host': str(configmap['kafkaNotifications']['host']),
            'kafka-topic': str(configmap['kafkaNotifications']['topic']),
            'kafka-topic-partitions-count': str(
                configmap['kafkaNotifications']['topicPartitionsCount']),
            'kafka-consumer-group-id': str(configmap['kafkaNotifications']['consumerGroupId']),
            'kafka-security-enabled': str(configmap['kafkaNotifications']['securityEnabled']),
            'cleanup': str(configmap.get('cleanup'))
        }

        if self.is_local_rmq():
            configmapdata['rabbit-host'] = 'localhost'
            configmapdata['rabbit-port'] = '5672'
            configmapdata['rabbit-vhost'] = '/'
            configmapdata['guaranteed-notifier-enabled'] = 'False'
            self.create_rmq_configmap()

        configmap = V1ConfigMap(data=configmapdata, kind='ConfigMap',
                                metadata=metadata)
        return configmap

    def create_rmq_configmap(self):
        if not self.is_configmap_present(MC.RABBIT_CONFIGMAP):
            metadata = client.V1ObjectMeta(
                name=MC.RABBIT_CONFIGMAP,
                namespace=self._workspace,
            )

            configmapdata = MC.RABBITMQ_CONFIGMAP_DATA.copy()

            configmap = V1ConfigMap(data=configmapdata, kind='ConfigMap',
                                    metadata=metadata)
            kopf.adopt(configmap)
            self._v1_apps_api.create_namespaced_config_map(
                namespace=self._workspace,
                body=configmap)

    def create_mistral_service(self):
        service_spec = \
            V1ServiceSpec(selector={'deploymentconfig': MC.SELECTOR},
                          ports=[V1ServicePort(
                              name='8989-tcp',
                              port=8989,
                              protocol='TCP',
                              target_port=8989)])

        if self.is_mistral_lite():
            service_spec.selector = {'deploymentconfig': MC.MISTRAL_LABEL}
        session_id = self._spec.get('deploymentSessionId', 'default-session-id')
        service = V1Service(spec=service_spec,
                            metadata=V1ObjectMeta(
                                labels={'app': MC.MISTRAL_LABEL,
                                        'name': MC.MISTRAL_LABEL,
                                        'app.kubernetes.io/name': MC.MISTRAL_LABEL,
                                        'app.kubernetes.io/managed-by': 'Helm',
                                        'app.kubernetes.io/part-of': 'mistral',
                                        'deployment.netcracker.com/session-id': session_id},
                                name=MC.MISTRAL_SERVICE))
        kopf.adopt(service)
        self._v1_apps_api.create_namespaced_service(self._workspace, service)

    def create_mistral_monitoring_service(self):
        service_spec = \
            V1ServiceSpec(selector={'deploymentconfig': 'mistral-monitoring'},
                          ports=[V1ServicePort(
                              name='9090-tcp',
                              port=9090,
                              protocol='TCP',
                              target_port=9090)])

        session_id = self._spec.get('deploymentSessionId', 'default-session-id')
        service = V1Service(spec=service_spec,
                            metadata=V1ObjectMeta(
                                labels={'app': 'mistral-monitoring',
                                        'name': 'mistral-monitoring',
                                        'app.kubernetes.io/name': 'mistral-monitoring',
                                        'app.kubernetes.io/part-of': 'mistral',
                                        'deployment.netcracker.com/session-id': session_id,
                                        'app.kubernetes.io/managed-by': 'Helm'},
                                name='mistral-monitoring'))
        kopf.adopt(service)
        self._v1_apps_api.create_namespaced_service(self._workspace, service)

    def update_mistral_common_configmap(self):
        configmap = self.generate_mistral_common_configmap_body()
        kopf.adopt(configmap)
        if not self.is_configmap_present(MC.COMMON_CONFIGMAP):
            self._v1_apps_api.create_namespaced_config_map(
                namespace=self._workspace,
                body=configmap
            )
        else:
            self._v1_apps_api.replace_namespaced_config_map(
                namespace=self._workspace,
                body=configmap,
                name=MC.COMMON_CONFIGMAP
            )

    def is_db_update_job_present(self):
        jobs = self._batch_v1_api.list_namespaced_job(
            namespace=self._workspace)
        exists = list(
            filter(lambda x: x.metadata.name == MC.UPDATE_DB_JOB,
                   jobs.items))
        return len(exists) != 0

    def update_db_job(self):
        logger.info("Running Update-db job")
        delopt = V1DeleteOptions(propagation_policy='Background',
                                 grace_period_seconds=0)
        if self.is_db_update_job_present():
            logger.info("Deleting old update db job")
            self._batch_v1_api.delete_namespaced_job(
                namespace=self._workspace,
                name=MC.UPDATE_DB_JOB,
                body=delopt
            )
        while self.is_db_update_job_present():
            logger.info("Waiting until old update db job deleted")
            sleep(3)
        self.apply_update_db_job()

    def cleanup_job(self):
        delopt = V1DeleteOptions(propagation_policy='Background',
                                 grace_period_seconds=0)
        if self.is_cleanup_job_present():
            logger.info("Deleting old cleanup job")
            self._batch_v1_api.delete_namespaced_job(
                namespace=self._workspace,
                name=MC.CLEANUP_JOB,
                body=delopt
            )
        while self.is_cleanup_job_present():
            logger.info("Waiting until old cleanup job deleted")
            sleep(3)
        logger.info("Running Cleanup job")
        self.apply_cleanup_job()

    def apply_cleanup_job(self):
        attempts = 36
        sleep_between_iterations = 20
        jobbody = self.generate_cleanup_job_body()
        kopf.adopt(jobbody)
        self._batch_v1_api.create_namespaced_job(self._workspace, jobbody)
        while attempts > 0:
            sleep(sleep_between_iterations)
            cleanup_db_job_status, cleanup_db_job_doc = self.get_job_status(job_name=MC.CLEANUP_JOB)
            if cleanup_db_job_status:
                break
            attempts = attempts - 1
        if attempts == 0 or cleanup_db_job_status == MC.Status.FAILED:
            job_logs = self.get_job_logs(job_doc=cleanup_db_job_doc)
            logger.error(
                "Error with Mistral cleanup db job. Following are failure logs"
                " from Mistral cleanup db job %s", job_logs
            )
            self.update_status(
                MC.Status.FAILED,
                "Error",
                "Error with Mistral cleanup db job. Following are failure logs"
                " from Mistral cleanup db job %s" % job_logs
            )
            sleep(5)
            raise kopf.PermanentError("Error with Mistral cleanup db job.")

    def generate_cleanup_job_body(self):
        cleanup_db_pod_params = self._spec['mistralCleanupDbPod']
        container_resources = \
            V1ResourceRequirements(limits={'cpu': '250m',
                                           'memory':
                                               cleanup_db_pod_params[
                                                   'memoryLimit']},
                                   requests={
                                       'cpu': '150m',
                                       'memory': '256Mi'})
        volumes = [
            V1Volume(
                name=MC.MISTRAL_CUSTOM_CONFIG_VOLUME,
                config_map=V1ConfigMapVolumeSource(
                    name=MC.CUSTOM_CONFIGMAP,
                    items=[V1KeyToPath(key=MC.CUSTOM_CONFIG, path=MC.CUSTOM_CONFIG_FILE_PATH)],
                )
            ),
            V1Volume(
                secret=V1SecretVolumeSource(
                    secret_name=MC.MISTRAL_TLS_SECRET,
                    default_mode=416
                ),
                name=MC.MISTRAL_TLS_CONFIG_VOLUME
            )
        ]
        mounth_path = cleanup_db_pod_params['mountConfigsHome'] + '/custom'
        volume_mounts = \
            [V1VolumeMount(name=MC.MISTRAL_CUSTOM_CONFIG_VOLUME,
                           mount_path=mounth_path)]
        if self.is_secret_present("mistral-tls-secret"):
            volume_mounts.append(
                V1VolumeMount(
                    mount_path='/opt/mistral/mount_configs/tls',
                    name=MC.MISTRAL_TLS_CONFIG_VOLUME,
                    read_only=True
                )
            )

        envs = [
            V1EnvVar(
                name='PG_USER',
                value_from=V1EnvVarSource(
                    secret_key_ref=V1SecretKeySelector(
                        key='pg-user',
                        name=MC.MISTRAL_SECRET))),
            V1EnvVar(
                name='PG_PASSWORD',
                value_from=V1EnvVarSource(
                    secret_key_ref=V1SecretKeySelector(
                        key='pg-password',
                        name=MC.MISTRAL_SECRET))),
            V1EnvVar(
                name='PG_DB_NAME',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='pg-db-name',
                        name=MC.COMMON_CONFIGMAP))),
            V1EnvVar(
                name='PG_HOST',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='pg-host',
                        name=MC.COMMON_CONFIGMAP))),
            V1EnvVar(
                name='PG_PORT',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='pg-port',
                        name=MC.COMMON_CONFIGMAP))),
            V1EnvVar(
                name='PG_IDLE_TIMEOUT',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='pg-idle-timeout',
                        name=MC.COMMON_CONFIGMAP))),
            V1EnvVar(
                name='PG_ADMIN_USER',
                value_from=V1EnvVarSource(
                    secret_key_ref=V1SecretKeySelector(
                        key='pg-admin-user',
                        name=MC.MISTRAL_SECRET))),
            V1EnvVar(
                name='PG_ADMIN_PASSWORD',
                value_from=V1EnvVarSource(
                    secret_key_ref=V1SecretKeySelector(
                        key='pg-admin-password',
                        name=MC.MISTRAL_SECRET))),
            V1EnvVar(
                name='RABBIT_USER',
                value_from=V1EnvVarSource(
                    secret_key_ref=V1SecretKeySelector(
                        key='rabbit-user',
                        name=MC.MISTRAL_SECRET))),
            V1EnvVar(
                name='RABBIT_ADMIN_USER',
                value_from=V1EnvVarSource(
                    secret_key_ref=V1SecretKeySelector(
                        key='rabbit-admin-user',
                        name=MC.MISTRAL_SECRET))),
            V1EnvVar(
                name='RABBIT_PASSWORD',
                value_from=V1EnvVarSource(
                    secret_key_ref=V1SecretKeySelector(
                        key='rabbit-password',
                        name=MC.MISTRAL_SECRET))),
            V1EnvVar(
                name='RABBIT_ADMIN_PASSWORD',
                value_from=V1EnvVarSource(
                    secret_key_ref=V1SecretKeySelector(
                        key='rabbit-admin-password',
                        name=MC.MISTRAL_SECRET))),
            V1EnvVar(
                name='RABBIT_HOST',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='rabbit-host',
                        name=MC.COMMON_CONFIGMAP))),
            V1EnvVar(
                name='RABBIT_PORT',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='rabbit-port',
                        name=MC.COMMON_CONFIGMAP))),
            V1EnvVar(
                name='RABBIT_VHOST',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='rabbit-vhost',
                        name=MC.COMMON_CONFIGMAP))),
            V1EnvVar(
                name='KAFKA_NOTIFICATIONS_ENABLED',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='kafka-notifications-enabled',
                        name=MC.COMMON_CONFIGMAP))),
            V1EnvVar(
                name='KAFKA_HOST',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='kafka-host',
                        name=MC.COMMON_CONFIGMAP))),
            V1EnvVar(
                name='KAFKA_TOPIC',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='kafka-topic',
                        name=MC.COMMON_CONFIGMAP))),
            V1EnvVar(
                name='KAFKA_CONSUMER_GROUP_ID',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='kafka-consumer-group-id',
                        name=MC.COMMON_CONFIGMAP))),
            V1EnvVar(
                name='KAFKA_TOPIC_PARTITIONS_COUNT',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='kafka-topic-partitions-count',
                        name=MC.COMMON_CONFIGMAP))),
            V1EnvVar(
                name='KAFKA_SECURITY_ENABLED',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='kafka-security-enabled',
                        name=MC.COMMON_CONFIGMAP))),
            V1EnvVar(
                name='KAFKA_SASL_PLAIN_USERNAME',
                value_from=V1EnvVarSource(
                    secret_key_ref=V1SecretKeySelector(
                        key='kafka-sasl-plain-username',
                        name=MC.MISTRAL_SECRET))),
            V1EnvVar(
                name='KAFKA_SASL_PLAIN_PASSWORD',
                value_from=V1EnvVarSource(
                    secret_key_ref=V1SecretKeySelector(
                        key='kafka-sasl-plain-password',
                        name=MC.MISTRAL_SECRET))),
            V1EnvVar(
                name='GUARANTEED_NOTIFIER_ENABLED',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='guaranteed-notifier-enabled',
                        name=MC.COMMON_CONFIGMAP))),
            V1EnvVar(
                name='MULTITENANCY_ENABLED',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='multitenancy-enabled',
                        name=MC.COMMON_CONFIGMAP))),
            V1EnvVar(
                name='QUEUE_NAME_PREFIX',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='queue-name-prefix',
                        name=MC.COMMON_CONFIGMAP))),
        ]

        if self.tls_enabled():
            envs.extend(self.get_tls_envs())

        job_pod_spec = V1PodSpec(
            containers=[
                V1Container(
                    name=MC.CLEANUP_JOB,
                    image=self._spec['mistral']['dockerImage'],
                    env=envs,
                    args=[cleanup_db_pod_params['args']],
                    resources=container_resources,
                    image_pull_policy='Always',
                    volume_mounts=volume_mounts,
                    security_context=self.get_container_security_context()
                )
            ],
            volumes=volumes,
            restart_policy='Never',
            security_context=self.get_security_context("mistralCleanupDbPod"),
            priority_class_name=self.get_priority_class_name("mistralCleanupDbPod")
        )

        job_pod_template = V1PodTemplateSpec(
            metadata=V1ObjectMeta(
                name=MC.CLEANUP_JOB,
                labels=self.get_labels(
                    {
                        'job-name': MC.CLEANUP_JOB,
                        'app': MC.CLEANUP_JOB
                    }, kubernetes_prefix="mistralCleanupDbJob"
                ),
                annotations={
                    "argocd.argoproj.io/hook": "PostSync",
                    "argocd.argoproj.io/hook-delete-policy": "HookSucceeded",
                    "helm.sh/hook-delete-policy": "before-hook-creation",
                    "helm.sh/hook": "post-install,post-upgrade",
                    "helm.sh/hook-weight": "10"}
            ),
            spec=job_pod_spec)

        job_spec = V1JobSpec(active_deadline_seconds=720,
                             ttl_seconds_after_finished=420,
                             backoff_limit=2,
                             template=job_pod_template)

        job_template = V1Job(api_version='batch/v1',
                             metadata=V1ObjectMeta(
                                 name=MC.CLEANUP_JOB,
                                 labels=self.get_labels({'app': MC.CLEANUP_JOB}),
                                         annotations={
                                             "argocd.argoproj.io/hook": "PostSync",
                                             "argocd.argoproj.io/hook-delete-policy": "HookSucceeded",
                                             "helm.sh/hook-delete-policy": "before-hook-creation",
                                             "helm.sh/hook": "post-install,post-upgrade",
                                             "helm.sh/hook-weight": "10"}
                             ),
                             kind='Job', spec=job_spec)
        return job_template

    def is_cleanup_job_present(self):
        jobs = self._batch_v1_api.list_namespaced_job(
            namespace=self._workspace)
        exists = list(
            filter(lambda x: x.metadata.name == MC.CLEANUP_JOB,
                   jobs.items))
        return len(exists) != 0

    def should_cleanup(self):
        return self._spec.get('mistralCommonParams', {}).get('cleanup', False)

    def integration_tests_enabled(self):
        enabled = self._spec['integrationTests']['enabled']
        if type(enabled) is bool:
            return enabled
        if type(enabled) is str:
            return enabled.lower() == 'true'
        return False

    def wait_test_result(self):
        wait = self._spec['integrationTests']['waitTestResultOnJob']
        if type(wait) is bool:
            return wait
        if type(wait) is str:
            return wait.lower() == 'true'
        return False

    def run_tests_only(self):
        enabled = self._spec['integrationTests']['runTestsOnly']
        if type(enabled) is bool:
            return enabled
        if type(enabled) is str:
            return enabled.lower() == 'true'
        return False

    def run_benchmarks(self):
        enabled = self._spec['integrationTests']['runBenchmarks']
        if type(enabled) is bool:
            return enabled
        if type(enabled) is str:
            return enabled.lower() == 'true'
        return False

    def initiate_status(self):
        cr = self.get_custom_resource()
        logger.info(cr)
        current = cr.get("status") or {}
        conditions = []
        now = datetime.now(timezone.utc).isoformat()
        cond = {
            "type": MC.Status.IN_PROGRESS,
            "status": True,
            "message": "Mistral operator started deploy process",
            "changed": now
        }

        conditions.append(cond)
        current["conditions"] = conditions
        self.patch_custom_resource_status(current)

    def patch_custom_resource_status(self, status_body):
        self._custom_objects_api.patch_namespaced_custom_object_status(
            group=MC.CR_GROUP,
            version=MC.CR_VERSION,
            namespace=self._workspace,
            plural=MC.CR_PLURAL,
            name=MC.CR_NAME,
            body={"status": status_body},
        )

    def update_status(self, status_type, error, message):
        cr = self.get_custom_resource()
        current = cr.get("status") or {}
        conditions = list(current.get("conditions") or [])
        now = datetime.now(timezone.utc).isoformat()

        new_cond = {
            "type": status_type,
            "status": True,
            "reason": error,
            "message": message,
            "changed": now
        }

        if conditions:
            old_cond_status = {
                "status": False
            }
            found = False
            for c in conditions:
                if c.get("type") == status_type:
                    c.update(new_cond)
                    found = True
                else:
                    c.update(old_cond_status)
            if not found:
                conditions.append(new_cond)
        else:
            conditions.append(new_cond)

        current["conditions"] = conditions
        self.patch_custom_resource_status(current)

    def check_mistral_service_ready(self, service):
        deployment = self._apps_api.read_namespaced_deployment(
            name=service,
            namespace=self._workspace
        )
        ready_replicas = deployment.status.ready_replicas
        if service in MC.SERVICES_NAME_TO_SERVER:
            spec = self._spec['mistral' + MC.SERVICES_NAME_TO_SERVER[service]]
            replicas = int(spec['replicas'])
        else:
            replicas = 1
        return ready_replicas == replicas

    def wait_mistral_ready(self, check_interval=10):
        wait_time = self._spec['integrationTests']['mistralReadyTimeout']
        mistral_ready = False
        time = 0
        while not mistral_ready and time < wait_time:
            logger.info("Waiting until Mistral is ready")
            sleep(check_interval)
            time = time + check_interval
            mistral_ready = True
            if self.is_mistral_lite():
                if self.is_deployment_present(MC.MISTRAL_SERVICE):
                    if not self.check_mistral_service_ready(MC.MISTRAL_SERVICE):
                        mistral_ready = False
            else:
                for service in MC.MISTRAL_SERVICES:
                    if self.is_deployment_present(service):
                        if not self.check_mistral_service_ready(service):
                            mistral_ready = False
                            break
        return mistral_ready

    def run_tests(self):
        logger.info('Integration tests enabled.')
        if not self.is_service_present(MC.MISTRAL_TESTS):
            logger.info('Creating robot tests service.')
            self.create_robot_tests_service()
        else:
            logger.info('Robot tests service already present.')

        template = self.generate_robot_tests_pod_template_body()
        kopf.adopt(template)

        if self.is_deployment_present(MC.MISTRAL_TESTS):
            logger.info('Recreating tests deployment.')
            self.delete_deployment(MC.MISTRAL_TESTS)

        while self.is_deployment_present(MC.MISTRAL_TESTS):
            logger.info("Waiting for older deployment to be deleted.")
            sleep(5)

        logger.info('Creating robot tests deployment.')
        kopf.adopt(template)
        self._apps_api.create_namespaced_deployment(
            self._workspace, template
        )

    def generate_robot_tests_pod_template_body(self):
        tests_params = self._spec['integrationTests']
        container_resources = V1ResourceRequirements(
            limits={
                'cpu': '300m',
                'memory': '300Mi'
            },
            requests={
                'cpu': '300m',
                'memory': '300Mi'
            }
        )

        tls_enabled = self._spec['mistral']['tls']['enabled']
        tls_api_enabled = self._spec['mistral']['tls']['services']['api']['enabled']
        scheme = 'https' if tls_enabled and tls_api_enabled else 'http'

        container_envs = [
            V1EnvVar(
                name='KUBERNETES_NAMESPACE', value_from=V1EnvVarSource(
                    field_ref=V1ObjectFieldSelector(
                        field_path='metadata.namespace')
                )
            ),
            V1EnvVar(
                name='STATUS_CUSTOM_RESOURCE_PATH',
                value='apps/v1/$(KUBERNETES_NAMESPACE)/deployments/' + MC.MISTRAL_OPERATOR
            ),
            V1EnvVar(
                name='MISTRAL_URL',
                value=f"{scheme}://" + MC.MISTRAL_SERVICE + ':8989/v2'
            ),
            V1EnvVar(
                name='MISTRAL_HOST',
                value=MC.MISTRAL_SERVICE
            ),
            V1EnvVar(
                name='OWN_URL',
                value='http://' + MC.MISTRAL_SERVICE + '-tests:8080'
            ),
            V1EnvVar(
                name='VALIDATE',
                value="false"
            ),
            V1EnvVar(
                name='AUTH_ENABLE',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='auth-enable',
                        name=MC.COMMON_CONFIGMAP
                    )
                )
            ),
            V1EnvVar(
                name='AUTH_TYPE',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='auth-type',
                        name=MC.COMMON_CONFIGMAP
                    )
                )
            ),
            V1EnvVar(
                name='IDP_SERVER',
                value_from=V1EnvVarSource(
                    config_map_key_ref=V1ConfigMapKeySelector(
                        key='idp-server',
                        name=MC.COMMON_CONFIGMAP
                    )
                )
            ),
            V1EnvVar(
                name='CLIENT_REGISTRATION_TOKEN',
                value_from=V1EnvVarSource(
                    secret_key_ref=V1SecretKeySelector(
                        key='idp-registration-token',
                        name=MC.MISTRAL_SECRET
                    )
                )
            ),
            V1EnvVar(
                name='IDP_USER',
                value_from=V1EnvVarSource(
                    secret_key_ref=V1SecretKeySelector(
                        key='idp-user-robot',
                        name=MC.MISTRAL_SECRET
                    )
                )
            ),
            V1EnvVar(
                name='IDP_PASSWORD',
                value_from=V1EnvVarSource(
                    secret_key_ref=V1SecretKeySelector(
                        key='idp-password-robot',
                        name=MC.MISTRAL_SECRET
                    )
                )
            )
        ]

        if tls_enabled and tls_api_enabled:
            container_envs.extend(
                [
                    V1EnvVar(
                        name='REQUESTS_CA_BUNDLE',
                        value=MC.MISTRAL_TLS_CA_PATH
                    )
                ]
            )

        if self.run_benchmarks():
            container_envs.extend(
                [
                    V1EnvVar(
                        name='RUN_BENCHMARKS',
                        value='True'
                    )
                ]
            )

        if self._spec['integrationTests'].get('prometheusUrl'):
            container_envs.extend(
                [
                    V1EnvVar(
                        name='PROMETHEUS_URL',
                        value=self._spec['integrationTests']['prometheusUrl']
                    )
                ]
            )

        if self.is_cloud_core_integration_enabled():
            container_envs.extend(
                [
                    V1EnvVar(
                        name='IDP_CLIENT_ID',
                        value_from=V1EnvVarSource(
                            secret_key_ref=V1SecretKeySelector(
                                key='username',
                                name='mistral-client-credentials'))),
                    V1EnvVar(
                        name='IDP_CLIENT_SECRET',
                        value_from=V1EnvVarSource(
                            secret_key_ref=V1SecretKeySelector(
                                key='password',
                                name='mistral-client-credentials')))
                ]
            )
        elif self.is_auth_enabled() and self.is_idp_user_precreated():
            container_envs.extend(
                [
                    V1EnvVar(
                        name='IDP_CLIENT_ID',
                        value_from=V1EnvVarSource(
                            secret_key_ref=V1SecretKeySelector(
                                key='idp-client-id',
                                name='idp-precreated-user'))),
                    V1EnvVar(
                        name='IDP_CLIENT_SECRET',
                        value_from=V1EnvVarSource(
                            secret_key_ref=V1SecretKeySelector(
                                key='idp-client-secret',
                                name='idp-precreated-user')))
                ]
            )
        else:
            container_envs.extend(
                [
                    V1EnvVar(
                        name='IDP_CLIENT_ID',
                        value_from=V1EnvVarSource(
                            secret_key_ref=V1SecretKeySelector(
                                key='idp-client-id',
                                name=MC.MISTRAL_SECRET))),
                    V1EnvVar(
                        name='IDP_CLIENT_SECRET',
                        value_from=V1EnvVarSource(
                            secret_key_ref=V1SecretKeySelector(
                                key='idp-client-secret',
                                name=MC.MISTRAL_SECRET)))
                ]
            )

        meta = V1ObjectMeta(
            labels=self.get_labels({'app': MC.MISTRAL_TESTS}),
            name=MC.MISTRAL_TESTS,
            namespace=self._workspace
        )

        volumes = []
        volume_mounts = []
        if self.is_secret_present(MC.MISTRAL_TLS_SECRET):
            volumes.append(
                V1Volume(
                    secret=V1SecretVolumeSource(
                        secret_name=MC.MISTRAL_TLS_SECRET,
                        default_mode=416
                    ),
                    name=MC.MISTRAL_TLS_CONFIG_VOLUME
                )
            )
            volume_mounts.append(
                V1VolumeMount(
                    mount_path='/opt/mistral/mount_configs/tls',
                    name=MC.MISTRAL_TLS_CONFIG_VOLUME,
                    read_only=True
                )
            )

        pod_template_spec = V1PodTemplateSpec(
            metadata=V1ObjectMeta(
                labels=self.get_labels({
                    'app': MC.MISTRAL_TESTS,
                    'name': MC.MISTRAL_TESTS
                }, kubernetes_prefix="mistralTests")
            ),
            spec=V1PodSpec(
                containers=[V1Container(
                    image=tests_params['dockerImage'],
                    name=MC.MISTRAL_TESTS,
                    resources=container_resources,
                    env=container_envs,
                    ports=[V1ContainerPort(
                        container_port=8080,
                        protocol='TCP'
                    )],
                    image_pull_policy='Always',
                    volume_mounts=volume_mounts,
                    security_context=self.get_container_security_context()
                )],
                security_context=self.get_security_context('integrationTests'),
                service_account=MC.SERVICE_ACCOUNT,
                service_account_name=MC.SERVICE_ACCOUNT,
                volumes=volumes,
                priority_class_name=self.get_priority_class_name('integrationTests')
            )
        )

        spec = client.V1DeploymentSpec(
            replicas=1,
            revision_history_limit=10,
            selector=V1LabelSelector(
                match_labels={
                    'app': MC.MISTRAL_TESTS,
                    'name': MC.MISTRAL_TESTS
                }
            ),
            template=pod_template_spec
        )

        body = client.V1Deployment(metadata=meta, spec=spec)

        return body

    def create_robot_tests_service(self):
        service_spec = V1ServiceSpec(
            selector={
                'app': MC.MISTRAL_TESTS
            },
            ports=[
                V1ServicePort(
                    name='internal',
                    port=8080,
                    protocol='TCP',
                    target_port=8080
                )
            ]
        )
        service = V1Service(
            spec=service_spec,
            metadata=V1ObjectMeta(
                labels={'app': MC.MISTRAL_TESTS},
                name=MC.MISTRAL_TESTS
            )
        )
        kopf.adopt(service)
        self._v1_apps_api.create_namespaced_service(self._workspace, service)

    def is_deployment_present(self, name):
        deployments = self._apps_api.list_namespaced_deployment(
            namespace=self._workspace)
        exists = list(
            filter(lambda x: x.metadata.name == name,
                   deployments.items))
        return len(exists) != 0

    def delete_lite_deployment(self, name):
        if self.is_deployment_present(name):
            self.delete_deployment(name)
            sleep(90)

    def update_deployment(self, name, server_name):
        logger.info("Updating %s deployment.", name)
        deployment_body = self.generate_deployment_config_body(name, server_name)
        kopf.adopt(deployment_body)
        self._apps_api.replace_namespaced_deployment(
            name=name,
            namespace=self._workspace,
            body=deployment_body)

    def update_lite_deployment(self, name):
        deployment_body = self.generate_lite_deployment_config_body(name)
        kopf.adopt(deployment_body)
        if self.is_deployment_present(name):
            self._apps_api.patch_namespaced_deployment(
                name=name,
                namespace=self._workspace,
                body=deployment_body)
        else:
            self._apps_api.create_namespaced_deployment(
                namespace=self._workspace,
                body=deployment_body)

    def is_service_present(self, name):
        services = self._v1_apps_api.list_namespaced_service(
            namespace=self._workspace)
        exists = list(
            filter(lambda x: x.metadata.name == name,
                   services.items))
        return len(exists) != 0

    def delete_mistral_secret(self):
        self._v1_apps_api.delete_namespaced_secret(name=MC.MISTRAL_SECRET,
                                                   namespace=self._workspace)

    def delete_configmap(self, name):
        delopt = V1DeleteOptions(propagation_policy='Background',
                                 grace_period_seconds=0)
        self._v1_apps_api.delete_namespaced_config_map(
            name=name, namespace=self._workspace, body=delopt)

    def delete_db_job(self):
        self._batch_v1_api.delete_namespaced_job(namespace=self._workspace,
                                                 name=MC.UPDATE_DB_JOB)

    def delete_deployment(self, name, force=None):
        if force:
            delopt = V1DeleteOptions(propagation_policy='Background',
                                     grace_period_seconds=0)
            self._apps_api.delete_namespaced_deployment(
                name=name,
                namespace=self._workspace,
                body=delopt
            )
        else:
            self._apps_api.delete_namespaced_deployment(
                name=name,
                namespace=self._workspace
            )

    def delete_mistral_service(self):
        delopt = V1DeleteOptions(propagation_policy='Background',
                                 grace_period_seconds=0)
        self._v1_apps_api.delete_namespaced_service(namespace=self._workspace,
                                                    name=MC.MISTRAL_SERVICE,
                                                    body=delopt)

    def scale_down_mistral_deployments(self, attempts=6, timeout=10):
        logger.info("Mistral scale down started")
        for deployment in MC.MISTRAL_SERVICES:
            if not self.is_deployment_present(deployment):
                logger.info("Can not scale down mistral: no deployment found.")
                return
            scale = self._apps_api.read_namespaced_deployment_scale(
                deployment, self._workspace
            )
            scale.spec.replicas = 0
            self._apps_api.patch_namespaced_deployment_scale(
                deployment, self._workspace, scale
            )

        while attempts:
            services_down = 0
            for deployment in MC.MISTRAL_SERVICES:
                dp_status = self._apps_api.read_namespaced_deployment_status(
                    deployment, self._workspace
                )
                if not dp_status.status.replicas:
                    services_down += 1
            if services_down == len(MC.MISTRAL_SERVICES):
                logger.info("Mistral scale down completed")
                return
            attempts -= 1
            logger.info("Mistral scale down is not completed yet, waiting...")
            sleep(timeout)
        logger.info("Mistral was not scaled down during switchover process")

    def scale_up_mistral_deployments(self, attempts=12, timeout=10):
        logger.info("Mistral scale up started")
        replicas = {}
        for service in MC.MISTRAL_SERVICES:
            spec = self._spec['mistral' + MC.SERVICES_NAME_TO_SERVER[service]]
            replicas[service] = int(spec['replicas'])
        for deployment in MC.MISTRAL_SERVICES:
            scale = self._apps_api.read_namespaced_deployment_scale(
                deployment, self._workspace
            )
            scale.spec.replicas = replicas[deployment]
            self._apps_api.patch_namespaced_deployment_scale(
                deployment, self._workspace, scale
            )

        while attempts:
            services_ready = 0
            for deployment in MC.MISTRAL_SERVICES:
                dp_status = self._apps_api.read_namespaced_deployment_status(
                    deployment, self._workspace
                )
                available_replicas = dp_status.status.available_replicas
                if available_replicas and available_replicas == replicas[deployment]:
                    services_ready += 1
            if services_ready == len(MC.MISTRAL_SERVICES):
                logger.info("Mistral scale up completed")
                return
            attempts -= 1
            logger.info("Mistral scale up is not completed yet, waiting...")
            sleep(timeout)
        logger.info("Mistral was not scaled up during switchover process")

    def get_custom_resource(self):
        cr = self._custom_objects_api.get_namespaced_custom_object(
            group=MC.CR_GROUP,
            version=MC.CR_VERSION,
            namespace=self._workspace,
            plural=MC.CR_PLURAL,
            name=MC.CR_NAME
        )
        return cr

    def update_custom_resource(self, body):
        self._custom_objects_api.patch_namespaced_custom_object(
            group=MC.CR_GROUP,
            version=MC.CR_VERSION,
            namespace=self._workspace,
            plural=MC.CR_PLURAL,
            name=MC.CR_NAME,
            body=body
        )

    def set_deploy_status_and_run_tests(self):
        if not self.wait_mistral_ready():
            self.update_status(
                MC.Status.FAILED,
                "Error",
                "Mistral service unavailable"
            )
            sleep(5)
            raise kopf.PermanentError("Mistral service unavailable.")
        if not self.wait_test_result() or not self.integration_tests_enabled():
            self.update_status(
                MC.Status.SUCCESSFUL,
                "None",
                "Mistral service installed successfully"
            )
        if self.integration_tests_enabled():
            if self.wait_test_result() and not self.run_benchmarks():
                self.run_tests()
                max_timeout = self._spec['integrationTests']['waitTestResultTimeout']
                if self.check_if_tests_are_failed(max_timeout):
                    self.update_status(
                        MC.Status.FAILED,
                        "Error",
                        "Mistral critical tests failed"
                    )
                    sleep(5)
                    raise kopf.PermanentError("Mistral critical tests failed.")
                else:
                    self.update_status(
                        MC.Status.SUCCESSFUL,
                        "None",
                        "Mistral service installed and tested successfully."
                    )
            else:
                message = "Mistral service installed successfully." \
                    " Detailed Integration tests result will be logged in " \
                    "mistral-operator logs and mistral-operator deployment status" \
                    " condition IntegrationTestsExecutionStatus, once it is completed."
                self.run_tests()
                self.update_status(
                    MC.Status.SUCCESSFUL,
                    "None",
                    message
                )
                logger.info(message)
                Thread(target=self.check_if_tests_are_failed).start()

    def update_disaster_recovery_status(self, mode=None, status=None, message=None):
        disaster_recovery_status = {
            key: value for key, value in zip(['mode', 'status', 'message'], [mode, status, message])
            if value is not None
        }
        cr = self.get_custom_resource()
        current = cr.get("status") or {}
        current["disasterRecoveryStatus"] = disaster_recovery_status
        self.patch_custom_resource_status(current)

    def decode_secret(self, secret):
        return base64.b64decode(secret).decode("utf-8")

    def get_rmq_helper(self):
        mistral_secret = self._v1_apps_api.read_namespaced_secret(MC.MISTRAL_SECRET, self._workspace)
        mistral_secret_data = mistral_secret.data
        rabbit_user = self.decode_secret(mistral_secret_data["rabbit-user"])
        rabbit_password = self.decode_secret(mistral_secret_data["rabbit-password"])
        admin_user = self.decode_secret(mistral_secret_data["rabbit-admin-user"])
        admin_password = self.decode_secret(mistral_secret_data["rabbit-admin-password"])
        rabbit_host = self._spec['mistralCommonParams']["rabbit"]["host"]
        rabbit_vhost = self._spec['mistralCommonParams']["rabbit"]["vhost"]
        queue_name_prefix = self._spec['mistralCommonParams']["queueNamePrefix"]
        return RabbitMQHelper(rabbit_host=rabbit_host,
                              rabbit_vhost=rabbit_vhost,
                              rabbit_user=rabbit_user,
                              rabbit_password=rabbit_password,
                              admin_user=admin_user,
                              admin_password=admin_password,
                              queue_name_prefix=queue_name_prefix
                              )

    def create_rabbit_credentials(self):
        rq_helper = self.get_rmq_helper()
        rq_helper.create_rabbit_user()
        rq_helper.create_rabbit_vhost()
        rq_helper.add_rabbit_permissions()

    def delete_existing_queues(self):
        rq_helper = self.get_rmq_helper()
        rq_helper.delete_existing_queues()

    def check_if_rmq_exchange_durable(self):
        rq_helper = self.get_rmq_helper()
        rabbit_vhost = self._spec['mistralCommonParams']["rabbit"]["vhost"]
        url = f"exchanges/{rabbit_vhost}/openstack"
        exchange_response = rq_helper.request(url=url, method="GET")
        if exchange_response.status_code == 200:
            exchange_response = exchange_response.json()
            logger.info("RabbitMQ exchange is durable.")
            return exchange_response.get("durable", False)
        else:
            logger.info("RabbitMQ exchange is not durable.")
            return False

    def tls_enabled(self):
        return self._spec['mistral']['tls']['enabled']

    def get_tls_envs(self):
        return [
            V1EnvVar(
                name='MISTRAL_TLS_ENABLED',
                value=str(self._spec['mistral']['tls']['services']['api']['enabled'])
            ),
            V1EnvVar(
                name='MISTRAL_MONITORING_TLS_ENABLED',
                value=str(self._spec['mistral']['tls']['services']['monitoring']['enabled'])
            ),
            V1EnvVar(
                name='RABBITMQ_TLS_ENABLED',
                value=str(self._spec['mistral']['tls']['services']['rabbitmq']['enabled'])
            ),
            V1EnvVar(
                name='KAFKA_TLS_ENABLED',
                value=str(self._spec['mistral']['tls']['services']['kafka']['enabled'])
            ),
            V1EnvVar(
                name='PGSSLMODE',
                value=self._spec['mistral']['tls']['services']['postgres']['sslmode']
            ),
        ]
