# -*- coding: utf-8 -*-
#
# Copyright 2013 - Mirantis, Inc.
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
from mistral.db.v2 import api as db_api_v2
from mistral.engine.rpc_backend import rpc
from mistral import exceptions as exc
from mistral.services import security
from mistral.services import triggers

LOG = logging.getLogger(__name__)

CONF = cfg.CONF

# {periodic_task: thread_group}
_periodic_tasks = {}


class MistralPeriodicTasks(periodic_task.PeriodicTasks):
    @periodic_task.periodic_task(spacing=1, run_immediately=True)
    def process_cron_triggers_v2(self, ctx):
        for t in triggers.get_next_cron_triggers():
            LOG.debug("Processing cron trigger: %s" % t)

            # Setup admin context before schedule triggers.
            ctx = security.create_context(t.trust_id, t.project_id)

            auth_ctx.set_ctx(ctx)

            LOG.debug("Cron trigger security context: %s" % ctx)

            try:
                # Try to advance the cron trigger next_execution_time and
                # remaining_executions if relevant.
                modified = advance_cron_trigger(t)

                # If cron trigger was not already modified by another engine.
                if modified:
                    LOG.debug(
                        "Starting workflow '%s' by cron trigger '%s'",
                        t.workflow.name, t.name
                    )

                    rpc.get_engine_client().start_workflow(
                        t.workflow.name,
                        t.workflow_input,
                        description="Workflow execution created "
                                    "by cron trigger.",
                        **t.workflow_params
                    )
            except Exception:
                # Log and continue to next cron trigger.
                LOG.exception("Failed to process cron trigger %s" % str(t))
            finally:
                auth_ctx.set_ctx(None)


def advance_cron_trigger(t):
    modified_count = 0

    try:
        # If the cron trigger is defined with limited execution count.
        if t.remaining_executions is not None and t.remaining_executions > 0:
            t.remaining_executions -= 1

        # If this is the last execution.
        if t.remaining_executions == 0:
            modified_count = db_api_v2.delete_cron_trigger(t.name)
        else:  # if remaining execution = None or > 0.
            next_time = triggers.get_next_execution_time(
                t.pattern,
                t.next_execution_time
            )

            # Update the cron trigger with next execution details
            # only if it wasn't already updated by a different process.
            updated, modified_count = db_api_v2.update_cron_trigger(
                t.name,
                {
                    'next_execution_time': next_time,
                    'remaining_executions': t.remaining_executions
                },
                query_filter={
                    'next_execution_time': t.next_execution_time
                }
            )
    except exc.DBEntityNotFoundError as e:
        # Cron trigger was probably already deleted by a different process.
        LOG.debug(
            "Cron trigger named '%s' does not exist anymore: %s",
            t.name, str(e)
        )

    # Return True if this engine was able to modify the cron trigger in DB.
    return modified_count > 0


def setup():
    tg = threadgroup.ThreadGroup()
    pt = MistralPeriodicTasks(CONF)

    ctx = auth_ctx.MistralContext(
        user_id=None,
        project_id=None,
        auth_token=None,
        is_admin=True
    )

    tg.add_dynamic_timer(
        pt.run_periodic_tasks,
        initial_delay=None,
        periodic_interval_max=1,
        context=ctx
    )

    _periodic_tasks[pt] = tg

    return tg


def stop_all_periodic_tasks():
    for pt, tg in _periodic_tasks.items():
        tg.stop()
        del _periodic_tasks[pt]
