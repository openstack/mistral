# Copyright 2013 - Mirantis, Inc.
# Copyright 2015 - StackStorm, Inc.
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

from mistral import exceptions as exc
from mistral import expressions as expr
from mistral.tests.unit import base

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
        self.assertEqual({
            'id': "03ea824a-aa24-4105-9131-66c48ae54acf",
            'name': 'cloud-fedora',
            'status': 'ACTIVE'
        }, res)

        res = self._evaluator.evaluate('$.server.id', DATA)
        self.assertEqual('03ea824a-aa24-4105-9131-66c48ae54acf', res)

        res = self._evaluator.evaluate("$.server.status = 'ACTIVE'", DATA)
        self.assertTrue(res)

    def test_wrong_expression(self):
        res = self._evaluator.evaluate("$.status = 'Invalid value'", DATA)
        self.assertFalse(res)

        self.assertRaises(
            exc.YaqlEvaluationException,
            self._evaluator.evaluate,
            '$.wrong_key',
            DATA
        )

        expression_str = 'invalid_expression_string'
        res = self._evaluator.evaluate(expression_str, DATA)
        self.assertEqual(expression_str, res)

    def test_select_result(self):
        res = self._evaluator.evaluate(
            '$.servers.where($.name = ubuntu)',
            SERVERS
        )
        item = list(res)[0]
        self.assertEqual({'name': 'ubuntu'}, item)

    def test_function_string(self):
        self.assertEqual('3', self._evaluator.evaluate('str($)', '3'))
        self.assertEqual('3', self._evaluator.evaluate('str($)', 3))

    def test_function_len(self):
        self.assertEqual(3, self._evaluator.evaluate('len($)', 'hey'))
        data = [{'some': 'thing'}]

        self.assertEqual(
            1,
            self._evaluator.evaluate('$.where($.some = thing).len()', data)
        )

    def test_validate(self):
        self._evaluator.validate('abc')
        self._evaluator.validate('1')
        self._evaluator.validate('1 + 2')
        self._evaluator.validate('$.a1')
        self._evaluator.validate('$.a1 * $.a2')

    def test_validate_failed(self):
        self.assertRaises(exc.YaqlGrammarException,
                          self._evaluator.validate,
                          '*')

        self.assertRaises(exc.YaqlGrammarException,
                          self._evaluator.validate,
                          [1, 2, 3])

        self.assertRaises(exc.YaqlGrammarException,
                          self._evaluator.validate,
                          {'a': 1})

    def test_json_pp(self):
        self.assertEqual('"3"', self._evaluator.evaluate('json_pp($)', '3'))
        self.assertEqual('3', self._evaluator.evaluate('json_pp($)', 3))
        self.assertEqual(
            '[\n    1,\n    2\n]',
            self._evaluator.evaluate('json_pp($)', [1, 2])
        )
        self.assertEqual(
            '{\n    "a": "b"\n}',
            self._evaluator.evaluate('json_pp($)', {'a': 'b'})
        )
        self.assertEqual(
            '"Mistral\nis\nawesome"',
            self._evaluator.evaluate(
                'json_pp($)', '\n'.join(['Mistral', 'is', 'awesome'])
            )
        )


class InlineYAQLEvaluatorTest(base.BaseTest):
    def setUp(self):
        super(InlineYAQLEvaluatorTest, self).setUp()

        self._evaluator = expr.InlineYAQLEvaluator()

    def test_multiple_placeholders(self):
        expr_str = """
            Statistics for tenant "<% $.project_id %>"

            Number of virtual machines: <% $.vm_count %>
            Number of active virtual machines: <% $.active_vm_count %>
            Number of networks: <% $.net_count %>

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

    def test_function_string(self):
        self.assertEqual('3', self._evaluator.evaluate('<% str($) %>', '3'))
        self.assertEqual('3', self._evaluator.evaluate('<% str($) %>', 3))

    def test_validate(self):
        self._evaluator.validate('There is no expression.')
        self._evaluator.validate('<% abc %>')
        self._evaluator.validate('<% 1 %>')
        self._evaluator.validate('<% 1 + 2 %>')
        self._evaluator.validate('<% $.a1 %>')
        self._evaluator.validate('<% $.a1 * $.a2 %>')
        self._evaluator.validate('<% $.a1 %> is <% $.a2 %>')
        self._evaluator.validate('The value is <% $.a1 %>.')

    def test_validate_failed(self):
        self.assertRaises(exc.YaqlGrammarException,
                          self._evaluator.validate,
                          'The value is <% * %>.')

        self.assertRaises(exc.YaqlEvaluationException,
                          self._evaluator.validate,
                          [1, 2, 3])

        self.assertRaises(exc.YaqlEvaluationException,
                          self._evaluator.validate,
                          {'a': 1})


class ExpressionsTest(base.BaseTest):
    def test_evaluate_complex_expressions(self):
        data = {
            'a': 1,
            'b': 2,
            'c': 3,
            'd': True,
            'e': False,
            'f': 10.1,
            'g': 10,
            'h': [1, 2, 3, 4, 5],
            'i': 'We are OpenStack!',
            'j': 'World',
            'k': 'Mistral',
            'l': 'awesome',
            'm': 'the way we roll'
        }

        test_cases = [
            ('<% $.a + $.b * $.c %>', 7),
            ('<%($.a + $.b) * $.c %>', 9),
            ('<% $.d and $.e %>', False),
            ('<% $.f > $.g %>', True),
            ('<% $.h.len() >= 5 %>', True),
            ('<% $.h.len() >= $.b + $.c %>', True),
            ('<% 100 in $.h %>', False),
            ('<% $.a in $.h%>', True),
            ('<% ''OpenStack'' in $.i %>', True),
            ('Hello, <% $.j %>!', 'Hello, World!'),
            ('<% $.k %> is <% $.l %>!', 'Mistral is awesome!'),
            ('This is <% $.m %>.', 'This is the way we roll.'),
            ('<% 1 + 1 = 3 %>', False)
        ]

        for expression, expected in test_cases:
            actual = expr.evaluate_recursively(expression, data)

            self.assertEqual(expected, actual)

    def test_evaluate_recursively(self):
        task_spec_dict = {
            'parameters': {
                'p1': 'My string',
                'p2': '<% $.param2 %>',
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
                    "name1": "<% $.auth_token %>",
                    "name2": "val_name2"
                },
                "param2": [
                    "var1",
                    "var2",
                    "/servers/<% $.project_id %>/bla"
                ]
            },
            "token": "<% $.auth_token %>"
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

    def test_evaluate_recursively_environment(self):
        environment = {
            'host': 'vm1234.example.com',
            'db': 'test',
            'timeout': 600,
            'verbose': True,
            '__actions': {
                'std.sql': {
                    'conn': 'mysql://admin:secrete@<% env().host %>'
                            '/<% env().db %>'
                }
            }
        }

        context = {
            '__env': environment
        }

        defaults = context['__env']['__actions']['std.sql']
        applied = expr.evaluate_recursively(defaults, context)
        expected = 'mysql://admin:secrete@vm1234.example.com/test'

        self.assertEqual(expected, applied['conn'])
