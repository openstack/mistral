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

import functools

from oslo_config import cfg

from mistral.executors import base as exe
from mistral import utils


_THREAD_LOCAL_NAME = "__action_queue_thread_local"


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


def _run_actions():
    executor = exe.get_executor(cfg.CONF.executor.type)

    for action_ex, action_def, target in _get_queue():
        executor.run_action(
            action_ex.id,
            action_def.action_class,
            action_def.attributes or {},
            action_ex.input,
            action_ex.runtime_context.get('safe_rerun', False),
            target=target
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

            _run_actions()
        finally:
            _clear()

        return res

    return decorate


def schedule(action_ex, action_def, target):
    _get_queue().append((action_ex, action_def, target))
