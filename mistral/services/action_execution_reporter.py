# Copyright 2018 Nokia Networks.
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

from oslo_config import cfg
from oslo_log import log as logging
from oslo_service import periodic_task
from oslo_service import threadgroup

from mistral import context as auth_ctx
from mistral.rpc import clients as rpc

LOG = logging.getLogger(__name__)

CONF = cfg.CONF


class ActionExecutionReporter(periodic_task.PeriodicTasks):
    """The reporter that reports the running action executions."""

    def __init__(self, conf):
        super(ActionExecutionReporter, self).__init__(conf)
        self._engine_client = rpc.get_engine_client()
        self._running_actions = set()

        self.interval = CONF.action_heartbeat.check_interval
        self.max_missed = CONF.action_heartbeat.max_missed_heartbeats
        self.enabled = self.interval and self.max_missed

        _periodic_task = periodic_task.periodic_task(
            spacing=self.interval,
            run_immediately=True
        )
        self.add_periodic_task(
            _periodic_task(report)
        )

    def add_action_ex_id(self, action_ex_id):
        # With run-action there is no actions_ex_id assigned
        if action_ex_id and self.enabled:
            self._engine_client.report_running_actions([action_ex_id])
            self._running_actions.add(action_ex_id)

    def remove_action_ex_id(self, action_ex_id):
        if action_ex_id and self.enabled:
            self._running_actions.discard(action_ex_id)


def report(reporter, ctx):
    LOG.debug("Running heartbeat reporter...")

    if not reporter._running_actions:
        return

    auth_ctx.set_ctx(ctx)
    reporter._engine_client.report_running_actions(reporter._running_actions)


def setup(action_execution_reporter):
    interval = CONF.action_heartbeat.check_interval
    max_missed = CONF.action_heartbeat.max_missed_heartbeats
    enabled = interval and max_missed
    if not enabled:
        LOG.info("Action heartbeat reporting disabled.")
        return None

    tg = threadgroup.ThreadGroup()

    ctx = auth_ctx.MistralContext(
        user=None,
        tenant=None,
        auth_token=None,
        is_admin=True
    )

    tg.add_dynamic_timer(
        action_execution_reporter.run_periodic_tasks,
        initial_delay=None,
        periodic_interval_max=1,
        context=ctx
    )

    return tg
