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
from mistral import exceptions as exc
from mistral.tests import base
from mistral.workbook.v2 import tasks
from mistral.workflow import utils
from mistral.workflow import with_items


TASK_DICT = {
    'name': 'task1',
    'version': '2.0',
    'action': 'std.echo',
    'with-items': [
        'item in $.array'
    ],
    'input': {
        'array': '$.my_array'
    }
}

TASK_SPEC = tasks.TaskSpec(TASK_DICT)

TASK_DB = models.Task(
    name='task1',
    output=None,
)


class WithItemsCalculationsTest(base.BaseTest):
    def test_calculate_output_with_key(self):
        task_dict = TASK_DICT.copy()
        task_dict['publish'] = {'result': '$.task1'}

        task_spec = tasks.TaskSpec(task_dict)
        raw_result = utils.TaskResult(data='output!')

        output = with_items.get_output(TASK_DB, task_spec, raw_result)

        self.assertDictEqual({'result': ['output!']}, output)

    def test_calculate_output_without_key(self):
        raw_result = utils.TaskResult(data='output!')
        output = with_items.get_output(TASK_DB, TASK_SPEC, raw_result)

        # TODO(rakhmerov): Fix during result/output refactoring.
        self.assertDictEqual({}, output)

    def test_calculate_input(self):
        with_items_input = {
            'name_info': [
                {'name': 'John'},
                {'name': 'Ivan'},
                {'name': 'Mistral'}
            ]
        }
        action_input_collection = with_items.calc_input(with_items_input)

        self.assertListEqual(
            [
                {'name_info': {'name': 'John'}},
                {'name_info': {'name': 'Ivan'}},
                {'name_info': {'name': 'Mistral'}}
            ],
            action_input_collection
        )

    def test_calculate_input_multiple_array(self):
        with_items_input = {
            'name_info': [
                {'name': 'John'},
                {'name': 'Ivan'},
                {'name': 'Mistral'}
            ],
            'server_info': [
                'server1',
                'server2',
                'server3'
            ]
        }

        action_input_collection = with_items.calc_input(with_items_input)

        self.assertListEqual(
            [
                {'name_info': {'name': 'John'}, 'server_info': 'server1'},
                {'name_info': {'name': 'Ivan'}, 'server_info': 'server2'},
                {'name_info': {'name': 'Mistral'}, 'server_info': 'server3'},
            ],
            action_input_collection
        )

    def test_calculate_input_wrong_array_length(self):
        with_items_input = {
            'name_info': [
                {'name': 'John'},
                {'name': 'Ivan'},
                {'name': 'Mistral'}
            ],
            'server_info': [
                'server1',
                'server2'
            ]
        }
        exception = self.assertRaises(
            exc.InputException,
            with_items.calc_input,
            with_items_input
        )

        self.assertIn('the same length', exception.message)

    def test_calculate_input_not_list(self):
        with_items_input = {
            'name_info': [
                {'name': 'John'},
                {'name': 'Ivan'},
                {'name': 'Mistral'}
            ],
            'server_info': 'some_string'
        }
        exception = self.assertRaises(
            exc.InputException,
            with_items.calc_input,
            with_items_input
        )

        self.assertIn('List type', exception.message)
