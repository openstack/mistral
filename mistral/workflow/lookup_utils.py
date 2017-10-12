# Copyright 2015 - Mirantis, Inc.
# Copyright 2015 - StackStorm, Inc.
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

"""
The intention of the module is providing various DB related lookup functions
 for more convenient usage within the workflow engine.

Some of the functions may provide caching capabilities.

WARNING: Oftentimes, persistent objects returned by the methods in this
module won't be attached to the current DB SQLAlchemy session because
they are returned from the cache and therefore they need to be used
carefully without trying to do any lazy loading etc.
These objects are also not suitable for re-attaching them to a session
in order to update their persistent DB state.
Mostly, they are useful for doing any kind of fast lookups with in order
to make some decision based on their state.
"""

import cachetools
import threading

from mistral.db.v2 import api as db_api
from mistral.workflow import states


def _create_lru_cache_for_workflow_execution(wf_ex_id):
    return cachetools.LRUCache(maxsize=500)

# This is a two-level caching structure.
# First level: [<workflow execution id> -> <task execution cache>]
# Second level (task execution cache): [<task_name> -> <task executions>]
# The first level (by workflow execution id) allows to invalidate
# needed cache entry when the workflow gets completed.
_TASK_EX_CACHE = cachetools.LRUCache(
    maxsize=100,
    missing=_create_lru_cache_for_workflow_execution
)

_CACHE_LOCK = threading.RLock()


def find_task_executions_by_name(wf_ex_id, task_name):
    """Finds task executions by workflow execution id and task name.

    :param wf_ex_id: Workflow execution id.
    :param task_name: Task name.
    :return: Task executions (possibly a cached value).
    """
    with _CACHE_LOCK:
        t_execs = _TASK_EX_CACHE[wf_ex_id].get(task_name)

    if t_execs:
        return t_execs

    t_execs = db_api.get_task_executions(
        workflow_execution_id=wf_ex_id,
        name=task_name,
        sort_keys=[]  # disable sorting
    )

    # We can cache only finished tasks because they won't change.
    all_finished = (
        t_execs and
        all([states.is_completed(t_ex.state) for t_ex in t_execs])
    )

    if all_finished:
        with _CACHE_LOCK:
            _TASK_EX_CACHE[wf_ex_id][task_name] = t_execs

    return t_execs


def find_task_executions_by_spec(wf_ex_id, task_spec):
    return find_task_executions_by_name(wf_ex_id, task_spec.get_name())


def find_task_executions_by_specs(wf_ex_id, task_specs):
    res = []

    for t_s in task_specs:
        res = res + find_task_executions_by_spec(wf_ex_id, t_s)

    return res


def find_task_executions_with_state(wf_ex_id, state):
    return db_api.get_task_executions(
        workflow_execution_id=wf_ex_id,
        state=state
    )


def find_successful_task_executions(wf_ex_id):
    return find_task_executions_with_state(wf_ex_id, states.SUCCESS)


def find_error_task_executions(wf_ex_id):
    return find_task_executions_with_state(wf_ex_id, states.ERROR)


def find_cancelled_task_executions(wf_ex_id):
    return find_task_executions_with_state(wf_ex_id, states.CANCELLED)


def find_completed_task_executions(wf_ex_id):
    return db_api.get_completed_task_executions(workflow_execution_id=wf_ex_id)


def get_task_execution_cache_size():
    return len(_TASK_EX_CACHE)


def invalidate_cached_task_executions(wf_ex_id):
    with _CACHE_LOCK:
        if wf_ex_id in _TASK_EX_CACHE:
            del _TASK_EX_CACHE[wf_ex_id]


def clear_caches():
    with _CACHE_LOCK:
        _TASK_EX_CACHE.clear()
