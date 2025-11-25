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

from oslo_config import cfg
from oslo_log import log as logging

CONF = cfg.CONF
LOG = logging.getLogger(__name__)


class NamedLocksRecoveryJob(base.MonitoringJob):
    def __init__(self):
        super(NamedLocksRecoveryJob, self).__init__(
            interval=CONF.recovery_job.recovery_interval, first_execute=True)

    def get_name(self):
        return "named locks recovery"

    def execute(self):
        self._delete_frozen_named_locks()

    def _delete_frozen_named_locks(self):
        with db_api.transaction():
            auth_ctx.set_ctx(
                auth_ctx.MistralContext(
                    user=None,
                    project_id=None,
                    auth_token=None,
                    is_admin=True
                )
            )
            deleted_count = db_api.delete_named_locks()
            if deleted_count:
                log = f'No of Named locks was removed: {deleted_count}'
                LOG.debug(log)
            else:
                LOG.debug('There are not any frozen named locks present')
