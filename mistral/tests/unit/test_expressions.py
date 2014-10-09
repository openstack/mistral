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

from mistral import expressions as expr
from mistral.tests import base

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
        {'name': 'centos'},
        {'name': 'ubuntu'},
        {'name': 'fedora'}
    ]
}


class YaqlEvaluatorTest(base.BaseTest):
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

    def test_function_length(self):
        # Lists.
        self.assertEqual(3, expr.evaluate('$.length()', [1, 2, 3]))
        self.assertEqual(2, expr.evaluate('$.length()', ['one', 'two']))
        self.assertEqual(4, expr.evaluate(
            '$.array.length()',
            {'array': ['1', '2', '3', '4']})
        )

        # Strings.
        self.assertEqual(3, expr.evaluate('$.length()', '123'))
        self.assertEqual(2, expr.evaluate('$.length()', '12'))
        self.assertEqual(
            4,
            expr.evaluate('$.string.length()', {'string': '1234'})
        )

        # Generators.
        self.assertEqual(
            2,
            expr.evaluate(
                "$[$.state = 'active'].length()",
                [
                    {'state': 'active'},
                    {'state': 'active'},
                    {'state': 'passive'}
                ]
            )
        )


class InlineYAQLEvaluatorTest(base.BaseTest):
    def setUp(self):
        super(InlineYAQLEvaluatorTest, self).setUp()

        self._evaluator = expr.InlineYAQLEvaluator()

    def test_multiple_placeholders(self):
        expr_str = """
            Statistics for tenant "{$.project_id}"

            Number of virtual machines: {$.vm_count}
            Number of active virtual machines: {$.active_vm_count}
            Number of networks: {$.net_count}

            -- Sincerely, Mistral Team.
        """

        result = self._evaluator.evaluate(
            expr_str,
            {
                'project_id': '1-2-3-4',
                'vm_count': 28,
                'active_vm_count': 0,
                'net_count': 1
            }
        )

        expected_result = """
            Statistics for tenant "1-2-3-4"

            Number of virtual machines: 28
            Number of active virtual machines: 0
            Number of networks: 1

            -- Sincerely, Mistral Team.
        """

        self.assertEqual(expected_result, result)


class ExpressionsTest(base.BaseTest):
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

        modified_task = expr.evaluate_recursively(
            task_spec_dict,
            {'param2': 'val32'}
        )

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
            modified_task
        )

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
            applied
        )
