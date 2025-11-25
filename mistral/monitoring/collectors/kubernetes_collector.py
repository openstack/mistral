# Copyright 2025 - NetCracker Technology Corp.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from kubernetes import client
from kubernetes import config as k8s_config
from mistral.monitoring import base
from oslo_log import log as logging

MISTRAL_APPS = ["mistral-api", "mistral-engine",
                "mistral-executor", "mistral-notifier",
                "mistral-monitoring"]
MISTRAL_LABEL_SELECTOR = "app=mistral"
MISTRAL_APPS_METRIC_GROUP = "mistral_apps"
MISTRAL_CLUSTER_METRIC_GROUP = "mistral_cluster"

LOG = logging.getLogger(__name__)

try:
    k8s_config.load_incluster_config()
except k8s_config.ConfigException:
    LOG.error(
        "Can't load incluster kubernetes config. "
        "Failed to collect metrics from Kubernetes Collector")


SERVICE_STATE = {
    "RUNNING": 0,
    "DEGRADED": 1,
    "DOWN": 2
}


class KubernetesMetricCollector(base.MetricCollector):
    SA_NAMESPACE_PATH = '/var/run/secrets/kubernetes.io/' \
                        'serviceaccount/namespace'

    def __init__(self):
        self._api_client = client.ApiClient()
        self._workspace = open(self.SA_NAMESPACE_PATH).read()
        self._apps_api = client.AppsV1Api(self._api_client)

    def collect(self):
        mistral_deployments = self._apps_api.list_namespaced_deployment(
            namespace=self._workspace,
            label_selector=MISTRAL_LABEL_SELECTOR
        )
        metrics_data = []
        available_apps = []
        any_down = False
        all_replicas = 0
        all_available_replicas = 0

        mistral_replicas_tags = {
            "name": "mistral_replicas",
            "description": "Count of mistral replicas",
            "namespace": self._workspace,
            "labels": ['namespace', 'name']
        }

        mistral_available_replicas_tags = {
            "name": "mistral_available_replicas",
            "description": "Count of mistral available replicas",
            "namespace": self._workspace,
            "labels": ['namespace', 'name']
        }

        mistral_state_tags = {
            "name": "mistral_state",
            "description": "State of mistral app",
            "namespace": self._workspace,
            "labels": ['namespace', 'name']
        }

        mistral_cluster_tags = {
            "name": "mistral_cluster",
            "description": "State of mistral cluster",
            "namespace": self._workspace,
            "labels": ['namespace']
        }

        for deployment in mistral_deployments.items:
            available_apps.append(deployment.metadata.name)

            replicas_ = deployment.status.replicas \
                if deployment.status.replicas else 0
            available_replicas_ = deployment.status.available_replicas \
                if deployment.status.available_replicas else 0

            state = SERVICE_STATE["RUNNING"]
            if replicas_ > available_replicas_:
                state = SERVICE_STATE["DEGRADED"]
            if available_replicas_ == 0:
                state = SERVICE_STATE["DOWN"]
                any_down = True

            base.add_metric(
                metrics_data,
                'mistral_replicas',
                fields={
                    "name": deployment.metadata.name,
                    "value": replicas_
                },
                tags=mistral_replicas_tags
            )

            base.add_metric(
                metrics_data,
                'mistral_available_replicas',
                fields={
                    "name": deployment.metadata.name,
                    "value": available_replicas_
                },
                tags=mistral_available_replicas_tags
            )

            base.add_metric(
                metrics_data,
                'mistral_state',
                fields={
                    "name": deployment.metadata.name,
                    "value": state
                },
                tags=mistral_state_tags
            )

            all_replicas += replicas_
            all_available_replicas += available_replicas_

        unavailable_apps = set(MISTRAL_APPS) - set(available_apps)
        if unavailable_apps:
            any_down = True
            for app in unavailable_apps:
                base.add_metric(
                    metrics_data,
                    'mistral_replicas',
                    fields={
                        "name": app,
                        "value": 0
                    },
                    tags=mistral_replicas_tags
                )
                base.add_metric(
                    metrics_data,
                    'mistral_available_replicas',
                    fields={
                        "name": app,
                        "value": 0
                    },
                    tags=mistral_available_replicas_tags
                )
                base.add_metric(
                    metrics_data,
                    'mistral_state',
                    fields={
                        "name": app,
                        "value": SERVICE_STATE["DOWN"]
                    },
                    tags=mistral_state_tags
                )

        state = SERVICE_STATE["RUNNING"]
        if all_replicas > all_available_replicas or any_down:
            state = SERVICE_STATE["DEGRADED"]

        if all_available_replicas == 0:
            state = SERVICE_STATE["DOWN"]

        base.add_metric(
            metrics_data,
            'mistral_cluster',
            fields={
                "value": state
            },
            tags=mistral_cluster_tags
        )
        return metrics_data
