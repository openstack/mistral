# Copyright 2015 - Mirantis, Inc.
# Copyright 2016 - Brocade Communications Systems, Inc.
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
import functools
from oslo_log import log as logging

from mistral import context
from mistral.db import utils as db_utils
from mistral.db.v2 import api as db_api
from mistral import utils


"""
This module contains a mini framework for scheduling operations while
performing transactional processing of a workflow event such as
completing a workflow action. The scheduled operations will run after
the main DB transaction, in a new transaction, if needed.
"""

LOG = logging.getLogger(__name__)


_THREAD_LOCAL_NAME = "__operation_queue_thread_local"


def _prepare():
    # Register two queues: transactional and non transactional operations.
    utils.set_thread_local(_THREAD_LOCAL_NAME, (list(), list()))


def _clear():
    utils.set_thread_local(_THREAD_LOCAL_NAME, None)


def register_operation(func, args=None, in_tx=False):
    """Register an operation."""

    _get_queues()[0 if in_tx else 1].append((func, args or []))


def _get_queues():
    queues = utils.get_thread_local(_THREAD_LOCAL_NAME)

    if queues is None:
        raise RuntimeError(
            'Operation queue is not initialized for the current thread.'
            ' Most likely some engine method is not decorated with'
            ' operation_queue.run()'
        )

    return queues


def run(func):
    """Decorator that runs all operations registered in the operation queue.

    Various engine methods may register such operations. All such methods must
    be decorated with this decorator.
    """
    @functools.wraps(func)
    def decorate(*args, **kw):
        _prepare()

        try:
            res = func(*args, **kw)

            queues = _get_queues()

            tx_queue = queues[0]
            non_tx_queue = queues[1]

            if not tx_queue and not non_tx_queue:
                return res

            auth_ctx = context.ctx() if context.has_ctx() else None

            def _within_new_thread():
                old_auth_ctx = context.ctx() if context.has_ctx() else None

                context.set_ctx(auth_ctx)

                try:
                    if tx_queue:
                        _process_tx_queue(tx_queue)

                    if non_tx_queue:
                        _process_non_tx_queue(non_tx_queue)
                finally:
                    context.set_ctx(old_auth_ctx)

            eventlet.spawn(_within_new_thread)
        finally:
            _clear()

        return res

    return decorate


@db_utils.retry_on_db_error
@run
def _process_tx_queue(queue):
    with db_api.transaction():
        for func, args in queue:
            try:
                func(*args)
            except Exception:
                LOG.exception("Failed to run transactional engine operation.")

                raise


def _process_non_tx_queue(queue):
    for func, args in queue:
        try:
            func(*args)
        except Exception:
            LOG.exception("Failed to run non-transactional engine operation.")
