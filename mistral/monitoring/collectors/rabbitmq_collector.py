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

import requests

from mistral.monitoring import base

from oslo_config import cfg
from oslo_log import log as logging

CONF = cfg.CONF
LOG = logging.getLogger(__name__)

SERVICE_STATE = {
    "RUNNING": 0,
    "DEGRADED": 1,
    "DOWN": 2
}


class RabbitMQMetricCollector(object):

    def __init__(self):
        self._namespace = CONF.monitoring.namespace

        self.vhost = CONF.rabbitmq.virtual_host
        if self.vhost == '/' or self.vhost == "":
            self.vhost = "%2F"

        self.management_url = 'http://%s:%s/api' % \
                              (CONF.rabbitmq.management_host,
                               CONF.rabbitmq.management_port)

        self.username = CONF.rabbitmq.user
        self.password = CONF.rabbitmq.password
        self.queues = ["_mistral_engine",
                       "_mistral_executor",
                       "_mistral_notifier"]

    def collect(self):
        queue_prefix = self._namespace

        metrics_data = []

        rabbitmq_queues_tags = {
            "name": "rabbitmq_queues",
            "description": "Count of messages in RabbitMQ queue",
            "namespace": self._namespace,
            "labels": ['namespace', 'queue']
        }

        rabbitmq_status_tags = {
            "name": "rabbitmq_status",
            "description": "State of RabbitMQ cluster",
            "namespace": self._namespace,
            "labels": ['namespace']
        }

        try:
            response = requests.get(
                self.management_url,
                auth=(self.username, self.password)
            )
        except requests.ConnectionError:
            for app in self.queues:
                base.add_metric(
                    metrics_data,
                    'rabbitmq_queues',
                    fields={
                        "queue": app,
                        "value": 0
                    },
                    tags=rabbitmq_queues_tags
                )
            base.add_metric(
                metrics_data,
                'rabbitmq_status',
                fields={
                    "value": SERVICE_STATE["DOWN"]
                },
                tags=rabbitmq_status_tags
            )

            return metrics_data

        if response.ok:
            base.add_metric(
                metrics_data,
                'rabbitmq_status',
                fields={
                    "value": SERVICE_STATE["RUNNING"]
                },
                tags=rabbitmq_status_tags
            )

            for app in self.queues:
                url = '%s/queues/%s/%s' % \
                      (self.management_url,
                       self.vhost, queue_prefix + app)
                try:
                    response = requests.get(
                        url,
                        auth=(self.username, self.password)
                    )

                    messages_count = response.json()["messages"]
                except KeyError:
                    messages_count = 0

                base.add_metric(
                    metrics_data,
                    'rabbitmq_queues',
                    fields={
                        "queue": app,
                        "value": messages_count
                    },
                    tags=rabbitmq_queues_tags
                )

        else:
            for app in self.queues:
                base.add_metric(
                    metrics_data,
                    'rabbitmq_queues',
                    fields={
                        "queue": app,
                        "value": 0
                    },
                    tags=rabbitmq_queues_tags
                )

            base.add_metric(
                metrics_data,
                'rabbitmq_status',
                fields={
                    "value": SERVICE_STATE["DOWN"]
                },
                tags=rabbitmq_status_tags
            )

        return metrics_data
