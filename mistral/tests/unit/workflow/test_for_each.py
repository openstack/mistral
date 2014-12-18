# -*- coding: utf-8 -*-
#
# Copyright 2014 - Mirantis, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

from mistral.db.v2.sqlalchemy import models
from mistral.tests import base
from mistral.workbook.v2 import tasks
from mistral.workflow import for_each
from mistral.workflow import utils


TASK_DICT = {
    "name": "task1",
    "version": "2.0",
    "action": "std.echo",
    "for-each": {
        "array_for_each": "$.array"
    },
    "input": {
        "array": "$.my_array"
    }
}
TASK_SPEC = tasks.TaskSpec(TASK_DICT)
TASK_DB = models.Task(
    name="task1",
    output=None,
)


class ForEachCalculationsTest(base.BaseTest):
    def test_calculate_output_with_key(self):
        task_dict = TASK_DICT.copy()
        task_dict['publish'] = {"result": "$"}

        task_spec = tasks.TaskSpec(task_dict)
        raw_result = utils.TaskResult(data="output!")

        output = for_each.get_for_each_output(TASK_DB, task_spec, raw_result)

        self.assertDictEqual(
            {
                'task': {
                    'task1': {
                        'result': ['output!']
                    }
                },
                'result': ['output!']
            }, output
        )

    def test_calculate_output_without_key(self):
        raw_result = utils.TaskResult(data="output!")
        output = for_each.get_for_each_output(TASK_DB, TASK_SPEC, raw_result)

        self.assertDictEqual(
            {
                'task': {
                    'task1': [None]
                }
            },
            output
        )

    def test_calculate_input(self):
        a_input = {
            'name_info': [
                {'name': 'John'},
                {'name': 'Ivan'},
                {'name': 'Mistral'}
            ]
        }
        action_input_collection = for_each.calc_for_each_input(a_input)

        self.assertListEqual(
            [
                {'name_info': {'name': 'John'}},
                {'name_info': {'name': 'Ivan'}},
                {'name_info': {'name': 'Mistral'}}
            ],
            action_input_collection
        )