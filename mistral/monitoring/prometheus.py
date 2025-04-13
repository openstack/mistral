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

import prometheus_client
from prometheus_client import Gauge

from oslo_log import log as logging

LOG = logging.getLogger(__name__)

_GRAPH = {}


def format_to_prometheus(metrics_list):

    for metric in metrics_list:
        metric_tags = metric['tags']
        metric_name = metric_tags.get('name')
        if not metric_name:
            LOG.error('Unable to parse metric')
            continue

        metric_labels = metric_tags.get('labels')
        metric_fields = metric['fields']
        metric_value = metric_fields['value']

        metric_label_values = {
            label: metric_fields[label]
            for label in metric_labels if label != 'namespace'
        }

        if 'namespace' in metric_labels:
            metric_label_values['namespace'] = metric_tags.get('namespace')

        if not _GRAPH.get(metric_name):
            _GRAPH[metric_name] = Gauge(
                metric_name,
                metric_tags.get('description'),
                metric_labels
            )
        _GRAPH[metric_name].labels(**metric_label_values).set(metric_value)

    res = []
    for key in _GRAPH:
        res.append(prometheus_client.generate_latest(_GRAPH[key]))

    return res
