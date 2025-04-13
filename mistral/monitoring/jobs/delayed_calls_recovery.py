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

import collections
import datetime

from oslo_config import cfg
from oslo_log import log as logging

CONF = cfg.CONF
LOG = logging.getLogger(__name__)


class DelayedCallsRecoveryJob(base.MonitoringJob):
    def __init__(self):
        super(DelayedCallsRecoveryJob, self).__init__(
            interval=CONF.recovery_job.recovery_interval, first_execute=True)

    def get_name(self):
        return "delayed calls recovery"

    def execute(self):
        with db_api.transaction():
            self._process_delayed_calls(
                template_success_message="Recovered calls",
                fail_message="There are no calls for recovery"
            )

    def _process_delayed_calls(self, template_success_message, fail_message):
        calls = db_api.get_calls_for_recovery(
            datetime.timedelta(seconds=CONF.recovery_job.hang_interval)
        )

        if len(calls):
            log = str(datetime.datetime.now())
            recovered = collections.Counter()
            for call in calls:
                call.processing = False
                recovered[call.target_method_name] += 1

                log += "\n{message}. ID: {0}, key: {1}, " \
                       "factory method: {2}, target method: {3}, " \
                       "method_arguments: {4}, execution time: {5}, " \
                       "updated_at: {6}". \
                    format(call.id, call.key,
                           call.factory_method_path, call.target_method_name,
                           call.method_arguments, call.execution_time,
                           call.updated_at,
                           message=template_success_message)

            LOG.info(log)
        else:
            LOG.debug(fail_message)
