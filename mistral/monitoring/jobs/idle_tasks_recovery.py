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
from mistral.monitoring import base
from mistral.scheduler import base as sched_base

import datetime

from oslo_config import cfg
from oslo_log import log as logging

CONF = cfg.CONF
LOG = logging.getLogger(__name__)


class IdleTasksRecoveryJob(base.MonitoringJob):
    def __init__(self):
        super(IdleTasksRecoveryJob, self).__init__(
            interval=CONF.recovery_job.recovery_interval, first_execute=True)

    _task_run_path = (
        'mistral.engine.task_handler._start_task'
    )

    def get_name(self):
        return "idle tasks recovery"

    def execute(self):
        auth_ctx.set_ctx(
            auth_ctx.MistralContext(
                user=None,
                project_id=None,
                auth_token=None,
                is_admin=True
            )
        )
        with db_api.transaction():
            self._process_idle_tasks()

    def get_idle_tasks(self):
        return db_api.get_expired_idle_task_executions(
            timeout=datetime.timedelta(
                seconds=CONF.recovery_job.idle_task_timeout
            )
        )

    def _get_task_run_key(self, task_ex):
        return 't_ex_r-%s' % task_ex.id

    def _process_idle_tasks(self):
        task_executions = self.get_idle_tasks()
        sched = sched_base.get_system_scheduler()
        for task_ex in task_executions:
            auth_ctx.set_ctx(
                auth_ctx.MistralContext(
                    user=None,
                    project_id=None,
                    auth_token=None,
                    is_admin=True
                )
            )

            wf_ex = db_api.get_workflow_execution(
                task_ex.workflow_execution_id)

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

            job_exist = sched.has_scheduled_jobs(
                key=self._get_task_run_key(task_ex),
                processing=False
            )

            if job_exist:
                return

            job = sched_base.SchedulerJob(
                run_after=1.5,
                func_name=self._task_run_path,
                func_args={
                    'task_ex_id': task_ex.id,
                    'first_run':
                        task_ex['runtime_context']['recovery']['first_run'],
                    'waiting': False,
                    'triggered_by': task_ex.get('triggered_by'),
                    'rerun': task_ex['runtime_context']['recovery']['rerun'],
                    'reset': task_ex['runtime_context']['recovery']['reset']
                },
                key=self._get_task_run_key(task_ex)
            )

            sched.schedule(job)
