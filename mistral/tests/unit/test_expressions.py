# Copyright 2013 - Mirantis, Inc.
# Copyright 2015 - StackStorm, Inc.
# Copyright 2016 - Brocade Communications Systems, Inc.
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
                    'conn': 'mysql://admin:secret@<% env().host %>'
                            '/<% env().db %>'
                }
            }
        }

        context = {
            '__env': environment
        }

        defaults = context['__env']['__actions']['std.sql']
        applied = expr.evaluate_recursively(defaults, context)
        expected = 'mysql://admin:secret@vm1234.example.com/test'

        self.assertEqual(expected, applied['conn'])

    def test_validate_jinja_with_yaql_context(self):
        self.assertRaises(exc.JinjaGrammarException,
                          expr.validate,
                          '{{ $ }}')

    def test_validate_mixing_jinja_and_yaql(self):
        self.assertRaises(exc.ExpressionGrammarException,
                          expr.validate,
                          '<% $.a %>{{ _.a }}')

        self.assertRaises(exc.ExpressionGrammarException,
                          expr.validate,
                          '{{ _.a }}<% $.a %>')

    def test_evaluate_mixing_jinja_and_yaql(self):
        actual = expr.evaluate('<% $.a %>{{ _.a }}', {'a': 'b'})

        self.assertEqual('<% $.a %>b', actual)

        actual = expr.evaluate('{{ _.a }}<% $.a %>', {'a': 'b'})

        self.assertEqual('b<% $.a %>', actual)
