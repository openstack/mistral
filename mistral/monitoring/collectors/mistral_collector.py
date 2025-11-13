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

from datetime import datetime

from mistral.db.v2 import api as db_api
from mistral.monitoring import base
from mistral.workflow import states

from pbr.version import VersionInfo
from oslo_config import cfg
from oslo_log import log as logging

CONF = cfg.CONF
LOG = logging.getLogger(__name__)
MISTRAL_VERSION = VersionInfo('mistral').release_string()

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
        self._update_task_retries()
        self._update_execution_time()

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

    def _update_task_retries(self):
        retry_counts = db_api.get_task_retries(limit=50)

        task_retries_tags = {
            "name": "mistral_task_retries",
            "description": "Retry count for task executions",
            "namespace": self._namespace,
            "labels": [
                'namespace',
                'workflow_execution_id',
                'task_name'
            ]
        }

        for (execution_id, task_name), retries in retry_counts.items():
            base.add_metric(
                self._metrics_data,
                'mistral_task_retries',
                fields={
                    "value": retries,
                    "namespace": self._namespace,
                    "workflow_execution_id": execution_id,
                    "task_name": task_name
                },
                tags=task_retries_tags
            )

    def _update_execution_time(self):
        wf_exes = db_api.get_recent_workflow_executions(limit=50)
        now = datetime.utcnow()

        time_tags = {
            "name": "mistral_execution_time",
            "description": "Workflow execution time in seconds",
            "namespace": self._namespace,
            "labels": [
                "namespace",
                "workflow_name",
                "execution_id",
                "state"
            ],
        }

        created_tags = {
            "name": "mistral_execution_created_timestamp",
            "description": "Start time of workflow execution (UNIX timestamp)",
            "namespace": self._namespace,
            "labels": [
                "namespace",
                "workflow_name",
                "execution_id"
            ],
        }

        for wf in wf_exes:
            exec_time = (
                (now - wf.created_at).total_seconds()
                if states.is_active_state(wf.state) or wf.updated_at is None
                else (wf.updated_at - wf.created_at).total_seconds()
            )

            base.add_metric(
                self._metrics_data,
                "mistral_execution_time",
                fields={
                    "value": exec_time,
                    "namespace": self._namespace,
                    "workflow_name": wf.name,
                    "execution_id": wf.id,
                    "state": wf.state,
                },
                tags=time_tags
            )

            base.add_metric(
                self._metrics_data,
                "mistral_execution_created_timestamp",
                fields={
                    "value": wf.created_at.timestamp(),
                    "namespace": self._namespace,
                    "workflow_name": wf.name,
                    "execution_id": wf.id,
                },
                tags=created_tags
            )
