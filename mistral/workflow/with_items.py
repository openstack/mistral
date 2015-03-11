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

import copy

from mistral import exceptions as exc
from mistral import expressions as expr


# TODO(rakhmerov): The module should probably go into task_handler.
def get_result(task_ex, task_spec, result):
    """Returns result from task markered as with-items

     Examples of result:
       1. Without publish clause:
          {
            "task": {
              "task1": [None]
            }
          }
       Note: In this case we don't create any specific
       result to prevent generating large data in DB.

       Note: None here used for calculating number of
       finished iterations.

       2. With publish clause and specific result key:
          {
            "result": [
              "result1",
              "result2"
            ],
            "task": {
              "task1": {
                "result": [
                  "result1",
                  "result2"
                ]
              }
            }
          }
    """
    e_data = result.error

    expr_ctx = copy.deepcopy(task_ex.in_context) or {}

    expr_ctx[task_ex.name] = copy.deepcopy(result.data) or {}

    # Calc result for with-items (only list form is used).
    result = expr.evaluate_recursively(task_spec.get_publish(), expr_ctx)

    if not task_ex.result:
        task_ex.result = {}

    task_result = copy.copy(task_ex.result)

    res_key = _get_result_key(task_spec)

    if res_key:
        if res_key in task_result:
            task_result[res_key].append(
                result.get(res_key) or e_data
            )
        else:
            task_result[res_key] = [result.get(res_key) or e_data]

        # Add same result to task result under key 'task'.
        # TODO(rakhmerov): Fix this during task result refactoring.
        # task_result[t_name] =
        #     {
        #         res_key: task_result[res_key]
        #     }
    # else:
    #     if 'task' not in task_result:
    #         task_result.update({'task': {t_name: [None or e_data]}})
    #     else:
    #         task_result['task'][t_name].append(None or e_data)

    return task_result


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


def prepare_runtime_context(task_ex, task_spec):
    runtime_context = task_ex.runtime_context
    with_items_spec = task_spec.get_with_items()

    if with_items_spec:
        # Prepare current indexes and parallel limitation.
        runtime_context['with_items'] = {
            'capacity': get_concurrency_spec(task_spec),
            'index': 0,
            'count': len(task_ex.input[with_items_spec.keys()[0]])
        }


def calc_input(with_items_input):
    """Calculate action input collection for separating each action input.

    Example:
      DSL:
        with_items:
          - itemX in <% $.arrayI %>
          - itemY in <% $.arrayJ %>

      Assume arrayI = [1, 2], arrayJ = ['a', 'b'].
      with_items_input = {
        "itemX": [1, 2],
        "itemY": ['a', 'b']
      }

      Then we get separated input:
      action_input_collection = [
        {'itemX': 1, 'itemY': 'a'},
        {'itemX': 2, 'itemY': 'b'}
      ]

    :param with_items_input: Dict containing mapped variables to their arrays.
    :return: list containing dicts of each action input.
    """
    validate_input(with_items_input)

    action_input_collection = []

    for key, value in with_items_input.items():
        for index, item in enumerate(value):
            iter_context = {key: item}

            if index >= len(action_input_collection):
                action_input_collection.append(iter_context)
            else:
                action_input_collection[index].update(iter_context)

    return action_input_collection


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


def _get_result_key(task_spec):
    return (task_spec.get_publish().keys()[0]
            if task_spec.get_publish() else None)


def is_iterations_incomplete(task_ex):
    return get_index(task_ex) < get_count(task_ex)
