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

from mistral import context as auth_ctx
from mistral.db.v2 import api as db_api
from mistral.engine import workflow_handler as w_h
from mistral.monitoring import base

import datetime

from oslo_config import cfg
from oslo_log import log as logging

CONF = cfg.CONF
LOG = logging.getLogger(__name__)


class SubworkflowCompleteRecoveryJob(base.MonitoringJob):
    def __init__(self):
        super(SubworkflowCompleteRecoveryJob, self).__init__(
            interval=CONF.recovery_job.stucked_subwf_task_timeout,
            first_execute=True
        )

    def get_name(self):
        return "complete subworkflow recovery"

    def execute(self):
        timeout = datetime.timedelta(
            seconds=CONF.recovery_job.stucked_subwf_task_timeout
        )

        with db_api.transaction():
            auth_ctx.set_ctx(
                auth_ctx.MistralContext(
                    user=None,
                    project_id=None,
                    auth_token=None,
                    is_admin=True
                )
            )
            task_executions = db_api.get_stucked_subwf_tasks(timeout)
            LOG.info(f"Found {len(task_executions)} stucked subwf tasks.")

            for task_id in task_executions:
                auth_ctx.set_ctx(
                    auth_ctx.MistralContext(
                        user=None,
                        project_id=None,
                        auth_token=None,
                        is_admin=True
                    )
                )
                task_ex = db_api.get_task_execution(task_id)

                wf_ex = db_api.get_workflow_execution(
                    task_ex.workflow_execution_id
                )

                if wf_ex.root_execution_id:
                    root_execution_id = wf_ex.root_execution_id
                else:
                    root_execution_id = wf_ex.id

                auth_ctx.set_ctx(
                    auth_ctx.MistralContext(
                        project_id=task_ex.project_id,
                        root_execution_id=root_execution_id
                    )
                )

                w_h._schedule_check_and_fix_integrity(
                    wf_ex,
                    CONF.engine.execution_integrity_check_delay
                )
