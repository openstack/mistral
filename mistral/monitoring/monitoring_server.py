#  Copyright 2023 - NetCracker Technology Corp.
# Modified in 2025 by NetCracker Technology Corp.
#
#  Licensed under the Apache License, Version 2.0 (the "License"); you may
#  not use this file except in compliance with the License. You may obtain
#  a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#  WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#  License for the specific language governing permissions and limitations
#  under the License.

import datetime
import ssl

from flask import Flask
from flask import jsonify
from flask import Response
from importlib_metadata import entry_points

from mistral.monitoring.prometheus import format_to_prometheus
from mistral.service import base as service_base

from oslo_config import cfg
from oslo_log import log as logging

CONF = cfg.CONF
LOG = logging.getLogger(__name__)


def get_oslo_service(setup_profiler=True):
    return MonitoringServer(
        setup_profiler=setup_profiler
    )


class MonitoringServer(service_base.MistralService):

    def __init__(self, setup_profiler=True):
        super(MonitoringServer, self).__init__(
            'monitoring_group',
            setup_profiler
        )
        collectors = entry_points(group='monitoring.metric_collector')
        self._metric_collectors = [collector.load()()
                                   for collector in collectors]
        self._jobs = []
        self._standard_tags = {}
        self._metrics = {}
        self._prometheus_formatted_metrics = []
        self._last_updated = None
        self._timedelta = datetime.timedelta(
            seconds=CONF.monitoring.metric_collection_interval
        )

        self.app = Flask(__name__)
        self.app.add_url_rule('/metrics', 'metrics', self.metrics)
        self.app.add_url_rule('/health', 'health', self.health)

    def collect_metrics(self, to_json=False):
        now = datetime.datetime.now()
        if not self._last_updated or self._outdated(now):
            metrics = []
            for collector in self._metric_collectors:
                metrics.extend(collector.collect())

            for metric in metrics:
                metric.tags.update(self._standard_tags)

            self._metrics = metrics

            self._last_updated = now

        if to_json:
            return list(map(lambda x: x.__dict__, self._metrics))

        return self._metrics

    def _outdated(self, now):
        return self._last_updated <= now - self._timedelta

    def _get_prometheus_metrics(self):
        metrics = self.collect_metrics(to_json=True)
        pr_metrics = format_to_prometheus(metrics)
        return ''.join([line.decode('utf-8') for line in pr_metrics])

    def metrics(self):
        with self.app.app_context():
            m = self._get_prometheus_metrics()
            return Response(m, 200, content_type='text/plain')

    def health(self):
        with self.app.app_context():
            return jsonify({'status': 'UP'})

    def _init_monitoring_jobs(self):
        if CONF.recovery_job.enabled:
            recovery_jobs = entry_points(group='monitoring.recovery_jobs')
            for job in recovery_jobs:
                recovery_job = job.load()()
                self._jobs.append(recovery_job)
                recovery_job.start()

    def start(self):
        super(MonitoringServer, self).start()
        self._init_monitoring_jobs()
        if CONF.monitoring.tls_enabled:
            cert_dir = "/opt/mistral/mount_configs/tls/"
            context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
            context.load_cert_chain(
                cert_dir + "tls.crt",
                cert_dir + "tls.key"
            )
            context.load_verify_locations(cert_dir + "ca.crt")

            self.app.run(host="0.0.0.0", port=9090, ssl_context=context)
        else:
            self.app.run(host="0.0.0.0", port=9090)

    def stop(self, graceful=False):
        super(MonitoringServer, self).stop()
        for job in self._jobs:
            job.stop(graceful)
