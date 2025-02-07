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

import functools
from oslo_config import cfg
from oslo_log import log as logging
from osprofiler import profiler
import threading

from mistral import context
from mistral.db import utils as db_utils
from mistral.db.v2 import api as db_api
from mistral_lib import utils


"""
This module contains a mini framework for scheduling operations while
performing transactional processing of a workflow event such as
completing a workflow action. The scheduled operations will run after
the main DB transaction, in a new transaction, if needed.
"""

LOG = logging.getLogger(__name__)


_THREAD_LOCAL_NAME = "__operation_queue_thread_local"


def _prepare():
    # Register queue for both transactional and non transactional operations.
    utils.set_thread_local(_THREAD_LOCAL_NAME, list())


def _clear():
    utils.set_thread_local(_THREAD_LOCAL_NAME, None)


def register_operation(func, args=None, in_tx=False):
    """Register an operation.

    An operation can be transactional (in_tx=True) or not.
    """

    _get_queue().append((func, args or [], in_tx))


def _get_queue():
    queue = utils.get_thread_local(_THREAD_LOCAL_NAME)

    if queue is None:
        raise RuntimeError(
            'Operation queue is not initialized for the current thread.'
            ' Most likely some engine method is not decorated with'
            ' operation_queue.run()'
        )

    return queue


def run(func):
    """Decorator that runs all operations registered in the operation queue.

    Various engine methods may register such operations. All such methods must
    be decorated with this decorator.
    Take a look at default_engine methods with @post_tx_queue.run
    """
    @functools.wraps(func)
    def decorate(*args, **kw):
        _prepare()

        try:
            res = func(*args, **kw)

            queue = _get_queue()

            if not queue:
                return res

            auth_ctx = context.ctx() if context.has_ctx() else None

            def _within_new_thread():
                # This is a new thread so we need to init a profiler again.
                if cfg.CONF.profiler.enabled:
                    profiler.init(cfg.CONF.profiler.hmac_keys)

                old_auth_ctx = context.ctx() if context.has_ctx() else None

                context.set_ctx(auth_ctx)

                try:
                    _process_queue(queue)
                finally:
                    context.set_ctx(old_auth_ctx)

            t = threading.Thread(target=_within_new_thread)
            t.start()
        finally:
            _clear()

        return res

    return decorate


@db_utils.retry_on_db_error
@run
def _process_queue(queue):
    """Run the functions from the queue

    Note that this function is also decorated with @run because we may
    register new operations (i.e. calling again register_operation()) from
    one of the function currently being processed.
    """
    for func, args, in_tx in queue:
        if in_tx:
            with db_api.transaction():
                try:
                    func(*args)
                except Exception:
                    LOG.exception(
                        "Failed to run transactional engine operation.")

                    raise
        else:
            try:
                func(*args)
            except Exception:
                LOG.exception(
                    "Failed to run non-transactional engine operation.")
