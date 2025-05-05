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

from asyncio import iscoroutinefunction
from fastapi import FastAPI
from fastapi import Response
from importlib_metadata import entry_points
import uvicorn

from oslo_config import cfg
from oslo_log import log as logging
from prometheus_client import CONTENT_TYPE_LATEST

from mistral.monitoring.prometheus import format_to_prometheus
from mistral.service import base as service_base


CONF = cfg.CONF
LOG = logging.getLogger(__name__)


app = FastAPI(title="Mistral Monitoring Service")

server = None


def get_oslo_service(setup_profiler=True):
    global server
    if not server:
        server = MonitoringServer(setup_profiler=setup_profiler)
    return server


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
        self._metrics = []
        self._last_updated = None
        self._timedelta = datetime.timedelta(
            seconds=CONF.monitoring.metric_collection_interval
        )

        self._prometheus_cache = ""
        self._prometheus_last_updated = None

    async def collect_metrics(self, to_json=False):
        now = datetime.datetime.now()
        if not self._last_updated or self._outdated(now):
            metrics = []
            for collector in self._metric_collectors:
                if hasattr(collector, "collect_async"):
                    metrics.extend(await collector.collect_async())
                elif iscoroutinefunction(collector.collect):
                    metrics.extend(await collector.collect())
                else:
                    metrics.extend(collector.collect())

            for metric in metrics:
                metric.tags.update(self._standard_tags)

            self._metrics = metrics
            self._last_updated = now

        if to_json:
            return [m.__dict__ for m in self._metrics]
        return self._metrics

    def _outdated(self, now):
        if self._last_updated is None:
            return True
        return self._last_updated <= now - self._timedelta

    async def _get_prometheus_metrics(self):
        if (
            not self._prometheus_last_updated
            or self._prometheus_last_updated
            <= datetime.datetime.now() - self._timedelta
        ):
            now = datetime.datetime.now()

            metrics = await self.collect_metrics(to_json=True)
            formatted = format_to_prometheus(metrics)
            self._prometheus_cache = ''.join(
                line.decode('utf-8') for line in formatted
            )

            self._prometheus_last_updated = now

        return self._prometheus_cache

    def _init_monitoring_jobs(self):
        if CONF.recovery_job.enabled:
            recovery_jobs = entry_points(group='monitoring.recovery_jobs')
            for job in recovery_jobs:
                recovery_job = job.load()()
                self._jobs.append(recovery_job)
                recovery_job.start()

    def start(self):
        super().start()
        self._init_monitoring_jobs()
        LOG.info("Launched monitoring server with Uvicorn")

        if CONF.monitoring.tls_enabled:
            cert_dir = "/opt/mistral/mount_configs/tls/"
            tls_cert_path = cert_dir + "tls.crt"
            tls_key_path = cert_dir + "tls.key"
            tls_ca_path = cert_dir + "ca.crt"
            LOG.info("SSL/TLS mode on for monitoring")

            uvicorn.run(
                app,
                host="0.0.0.0",
                port=9090,
                ssl_certfile=tls_cert_path,
                ssl_keyfile=tls_key_path,
                ssl_ca_certs=tls_ca_path
            )
        else:
            uvicorn.run(app, host="0.0.0.0", port=9090)

    def stop(self, graceful=False):
        super().stop()
        for job in self._jobs:
            job.stop(graceful)


@app.get("/health")
def health():
    return {"status": "UP"}


@app.get("/metrics")
async def metrics():
    prometheus_data = await get_oslo_service()._get_prometheus_metrics()
    return Response(content=prometheus_data, media_type=CONTENT_TYPE_LATEST)
