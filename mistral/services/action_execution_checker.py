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

import datetime
import eventlet
import sys

from mistral import context as auth_ctx
from mistral.db import utils as db_utils
from mistral.db.v2 import api as db_api
from mistral.engine import action_handler
from mistral.engine import post_tx_queue
from mistral import utils
from mistral_lib import actions as mistral_lib
from oslo_config import cfg
from oslo_log import log as logging

LOG = logging.getLogger(__name__)

CONF = cfg.CONF

_stopped = True


@db_utils.retry_on_db_error
@post_tx_queue.run
def handle_expired_actions():
    LOG.debug("Running heartbeat checker...")

    interval = CONF.action_heartbeat.check_interval
    max_missed = CONF.action_heartbeat.max_missed_heartbeats

    exp_date = utils.utc_now_sec() - datetime.timedelta(
        seconds=max_missed * interval
    )

    with db_api.transaction():
        action_exs = db_api.get_running_expired_sync_action_executions(
            exp_date,
            CONF.action_heartbeat.batch_size
        )

        LOG.debug("Found {} running and expired actions.".format(
            len(action_exs))
        )

        if action_exs:
            LOG.info(
                "Actions executions to transit to error, because "
                "heartbeat wasn't received: {}".format(action_exs)
            )

            for action_ex in action_exs:
                result = mistral_lib.Result(
                    error="Heartbeat wasn't received."
                )

                action_handler.on_action_complete(action_ex, result)


def _loop():
    global _stopped

    # This is an administrative thread so we need to set an admin
    # security context.
    auth_ctx.set_ctx(
        auth_ctx.MistralContext(
            user=None,
            tenant=None,
            auth_token=None,
            is_admin=True
        )
    )

    while not _stopped:
        try:
            handle_expired_actions()
        except Exception:
            LOG.exception(
                'Action execution checker iteration failed'
                ' due to unexpected exception.'
            )

            # For some mysterious reason (probably eventlet related)
            # the exception is not cleared from the context automatically.
            # This results in subsequent log.warning calls to show invalid
            # info.
            if sys.version_info < (3,):
                sys.exc_clear()

        eventlet.sleep(CONF.action_heartbeat.check_interval)


def start():
    interval = CONF.action_heartbeat.check_interval
    max_missed = CONF.action_heartbeat.max_missed_heartbeats

    enabled = interval and max_missed

    if not enabled:
        LOG.info("Action heartbeat reporting is disabled.")

        return

    wait_time = interval * max_missed

    LOG.debug(
        "First run of action execution checker, wait before "
        "checking to make sure executors have time to send "
        "heartbeats. ({} seconds)".format(wait_time)
    )

    global _stopped

    _stopped = False

    eventlet.spawn_after(wait_time, _loop)


def stop(graceful=False):
    global _stopped

    _stopped = True
