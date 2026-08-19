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

from mistral import expressions
from mistral.expressions import jinja_expression
from mistral.expressions import yaql_expression
from mistral.tests.unit import base

SECRET = 'SUPER_SECRET_AUTH_TOKEN'


class ExpressionErrorNoContextLeakTest(base.BaseTest):
    """A failing expression must not leak the evaluation context.

    The evaluation context can hold sensitive data (auth token, service
    catalog, ...), so it must never end up in the raised exception - it
    would otherwise be persisted in the task state_info and written to
    the logs.
    """

    def _ctx(self):
        return {'auth_token': SECRET, 'x': 1}

    def _assert_no_leak(self, evaluator, expression):
        try:
            evaluator.evaluate(expression, self._ctx())
        except Exception as e:
            self.assertNotIn(SECRET, str(e))
            # The expression itself stays in the message (it is useful and
            # not sensitive).
            self.assertIn(expression.strip('{}<%> '), str(e))
        else:
            self.fail("Expression %s was expected to fail" % expression)

    def test_jinja_inline_error_does_not_leak_context(self):
        # A block template that raises at render time goes through the
        # generic wrapping path.
        self._assert_no_leak(
            jinja_expression.InlineJinjaEvaluator,
            '{{ 1 / 0 }}'
        )

    def test_yaql_error_does_not_leak_context(self):
        self._assert_no_leak(
            yaql_expression.InlineYAQLEvaluator,
            '<% 1 / 0 %>'
        )

    def test_evaluate_recursively_error_does_not_leak_context(self):
        # Same, but through the public evaluate() entry point.
        try:
            expressions.evaluate('{{ 1 / 0 }}', self._ctx())
        except Exception as e:
            self.assertNotIn(SECRET, str(e))
        else:
            self.fail("Expression was expected to fail")
