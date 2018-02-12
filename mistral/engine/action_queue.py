# Copyright 2016 - Nokia Networks.
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

from oslo_config import cfg

from mistral import context
from mistral.executors import base as exe
from mistral.rpc import clients as rpc
from mistral import utils


_THREAD_LOCAL_NAME = "__action_queue_thread_local"

# Action queue operations.
_RUN_ACTION = "run_action"
_ON_ACTION_COMPLETE = "on_action_complete"


def _prepare():
    utils.set_thread_local(_THREAD_LOCAL_NAME, list())


def _clear():
    utils.set_thread_local(_THREAD_LOCAL_NAME, None)


def _get_queue():
    queue = utils.get_thread_local(_THREAD_LOCAL_NAME)

    if queue is None:
        raise RuntimeError(
            'Action queue is not initialized for the current thread.'
            ' Most likely some transactional method is not decorated'
            ' with action_queue.process()'
        )

    return queue


def _process_queue(queue):
    executor = exe.get_executor(cfg.CONF.executor.type)

    for operation, args in queue:
        if operation == _RUN_ACTION:
            action_ex, action_def, target, execution_context, timeout = args

            executor.run_action(
                action_ex.id,
                action_def.action_class,
                action_def.attributes or {},
                action_ex.input,
                action_ex.runtime_context.get('safe_rerun', False),
                execution_context,
                target=target,
                timeout=timeout
            )
        elif operation == _ON_ACTION_COMPLETE:
            action_ex_id, result, wf_action = args

            rpc.get_engine_client().on_action_complete(
                action_ex_id,
                result,
                wf_action
            )


def process(func):
    """Decorator that processes (runs) all actions in the action queue.

    Various engine methods may cause new actions to be scheduled. All
    such methods must be decorated with this decorator. It makes sure
    to run all the actions in the queue and clean up the queue.
    """
    @functools.wraps(func)
    def decorate(*args, **kw):
        _prepare()

        try:
            res = func(*args, **kw)

            queue = _get_queue()
            auth_ctx = context.ctx() if context.has_ctx() else None

            # NOTE(rakhmerov): Since we make RPC calls to the engine itself
            # we need to process the action queue asynchronously in a new
            # thread. Otherwise, if we have one engine process the engine
            # will may send a request to itself while already processing
            # another one. In conjunction with blocking RPC it will lead
            # to a deadlock (and RPC timeout).
            def _within_new_thread():
                old_auth_ctx = context.ctx() if context.has_ctx() else None

                context.set_ctx(auth_ctx)

                try:
                    _process_queue(queue)
                finally:
                    context.set_ctx(old_auth_ctx)

            eventlet.spawn(_within_new_thread)
        finally:
            _clear()

        return res

    return decorate


def schedule_run_action(action_ex, action_def, target, execution_context,
                        timeout):
    args = (action_ex, action_def, target, execution_context, timeout)
    _get_queue().append((_RUN_ACTION, args))


def schedule_on_action_complete(action_ex_id, result, wf_action=False):
    _get_queue().append(
        (_ON_ACTION_COMPLETE, (action_ex_id, result, wf_action))
    )
