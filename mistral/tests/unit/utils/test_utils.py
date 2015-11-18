# Copyright 2013 - Mirantis, Inc.
# Copyright 2015 - StackStorm, Inc.
# Copyright 2015 - Huawei Technologies Co. Ltd
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

from mistral import exceptions as exc
from mistral.tests.unit import base
from mistral import utils
from mistral.utils import ssh_utils

LEFT = {
    'key1': {
        'key11': "val11"
    },
    'key2': 'val2'
}

RIGHT = {
    'key1': {
        'key11': "val111111",
        'key12': "val12",
        'key13': {
            'key131': 'val131'
        }
    },
    'key2': 'val2222',
    'key3': 'val3'
}


class UtilsTest(base.BaseTest):
    def setUp(self):
        super(UtilsTest, self).setUp()

    def test_merge_dicts(self):
        left = copy.deepcopy(LEFT)
        right = copy.deepcopy(RIGHT)

        expected = {
            'key1': {
                'key11': "val111111",
                'key12': "val12",
                'key13': {
                    'key131': 'val131'
                }
            },
            'key2': 'val2222',
            'key3': 'val3'
        }

        utils.merge_dicts(left, right)

        self.assertDictEqual(left, expected)

    def test_merge_dicts_overwrite_false(self):
        left = copy.deepcopy(LEFT)
        right = copy.deepcopy(RIGHT)

        expected = {
            'key1': {
                'key11': "val11",
                'key12': "val12",
                'key13': {
                    'key131': 'val131'
                }
            },
            'key2': 'val2',
            'key3': 'val3'
        }

        utils.merge_dicts(left, right, overwrite=False)

        self.assertDictEqual(left, expected)

    def test_itersubclasses(self):
        class A(object):
            pass

        class B(A):
            pass

        class C(A):
            pass

        class D(C):
            pass

        self.assertEqual([B, C, D], list(utils.iter_subclasses(A)))

    def test_get_input_dict(self):
        input = ['param1', {'param2': 2}]
        input_dict = utils.get_input_dict(input)

        self.assertIn('param1', input_dict)
        self.assertIn('param2', input_dict)
        self.assertEqual(2, input_dict.get('param2'))
        self.assertIs(input_dict.get('param1'), utils.NotDefined)

    def test_get_input_dict_from_input_string(self):
        input_string = 'param1, param2=2, param3="var3"'
        input_dict = utils.get_dict_from_string(input_string)

        self.assertIn('param1', input_dict)
        self.assertIn('param2', input_dict)
        self.assertIn('param3', input_dict)
        self.assertEqual(2, input_dict.get('param2'))
        self.assertEqual('var3', input_dict.get('param3'))
        self.assertIs(input_dict.get('param1'), utils.NotDefined)

    def test_paramiko_to_private_key(self):
        self.assertRaises(
            exc.DataAccessException,
            ssh_utils._to_paramiko_private_key,
            "../dir"
        )
        self.assertRaises(
            exc.DataAccessException,
            ssh_utils._to_paramiko_private_key,
            "..\\dir"
        )
