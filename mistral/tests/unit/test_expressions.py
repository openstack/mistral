# -*- coding: utf-8 -*-
#
# Copyright 2013 - Mirantis, Inc.
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

import unittest2

from mistral import expressions as expr


DATA = {
    "server": {
        "id": "03ea824a-aa24-4105-9131-66c48ae54acf",
        "name": "cloud-fedora",
        "status": "ACTIVE"
    },
    "status": "OK"
}

SERVERS = {
    "servers": [
        {
            'name': 'centos'
        },
        {
            'name': 'ubuntu'
        },
        {
            'name': 'fedora'
        }
    ]
}


class YaqlEvaluatorTest(unittest2.TestCase):
    def setUp(self):
        super(YaqlEvaluatorTest, self).setUp()
        self._evaluator = expr.YAQLEvaluator()

    def test_expression_result(self):
        res = self._evaluator.evaluate('$.server', DATA)
        self.assertEqual(res, {
            'id': "03ea824a-aa24-4105-9131-66c48ae54acf",
            'name': 'cloud-fedora',
            'status': 'ACTIVE'
        })

        res = self._evaluator.evaluate('$.server.id', DATA)
        self.assertEqual(res, '03ea824a-aa24-4105-9131-66c48ae54acf')

        res = self._evaluator.evaluate("$.server.status = 'ACTIVE'", DATA)
        self.assertTrue(res)

    def test_wrong_expression(self):
        res = self._evaluator.evaluate("$.status = 'Invalid value'", DATA)
        self.assertFalse(res)

        res = self._evaluator.evaluate('$.wrong_key', DATA)
        self.assertIsNone(res)

        expression_str = 'invalid_expression_string'
        res = self._evaluator.evaluate(expression_str, DATA)
        self.assertEqual(res, expression_str)

    def test_select_result(self):
        res = self._evaluator.evaluate('$.servers[$.name = ubuntu]', SERVERS)
        item = list(res)[0]
        self.assertEqual(item, {'name': 'ubuntu'})

    def test_evaluate_recursively(self):
        task_spec_dict = {
            'parameters': {
                'p1': 'My string',
                'p2': '$.param2',
                'p3': ''
            },
            'publish': {
                'new_key11': 'new_key1'
            }
        }
        modified_task = expr.evaluate_recursively(task_spec_dict,
                                                  {
                                                      'param2': 'val32'
                                                  })

        self.assertDictEqual(
            {
                'parameters': {
                    'p1': 'My string',
                    'p2': 'val32',
                    'p3': ''
                },
                'publish': {
                    'new_key11': 'new_key1'
                }
            },
            modified_task)

    def test_evaluate_recursively_arbitrary_dict(self):
        context = {
            "auth_token": "123",
            "project_id": "mistral"
        }
        data = {
            "parameters": {
                "parameter1": {
                    "name1": "$.auth_token",
                    "name2": "val_name2"
                },
                "param2": [
                    "var1",
                    "var2",
                    "/servers/{$.project_id}/bla"
                ]
            },
            "token": "$.auth_token"
        }

        applied = expr.evaluate_recursively(data, context)

        self.assertDictEqual(
            {
                "parameters": {
                    "parameter1": {
                        "name1": "123",
                        "name2": "val_name2"
                    },
                    "param2": ["var1", "var2", "/servers/mistral/bla"]
                },
                "token": "123"
            },
            applied)
