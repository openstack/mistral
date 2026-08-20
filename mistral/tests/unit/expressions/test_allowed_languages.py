# Copyright 2026 - OVHcloud.
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
from mistral import expressions
from mistral.tests.unit import base


class AllowedExpressionLanguagesTest(base.BaseTest):
    def test_jinja_allowed_by_default(self):
        # The default configuration keeps both languages enabled.
        self.assertEqual(3, expressions.evaluate('{{ 1 + 2 }}', {}))

        # Validation of a Jinja expression passes.
        expressions.validate('{{ 1 + 2 }}')

    def test_jinja_evaluation_rejected_when_disabled(self):
        self.override_config(
            'allowed_languages', ['yaql'], group='expressions'
        )

        self.assertRaises(
            exc.EvaluationException,
            expressions.evaluate,
            '{{ 1 + 2 }}',
            {}
        )

    def test_jinja_validation_rejected_when_disabled(self):
        self.override_config(
            'allowed_languages', ['yaql'], group='expressions'
        )

        self.assertRaises(
            exc.ExpressionGrammarException,
            expressions.validate,
            '{{ 1 + 2 }}'
        )

    def test_yaql_still_works_when_jinja_disabled(self):
        self.override_config(
            'allowed_languages', ['yaql'], group='expressions'
        )

        self.assertEqual(3, expressions.evaluate('<% 1 + 2 %>', {}))
        expressions.validate('<% 1 + 2 %>')
