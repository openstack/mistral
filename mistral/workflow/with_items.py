# Copyright 2014 - Mirantis, Inc.
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

import copy
import six

from mistral import exceptions as exc
from mistral.workflow import states


# TODO(rakhmerov): Seems like it makes sense to get rid of this module in favor
# of implementing all the needed logic in engine.tasks.WithItemsTask directly.

_CAPACITY = 'capacity'
_CONCURRENCY = 'concurrency'
_COUNT = 'count'
_WITH_ITEMS = 'with_items_context'

_DEFAULT_WITH_ITEMS = {
    _COUNT: 0,
    _CONCURRENCY: 0,
    _CAPACITY: 0
}


def _get_context(task_ex):
    return task_ex.runtime_context.get(_WITH_ITEMS, _DEFAULT_WITH_ITEMS)


def get_count(task_ex):
    return _get_context(task_ex)[_COUNT]


def get_capacity(task_ex):
    return _get_context(task_ex)[_CAPACITY]


def get_concurrency(task_ex):
    return task_ex.runtime_context.get(_CONCURRENCY)


def is_completed(task_ex):
    find_cancelled = lambda x: x.accepted and x.state == states.CANCELLED

    if list(filter(find_cancelled, task_ex.executions)):
        return True

    execs = list(filter(lambda t: t.accepted, task_ex.executions))
    count = get_count(task_ex) or 1

    return count == len(execs)


def get_index(task_ex):
    f = lambda x: (
        x.accepted or
        states.is_running(x.state) or
        states.is_idle(x.state)
    )

    return len(list(filter(f, task_ex.executions)))


def get_final_state(task_ex):
    find_error = lambda x: x.accepted and x.state == states.ERROR
    find_cancelled = lambda x: x.accepted and x.state == states.CANCELLED

    if list(filter(find_cancelled, task_ex.executions)):
        return states.CANCELLED
    elif list(filter(find_error, task_ex.executions)):
        return states.ERROR
    else:
        return states.SUCCESS


def _get_with_item_indices(exs):
    """Returns a list of indices in case of re-running with-items.

    :param exs: List of executions.
    :return: a list of numbers.
    """
    return sorted(set([ex.runtime_context['index'] for ex in exs]))


def _get_accepted_executions(task_ex):
    # Choose only if not accepted but completed.
    return list(
        filter(
            lambda x: x.accepted and states.is_completed(x.state),
            task_ex.executions
        )
    )


def _get_unaccepted_executions(task_ex):
    # Choose only if not accepted but completed.
    return list(
        filter(
            lambda x: not x.accepted and states.is_completed(x.state),
            task_ex.executions
        )
    )


def get_next_indices(task_ex):
    capacity = get_capacity(task_ex)
    count = get_count(task_ex)

    accepted = _get_with_item_indices(_get_accepted_executions(task_ex))
    unaccepted = _get_with_item_indices(_get_unaccepted_executions(task_ex))
    candidates = sorted(list(set(unaccepted) - set(accepted)))

    if candidates:
        indices = copy.copy(candidates)

        if max(candidates) < count - 1:
            indices += list(six.moves.range(max(candidates) + 1, count))
    else:
        index = get_index(task_ex)
        indices = list(six.moves.range(index, count))

    return indices[:capacity]


def increase_capacity(task_ex):
    ctx = _get_context(task_ex)
    concurrency = get_concurrency(task_ex)

    if concurrency and ctx[_CAPACITY] < concurrency:
        ctx[_CAPACITY] += 1

        task_ex.runtime_context.update({_WITH_ITEMS: ctx})


def decrease_capacity(task_ex, count):
    ctx = _get_context(task_ex)

    capacity = ctx[_CAPACITY]

    if capacity is not None:
        if capacity >= count:
            ctx[_CAPACITY] -= count
        else:
            raise RuntimeError(
                "Can't decrease with-items capacity [capacity=%s, count=%s]"
                % (capacity, count)
            )

    task_ex.runtime_context.update({_WITH_ITEMS: ctx})


def is_new(task_ex):
    return not task_ex.runtime_context.get(_WITH_ITEMS)


def prepare_runtime_context(task_ex, task_spec, action_count):
    runtime_ctx = task_ex.runtime_context
    with_items_spec = task_spec.get_with_items()

    if with_items_spec and not runtime_ctx.get(_WITH_ITEMS):
        # Prepare current indexes and parallel limitation.
        runtime_ctx[_WITH_ITEMS] = {
            _CAPACITY: get_concurrency(task_ex),
            _COUNT: action_count
        }


def validate_values(with_items_values):
    # Take only mapped values and check them.
    values = list(with_items_values.values())

    if not all([isinstance(v, list) for v in values]):
        raise exc.InputException(
            "Wrong input format for: %s. List type is"
            " expected for each value." % with_items_values
        )

    required_len = len(values[0])

    if not all(len(v) == required_len for v in values):
        raise exc.InputException(
            "Wrong input format for: %s. All arrays must"
            " have the same length." % with_items_values
        )


def has_more_iterations(task_ex):
    # See action executions which have been already
    # accepted or are still running.
    action_exs = list(filter(
        lambda x: x.accepted or x.state == states.RUNNING,
        task_ex.executions
    ))

    return get_count(task_ex) > len(action_exs)
