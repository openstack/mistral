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

from mistral import expressions as expr


def get_for_each_output(task_db, task_spec, raw_result):
    t_name = task_db.name

    # Calc output for for-each (only list form is used).
    out_key = (task_spec.get_publish().keys()[0]
               if task_spec.get_publish() else None)

    # TODO(nmakhotkin): Simplify calculating task output.
    e_data = raw_result.error
    output = expr.evaluate_recursively(
        task_spec.get_publish(),
        raw_result.data or {}
    )

    if not task_db.output:
        task_db.output = {}

    task_output = copy.copy(task_db.output)

    if out_key:
        if out_key in task_output:
            task_output[out_key].append(
                output.get(out_key) or e_data
            )
        else:
            task_output[out_key] = [output.get(out_key) or e_data]

        # Add same result to task output under key 'task'.
        task_output['task'] = {
            t_name: task_output[out_key]
        }
    else:
        if 'task' not in task_output:
            task_output.update({'task': {t_name: [output or e_data]}})
        else:
            task_output['task'][t_name].append(output or e_data)

    return task_output


def calc_for_each_input(action_input):
    # In case of for-each iterate over action_input and send
    # each part of data to executor.
    # Calculate action input collection for separating input.
    action_input_collection = []

    for key, value in action_input.items():
        for index, item in enumerate(value):
            iter_context = {key: item}

            if index >= len(action_input_collection):
                action_input_collection.append(iter_context)
            else:
                action_input_collection[index].update(iter_context)

    return action_input_collection