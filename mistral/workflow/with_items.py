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

from mistral import exceptions as exc
from mistral.workflow import states


def _get_context(task_ex):
    return task_ex.runtime_context['with_items']


def get_count(task_ex):
    return _get_context(task_ex)['count']


def get_index(task_ex):
    return _get_context(task_ex)['index']


def get_concurrency_spec(task_spec):
    policies = task_spec.get_policies()

    return policies.get_concurrency() if policies else None


def get_indexes_for_loop(task_ex, task_spec):
    concurrency_spec = get_concurrency_spec(task_spec)
    concurrency = task_ex.runtime_context['concurrency']
    index = get_index(task_ex)

    number_to_execute = (get_count(task_ex) - index
                         if not concurrency_spec else concurrency)

    return index, index + number_to_execute


def do_step(task_ex):
    with_items_context = _get_context(task_ex)

    if with_items_context['capacity'] > 0:
        with_items_context['capacity'] -= 1

    with_items_context['index'] += 1

    task_ex.runtime_context.update({'with_items': with_items_context})


def prepare_runtime_context(task_ex, task_spec, input_dicts):
    runtime_context = task_ex.runtime_context
    with_items_spec = task_spec.get_with_items()

    if with_items_spec:
        # Prepare current indexes and parallel limitation.
        runtime_context['with_items'] = {
            'capacity': get_concurrency_spec(task_spec),
            'index': 0,
            'count': len(input_dicts)
        }


def validate_input(with_items_input):
    # Take only mapped values and check them.
    values = with_items_input.values()

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


def iterations_completed(task_ex):
    completed = all([states.is_completed(ex.state)
                    for ex in task_ex.executions])
    return completed
