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

import abc
import threading

import eventlet
import six

from oslo_log import log as logging
LOG = logging.getLogger(__name__)


class Metric(object):
    def __init__(self, measurement, fields, tags=None):
        self.measurement = measurement
        self.fields = fields
        self.tags = tags

    def __repr__(self):
        return "measurement: {}, fields: {}, tags: {}".format(
            self.measurement, self.fields, self.tags
        )


def add_metric(metrics, group, tags={}, fields={}):
    metrics.append(Metric(
        measurement=group,
        fields=fields,
        tags=tags
    ))


@six.add_metaclass(abc.ABCMeta)
class MetricCollector(object):
    """Metric collector unit interface"""

    @abc.abstractmethod
    def collect(self):
        raise NotImplementedError()


@six.add_metaclass(abc.ABCMeta)
class MonitoringJob(object):

    def __init__(self, interval=60, first_execute=False):
        self._interval = interval
        self._job_execution_thread = threading.Thread(
            target=self._execute_job
        )
        self._job_execution_thread.daemon = True
        self._stopped = True

        self._was_executed = first_execute

    def get_name(self):
        raise NotImplementedError()

    def execute(self):
        raise NotImplementedError()

    def _execute_job(self):
        while not self._stopped:
            LOG.debug(
                "Starting monitoring job. "
                "[job_name=%s]", self.get_name()
            )

            if self._was_executed:
                eventlet.sleep(self._interval)

            try:
                self._was_executed = True
                self.execute()

            except Exception:
                LOG.exception(
                    "Monitoring job failed to unexpected exception "
                    "[job_name=%s]", self.get_name()
                )

    def start(self):
        self._stopped = False
        self._job_execution_thread.start()

    def stop(self, graceful=False):
        self._stopped = True
        if graceful:
            self._job_execution_thread.join()
