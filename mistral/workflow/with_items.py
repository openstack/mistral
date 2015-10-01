# Copyright 2014 - Mirantis, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
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

import six

from mistral.db.v2 import api as db_api
from mistral import exceptions as exc
from mistral.workflow import states


_CAPACITY = 'capacity'
_CONCURRENCY = 'concurrency'
_COUNT = 'count'
_WITH_ITEMS = 'with_items_context'


def _get_context(task_ex):
    return task_ex.runtime_context[_WITH_ITEMS]


def get_count(task_ex):
    return _get_context(task_ex)[_COUNT]


def is_completed(task_ex):
    action_exs = db_api.get_action_executions(
        task_execution_id=task_ex.id,
        accepted=True
    )
    count = get_count(task_ex) or 1

    return count == len(action_exs)


def get_index(task_ex):
    return len(
        filter(
            lambda x: x.accepted or states.RUNNING, task_ex.executions
        )
    )


def get_concurrency(task_ex):
    return task_ex.runtime_context.get(_CONCURRENCY)


def get_final_state(task_ex):
    find_error = lambda x: x.accepted and x.state == states.ERROR

    if filter(find_error, task_ex.executions):
        return states.ERROR
    else:
        return states.SUCCESS


def _get_indices_if_rerun(unaccepted_executions):
    """Returns a list of indices in case of re-running with-items.

    :param unaccepted_executions: List of executions.
    :return: a list of numbers.
    """

    return sorted(
        set([
            ex.runtime_context['with_items_index']
            for ex in unaccepted_executions
        ])
    )


def _get_unaccepted_act_exs(task_ex):
    # Choose only if not accepted but completed.
    return filter(
        lambda x: not x.accepted and states.is_completed(x.state),
        task_ex.executions
    )


def get_indices_for_loop(task_ex):
    capacity = _get_context(task_ex)[_CAPACITY]
    count = get_count(task_ex)

    unaccepted = _get_unaccepted_act_exs(task_ex)

    if unaccepted:
        indices = _get_indices_if_rerun(unaccepted)

        if max(indices) < count - 1:
            indices += list(six.moves.range(max(indices) + 1, count))

        return indices[:capacity] if capacity else indices

    index = get_index(task_ex)

    number_to_execute = capacity if capacity else count - index

    return list(six.moves.range(index, index + number_to_execute))


def decrease_capacity(task_ex, count):
    with_items_context = _get_context(task_ex)

    if with_items_context[_CAPACITY] >= count:
        with_items_context[_CAPACITY] -= count
    elif with_items_context[_CAPACITY]:
        raise exc.WorkflowException(
            "Impossible to apply current with-items concurrency."
        )

    task_ex.runtime_context.update({_WITH_ITEMS: with_items_context})


def increase_capacity(task_ex):
    with_items_context = _get_context(task_ex)
    max_concurrency = get_concurrency(task_ex)

    if max_concurrency and with_items_context[_CAPACITY] < max_concurrency:
        with_items_context[_CAPACITY] += 1
        task_ex.runtime_context.update({_WITH_ITEMS: with_items_context})


def prepare_runtime_context(task_ex, task_spec, input_dicts):
    runtime_context = task_ex.runtime_context
    with_items_spec = task_spec.get_with_items()

    if with_items_spec and not runtime_context.get(_WITH_ITEMS):
        # Prepare current indexes and parallel limitation.
        runtime_context[_WITH_ITEMS] = {
            _CAPACITY: get_concurrency(task_ex),
            _COUNT: len(input_dicts)
        }


def validate_input(with_items_input):
    # Take only mapped values and check them.
    values = list(with_items_input.values())

    if not all([isinstance(v, list) for v in values]):
        raise exc.InputException(
            "Wrong input format for: %s. List type is"
            " expected for each value." % with_items_input
        )

    required_len = len(values[0])

    if not all(len(v) == required_len for v in values):
        raise exc.InputException(
            "Wrong input format for: %s. All arrays must"
            " have the same length." % with_items_input
        )


def has_more_iterations(task_ex):
    # See action executions which have been already
    # accepted or are still running.
    action_exs = filter(
        lambda x: x.accepted or x.state == states.RUNNING,
        task_ex.executions
    )

    return get_count(task_ex) > len(action_exs)
