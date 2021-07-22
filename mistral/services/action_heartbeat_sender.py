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

import eventlet

from oslo_config import cfg
from oslo_log import log as logging

from mistral import context as auth_ctx
from mistral.rpc import clients as rpc

LOG = logging.getLogger(__name__)

CONF = cfg.CONF


_enabled = False
_stopped = True

_running_actions = set()


def add_action(action_ex_id):
    global _enabled

    # With run-action there is no actions_ex_id assigned.
    if action_ex_id and _enabled:
        rpc.get_engine_client().process_action_heartbeats([action_ex_id])

        _running_actions.add(action_ex_id)


def remove_action(action_ex_id):
    global _enabled

    if action_ex_id and _enabled:
        _running_actions.discard(action_ex_id)


def send_action_heartbeats():
    LOG.debug('Running heartbeat sender...')

    global _running_actions

    if not _running_actions:
        return

    rpc.get_engine_client().process_action_heartbeats(_running_actions)


def _loop():
    global _stopped

    # This is an administrative thread so we need to set an admin
    # security context.
    auth_ctx.set_ctx(
        auth_ctx.MistralContext(
            user_id=None,
            project_id=None,
            auth_token=None,
            is_admin=True
        )
    )

    while not _stopped:
        try:
            send_action_heartbeats()
        except Exception:
            LOG.exception(
                'Action heartbeat sender iteration failed'
                ' due to an unexpected exception.'
            )

        eventlet.sleep(CONF.action_heartbeat.check_interval)


def start():
    global _stopped, _enabled

    interval = CONF.action_heartbeat.check_interval
    max_missed = CONF.action_heartbeat.max_missed_heartbeats

    _enabled = interval and max_missed

    if not _enabled:
        LOG.info("Action heartbeat reporting is disabled.")

        return

    _stopped = False

    eventlet.spawn(_loop)


def stop(graceful=False):
    global _stopped

    _stopped = True
