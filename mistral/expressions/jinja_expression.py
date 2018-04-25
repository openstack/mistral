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

import re

import jinja2
from jinja2 import parser as jinja_parse
from jinja2.sandbox import SandboxedEnvironment
from oslo_db import exception as db_exc
from oslo_log import log as logging
import six

from mistral import exceptions as exc
from mistral.expressions.base_expression import Evaluator
from mistral.utils import expression_utils


LOG = logging.getLogger(__name__)

ANY_JINJA_REGEXP = "{{.*}}|{%.*%}"

JINJA_REGEXP = '({{(.*?)}})'
JINJA_BLOCK_REGEXP = '({%(.*?)%})'

JINJA_OPTS = {'undefined_to_none': False}

_environment = SandboxedEnvironment(
    undefined=jinja2.StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True
)

_filters = expression_utils.get_custom_functions()

for name in _filters:
    _environment.filters[name] = _filters[name]


class JinjaEvaluator(Evaluator):
    _env = _environment.overlay()

    @classmethod
    def validate(cls, expression):
        if not isinstance(expression, six.string_types):
            raise exc.JinjaEvaluationException(
                "Unsupported type '%s'." % type(expression)
            )

        try:
            parser = jinja_parse.Parser(cls._env, expression, state='variable')

            parser.parse_expression()
        except jinja2.exceptions.TemplateError as e:
            raise exc.JinjaGrammarException(
                "Syntax error '%s'." % str(e)
            )

    @classmethod
    def evaluate(cls, expression, data_context):
        ctx = expression_utils.get_jinja_context(data_context)

        result = cls._env.compile_expression(
            expression,
            **JINJA_OPTS
        )(**ctx)

        # For StrictUndefined values, UndefinedError only gets raised when
        # the value is accessed, not when it gets created. The simplest way
        # to access it is to try and cast it to string.
        str(result)

        return result

    @classmethod
    def is_expression(cls, s):
        # The class should only be called from within InlineJinjaEvaluator. The
        # return value prevents the class from being accidentally added as
        # Extension
        return False


class InlineJinjaEvaluator(Evaluator):
    # The regular expression for Jinja variables and blocks
    find_expression_pattern = re.compile(JINJA_REGEXP)
    find_block_pattern = re.compile(JINJA_BLOCK_REGEXP)

    _env = _environment.overlay()

    @classmethod
    def validate(cls, expression):
        if not isinstance(expression, six.string_types):
            raise exc.JinjaEvaluationException(
                "Unsupported type '%s'." % type(expression)
            )

        try:
            cls._env.parse(expression)
        except jinja2.exceptions.TemplateError as e:
            raise exc.JinjaGrammarException(
                "Syntax error '%s'." % str(e)
            )

    @classmethod
    def evaluate(cls, expression, data_context):
        LOG.debug(
            "Start to evaluate Jinja expression. "
            "[expression='%s', context=%s]",
            expression,
            data_context
        )

        patterns = cls.find_expression_pattern.findall(expression)

        try:
            if patterns[0][0] == expression:
                result = JinjaEvaluator.evaluate(patterns[0][1], data_context)
            else:
                ctx = expression_utils.get_jinja_context(data_context)
                result = cls._env.from_string(expression).render(**ctx)
        except Exception as e:
            # NOTE(rakhmerov): if we hit a database error then we need to
            # re-raise the initial exception so that upper layers had a
            # chance to handle it properly (e.g. in case of DB deadlock
            # the operations needs to retry. Essentially, such situation
            # indicates a problem with DB rather than with the expression
            # syntax or values.
            if isinstance(e, db_exc.DBError):
                LOG.error(
                    "Failed to evaluate Jinja expression due to a database"
                    " error, re-raising initial exception [expression=%s,"
                    " error=%s, data=%s]",
                    expression,
                    str(e),
                    data_context
                )

                raise e

            raise exc.JinjaEvaluationException(
                "Can not evaluate Jinja expression [expression=%s, error=%s"
                ", data=%s]" % (expression, str(e), data_context)
            )

        LOG.debug(
            "Finished evaluation. [expression='%s', result: %s]",
            expression,
            result
        )

        return result

    @classmethod
    def is_expression(cls, s):
        return (cls.find_expression_pattern.search(s) or
                cls.find_block_pattern.search(s))
