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

import abc
import copy
import inspect
import re

from oslo_log import log as logging
import six
from yaql.language import exceptions as yaql_exc
from yaql.language import factory

from mistral import exceptions as exc
from mistral.utils import yaql_utils


LOG = logging.getLogger(__name__)
YAQL_ENGINE = factory.YaqlFactory().create()


class Evaluator(object):
    """Expression evaluator interface.

    Having this interface gives the flexibility to change the actual expression
    language used in Mistral DSL for conditions, output calculation etc.
    """

    @classmethod
    @abc.abstractmethod
    def validate(cls, expression):
        """Parse and validates the expression.

        :param expression: Expression string
        :return: True if expression is valid
        """
        pass

    @classmethod
    @abc.abstractmethod
    def evaluate(cls, expression, context):
        """Evaluates the expression against the given data context.

        :param expression: Expression string
        :param context: Data context
        :return: Expression result
        """
        pass

    @classmethod
    @abc.abstractmethod
    def is_expression(cls, expression):
        """Check expression string and decide whether it is expression or not.

        :param expression: Expression string
        :return: True if string is expression
        """
        pass


class YAQLEvaluator(Evaluator):
    @classmethod
    def validate(cls, expression):
        LOG.debug("Validating YAQL expression [expression='%s']", expression)

        try:
            YAQL_ENGINE(expression)
        except (yaql_exc.YaqlException, KeyError, ValueError, TypeError) as e:
            raise exc.YaqlGrammarException(getattr(e, 'message', e))

    @classmethod
    def evaluate(cls, expression, data_context):
        LOG.debug("Evaluating YAQL expression [expression='%s', context=%s]"
                  % (expression, data_context))

        try:
            result = YAQL_ENGINE(expression).evaluate(
                context=yaql_utils.get_yaql_context(data_context)
            )
        except (yaql_exc.YaqlException, KeyError, ValueError, TypeError) as e:
            raise exc.YaqlEvaluationException(
                "Can not evaluate YAQL expression: %s, data = %s; error:"
                " %s" % (expression, data_context, str(e))
            )

        LOG.debug("YAQL expression result: %s" % result)

        return result if not inspect.isgenerator(result) else list(result)

    @classmethod
    def is_expression(cls, s):
        # TODO(rakhmerov): It should be generalized since it may not be YAQL.
        # Treat any string as a YAQL expression.
        return isinstance(s, six.string_types)


INLINE_YAQL_REGEXP = '<%.*?%>'


class InlineYAQLEvaluator(YAQLEvaluator):
    # This regular expression will look for multiple occurrences of YAQL
    # expressions in '<% %>' (i.e. <% any_symbols %>) within a string.
    find_expression_pattern = re.compile(INLINE_YAQL_REGEXP)

    @classmethod
    def validate(cls, expression):
        LOG.debug(
            "Validating inline YAQL expression [expression='%s']", expression)

        if not isinstance(expression, six.string_types):
            raise exc.YaqlEvaluationException("Unsupported type '%s'." %
                                              type(expression))

        found_expressions = cls.find_inline_expressions(expression)

        if found_expressions:
            [super(InlineYAQLEvaluator, cls).validate(expr.strip("<%>"))
             for expr in found_expressions]

    @classmethod
    def evaluate(cls, expression, data_context):
        LOG.debug(
            "Evaluating inline YAQL expression [expression='%s', context=%s]"
            % (expression, data_context)
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

        LOG.debug("Inline YAQL expression result: %s" % result)

        return result

    @classmethod
    def is_expression(cls, s):
        return s

    @classmethod
    def find_inline_expressions(cls, s):
        return cls.find_expression_pattern.findall(s)


# TODO(rakhmerov): Make it configurable.
_EVALUATOR = InlineYAQLEvaluator


def validate(expression):
    return _EVALUATOR.validate(expression)


def evaluate(expression, context):
    # Check if the passed value is expression so we don't need to do this
    # every time on a caller side.
    if (not isinstance(expression, six.string_types) or
            not _EVALUATOR.is_expression(expression)):
        return expression

    return _EVALUATOR.evaluate(expression, context)


def _evaluate_item(item, context):
    if isinstance(item, six.string_types):
        try:
            return evaluate(item, context)
        except AttributeError as e:
            LOG.debug("Expression %s is not evaluated, [context=%s]: %s"
                      % (item, context, e))
            return item
    else:
        return evaluate_recursively(item, context)


def evaluate_recursively(data, context):
    data = copy.deepcopy(data)

    if not context:
        return data

    if isinstance(data, dict):
        for key in data:
            data[key] = _evaluate_item(data[key], context)
    elif isinstance(data, list):
        for index, item in enumerate(data):
            data[index] = _evaluate_item(item, context)
    elif isinstance(data, six.string_types):
        return _evaluate_item(data, context)

    return data
