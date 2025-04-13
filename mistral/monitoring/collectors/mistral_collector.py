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

from mistral.db.v2 import api as db_api
from mistral.monitoring import base
from mistral.workflow import states

from opensource_version import MISTRAL_VERSION
from oslo_config import cfg
from oslo_log import log as logging

CONF = cfg.CONF
LOG = logging.getLogger(__name__)

TASK_STATES = [
    states.IDLE,
    states.WAITING,
    states.RUNNING,
    states.RUNNING_DELAYED,
    states.PAUSED,
    states.SUCCESS,
    states.CANCELLED,
    states.ERROR,
]

WORKFLOW_STATES = [
    states.RUNNING,
    states.PAUSED,
    states.SUCCESS,
    states.CANCELLED,
    states.ERROR,
]

ACTION_STATES = [
    states.RUNNING,
    states.PAUSED,
    states.SUCCESS,
    states.CANCELLED,
    states.ERROR
]

DC_TARGET_METHODS = [
    'mistral.engine.task_handler._refresh_task_state',
    'mistral.engine.task_handler._scheduled_on_action_complete',
    'mistral.engine.task_handler._scheduled_on_action_update',
    'mistral.engine.workflow_handler._check_and_complete',
    'mistral.engine.policies._continue_task',
    'mistral.engine.policies._complete_task',
    'mistral.engine.policies._fail_task_if_incomplete',
    'mistral.services.maintenance._pause_executions',
    'mistral.services.maintenance._resume_executions',
]

MAINTENANCE_STATUS_MAP = {
    'RUNNING': 0,
    'PAUSING': 1,
    'PAUSED': 2
}


class MistralMetricCollector(base.MetricCollector):
    def __init__(self):
        self._metrics_data = []
        self._namespace = CONF.monitoring.namespace

    def collect(self):
        self._metrics_data = []

        self._update_maintenance_status()
        self._update_e2e_smoke_status()
        self._update_action_count()
        self._update_task_count()
        self._update_workflow_count()
        self._update_delayed_call_count()
        self._update_mistral_version()

        return self._metrics_data

    def _update_maintenance_status(self):
        status = db_api.get_maintenance_status()
        maintenance_status_tags = {
            "name": "mistral_maintenance_status",
            "description": "Mistral's maintenance status",
            "namespace": self._namespace,
            "labels": ['namespace']
        }
        value = MAINTENANCE_STATUS_MAP[status]
        base.add_metric(
            self._metrics_data,
            'mistral_maintenance_status',
            fields={"value": value},
            tags=maintenance_status_tags
        )

    def _update_e2e_smoke_status(self):
        status = 0  # not supported
        smoke_status_tags = {
            "name": "mistral_smoke_status",
            "description": "Mistral's E2E smoke status",
            "namespace": self._namespace,
            "labels": ['namespace']
        }
        base.add_metric(
            self._metrics_data,
            'mistral_maintenance_status',
            fields={"value": status},
            tags=smoke_status_tags
        )

    def _update_action_count(self):
        counts = dict(db_api.get_action_execution_count_by_state())
        action_count_tags = {
            "name": "mistral_action_count",
            "description": "Count of action by state",
            "namespace": self._namespace,
            "labels": ['namespace', 'state']
        }

        for state in ACTION_STATES:
            base.add_metric(
                self._metrics_data,
                'mistral_entities',
                fields={"state": str(state),
                        "value": counts.get(state, 0)},
                tags=action_count_tags
            )

    def _update_task_count(self):
        counts = dict(db_api.get_task_execution_count_by_state())
        task_count_tags = {
            "name": "mistral_task_count",
            "description": "Count of tasks by state",
            "namespace": self._namespace,
            "labels": ['namespace', 'state']
        }

        for state in TASK_STATES:
            base.add_metric(
                self._metrics_data,
                'mistral_entities',
                fields={"state": str(state),
                        "value": counts.get(state, 0)},
                tags=task_count_tags
            )

    def _update_workflow_count(self):
        counts = dict(db_api.get_workflow_execution_count_by_state())
        workflow_count_tags = {
            "name": "mistral_workflow_count",
            "description": "Count of workflows by state",
            "namespace": self._namespace,
            "labels": ['namespace', 'state']
        }

        for state in WORKFLOW_STATES:
            base.add_metric(
                self._metrics_data,
                'mistral_entities',
                fields={"state": str(state),
                        "value": counts.get(state, 0)},
                tags=workflow_count_tags
            )

    def _update_delayed_call_count(self):
        counts = dict(db_api.get_delayed_calls_count_by_target())
        delayed_calls_tags = {
            "name": "mistral_delayed_calls_count",
            "description": "Count of delayed calls by target method",
            "namespace": self._namespace,
            "labels": ['namespace', 'target']
        }

        for target in DC_TARGET_METHODS:
            base.add_metric(
                self._metrics_data,
                "mistral_entities",
                fields={"target": str(target).lower(),
                        "value": counts.get(target, 0)},
                tags=delayed_calls_tags
            )

    def _update_mistral_version(self):
        version_tags = {
            "name": "mistral_version",
            "description": "Version of OpenStack Mistral",
            "namespace": self._namespace,
            "labels": ['namespace', 'version']
        }
        base.add_metric(
            self._metrics_data,
            'mistral_version',
            fields={
                "version": MISTRAL_VERSION,
                "value": 1
            },
            tags=version_tags
        )
