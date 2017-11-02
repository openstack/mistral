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

import inspect
import re

from oslo_db import exception as db_exc
from oslo_log import log as logging
import six
from yaql.language import exceptions as yaql_exc
from yaql.language import factory

from mistral import exceptions as exc
from mistral.expressions.base_expression import Evaluator
from mistral.utils import expression_utils

LOG = logging.getLogger(__name__)
YAQL_ENGINE = factory.YaqlFactory().create()

INLINE_YAQL_REGEXP = '<%.*?%>'


class YAQLEvaluator(Evaluator):
    @classmethod
    def validate(cls, expression):
        try:
            YAQL_ENGINE(expression)
        except (yaql_exc.YaqlException, KeyError, ValueError, TypeError) as e:
            raise exc.YaqlGrammarException(getattr(e, 'message', e))

    @classmethod
    def evaluate(cls, expression, data_context):
        expression = expression.strip() if expression else expression

        try:
            result = YAQL_ENGINE(expression).evaluate(
                context=expression_utils.get_yaql_context(data_context)
            )
        except Exception as e:
            # NOTE(rakhmerov): if we hit a database error then we need to
            # re-raise the initial exception so that upper layers had a
            # chance to handle it properly (e.g. in case of DB deadlock
            # the operations needs to retry. Essentially, such situation
            # indicates a problem with DB rather than with the expression
            # syntax or values.
            if isinstance(e, db_exc.DBError):
                LOG.error(
                    "Failed to evaluate YAQL expression due to a database"
                    " error, re-raising initial exception [expression=%s,"
                    " error=%s, data=%s]",
                    expression,
                    str(e),
                    data_context
                )

                raise e

            raise exc.YaqlEvaluationException(
                "Can not evaluate YAQL expression [expression=%s, error=%s"
                ", data=%s]" % (expression, str(e), data_context)
            )

        return result if not inspect.isgenerator(result) else list(result)

    @classmethod
    def is_expression(cls, s):
        # The class should not be used outside of InlineYAQLEvaluator since by
        # convention, YAQL expression should always be wrapped in '<% %>'.
        return False


class InlineYAQLEvaluator(YAQLEvaluator):
    # This regular expression will look for multiple occurrences of YAQL
    # expressions in '<% %>' (i.e. <% any_symbols %>) within a string.
    find_expression_pattern = re.compile(INLINE_YAQL_REGEXP)

    @classmethod
    def validate(cls, expression):
        if not isinstance(expression, six.string_types):
            raise exc.YaqlEvaluationException(
                "Unsupported type '%s'." % type(expression)
            )

        found_expressions = cls.find_inline_expressions(expression)

        if found_expressions:
            [super(InlineYAQLEvaluator, cls).validate(expr.strip("<%>"))
             for expr in found_expressions]

    @classmethod
    def evaluate(cls, expression, data_context):
        LOG.debug(
            "Start to evaluate YAQL expression. "
            "[expression='%s', context=%s]",
            expression,
            data_context
        )

        result = expression
        found_expressions = cls.find_inline_expressions(expression)

        if found_expressions:
            for expr in found_expressions:
                trim_expr = expr.strip("<%>")
                evaluated = super(InlineYAQLEvaluator,
                                  cls).evaluate(trim_expr, data_context)
                if len(expression) == len(expr):
                    result = evaluated
                else:
                    result = result.replace(expr, str(evaluated))

        LOG.debug(
            "Finished evaluation. [expression='%s', result: %s]",
            expression,
            result
        )

        return result

    @classmethod
    def is_expression(cls, s):
        return cls.find_expression_pattern.search(s)

    @classmethod
    def find_inline_expressions(cls, s):
        return cls.find_expression_pattern.findall(s)
