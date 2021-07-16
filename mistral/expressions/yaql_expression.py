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

from collections import abc as collections_abc
import inspect
import re

from oslo_db import exception as db_exc
from oslo_log import log as logging
from yaml import representer
import yaql
from yaql.language import exceptions as yaql_exc
from yaql.language import factory
from yaql.language import utils as yaql_utils

from mistral.config import cfg
from mistral import exceptions as exc
from mistral.expressions import base
from mistral_lib import utils


LOG = logging.getLogger(__name__)

_YAQL_CONF = cfg.CONF.yaql

INLINE_YAQL_REGEXP = '<%.*?%>'

YAQL_ENGINE = None

ROOT_YAQL_CONTEXT = None

# TODO(rakhmerov): it's work around the bug in YAQL.
# YAQL shouldn't expose internal types to custom functions.
representer.SafeRepresenter.add_representer(
    yaql_utils.FrozenDict,
    representer.SafeRepresenter.represent_dict
)


def get_yaql_context(data_context):
    global ROOT_YAQL_CONTEXT

    if not ROOT_YAQL_CONTEXT:
        ROOT_YAQL_CONTEXT = yaql.create_context()

        _register_yaql_functions(ROOT_YAQL_CONTEXT)

    new_ctx = ROOT_YAQL_CONTEXT.create_child_context()

    new_ctx['$'] = (
        data_context if not cfg.CONF.yaql.convert_input_data
        else yaql_utils.convert_input_data(data_context)
    )

    if isinstance(data_context, dict):
        new_ctx['__env'] = data_context.get('__env')
        new_ctx['__execution'] = data_context.get('__execution')
        new_ctx['__task_execution'] = data_context.get('__task_execution')

    return new_ctx


def _register_yaql_functions(yaql_ctx):
    functions = base.get_custom_functions()

    for name in functions:
        yaql_ctx.register_function(functions[name], name=name)


def get_yaql_engine_options():
    return {
        "yaql.limitIterators": _YAQL_CONF.limit_iterators,
        "yaql.memoryQuota": _YAQL_CONF.memory_quota,
        "yaql.convertTuplesToLists": _YAQL_CONF.convert_tuples_to_lists,
        "yaql.convertSetsToLists": _YAQL_CONF.convert_sets_to_lists,
        "yaql.iterableDicts": _YAQL_CONF.iterable_dicts,
        "yaql.convertOutputData": _YAQL_CONF.convert_output_data
    }


def create_yaql_engine_class(keyword_operator, allow_delegates,
                             engine_options):
    return factory.YaqlFactory(
        keyword_operator=keyword_operator,
        allow_delegates=allow_delegates
    ).create(options=engine_options)


def get_yaql_engine_class():
    global YAQL_ENGINE

    if YAQL_ENGINE is not None:
        return YAQL_ENGINE

    YAQL_ENGINE = create_yaql_engine_class(
        _YAQL_CONF.keyword_operator,
        _YAQL_CONF.allow_delegates,
        get_yaql_engine_options()
    )

    LOG.info(
        "YAQL engine has been initialized with the options: \n%s",
        utils.merge_dicts(
            get_yaql_engine_options(),
            {
                "keyword_operator": _YAQL_CONF.keyword_operator,
                "allow_delegates": _YAQL_CONF.allow_delegates
            }
        )
    )

    return YAQL_ENGINE


def _sanitize_yaql_result(result):
    # Expression output conversion can be disabled but we can still
    # do some basic unboxing if we got an internal YAQL type.
    # TODO(rakhmerov): FrozenDict doesn't provide any public method
    # or property to access a regular dict that it wraps so ideally
    # we need to add it to YAQL. Once it's there we need to make a
    # fix here.
    if isinstance(result, yaql_utils.FrozenDict):
        return result._d

    if (inspect.isgenerator(result) or
            isinstance(result, collections_abc.Iterator)):
        return list(result)

    return result


class YAQLEvaluator(base.Evaluator):
    @classmethod
    def validate(cls, expression):
        try:
            get_yaql_engine_class()(expression)
        except (yaql_exc.YaqlException, KeyError, ValueError, TypeError) as e:
            raise exc.YaqlGrammarException(getattr(e, 'message', e))

    @classmethod
    def evaluate(cls, expression, data_context):
        expression = expression.strip() if expression else expression

        try:
            result = get_yaql_engine_class()(expression).evaluate(
                context=get_yaql_context(data_context)
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

        return _sanitize_yaql_result(result)

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
        if not isinstance(expression, str):
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
            "Starting to evaluate YAQL expression. "
            "[expression='%s']", expression
        )

        result = expression
        found_expressions = cls.find_inline_expressions(expression)

        if found_expressions:
            for expr in found_expressions:
                trim_expr = expr.strip("<%>")

                evaluated = super(InlineYAQLEvaluator, cls).evaluate(
                    trim_expr,
                    data_context
                )

                if len(expression) == len(expr):
                    result = evaluated
                else:
                    result = result.replace(expr, str(evaluated))

        return result

    @classmethod
    def is_expression(cls, s):
        return cls.find_expression_pattern.search(s)

    @classmethod
    def find_inline_expressions(cls, s):
        return cls.find_expression_pattern.findall(s)
