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

import copy

from oslo_log import log as logging
import six
from stevedore import extension

from mistral import exceptions as exc

LOG = logging.getLogger(__name__)

_mgr = extension.ExtensionManager(
    namespace='mistral.expression.evaluators',
    invoke_on_load=False
)

_evaluators = []
patterns = {}

for name in sorted(_mgr.names()):
    evaluator = _mgr[name].plugin
    _evaluators.append((name, evaluator))
    patterns[name] = evaluator.find_expression_pattern.pattern


def validate(expression):
    LOG.debug("Validating expression [expression='%s']", expression)

    if not isinstance(expression, six.string_types):
        return

    expression_found = None

    for name, evaluator in _evaluators:
        if evaluator.is_expression(expression):
            if expression_found:
                raise exc.ExpressionGrammarException(
                    "The line already contains an expression of type '%s'. "
                    "Mixing expression types in a single line is not allowed."
                    % expression_found)

            try:
                evaluator.validate(expression)
            except Exception:
                raise
            else:
                expression_found = name


def evaluate(expression, context):
    for name, evaluator in _evaluators:
        # Check if the passed value is expression so we don't need to do this
        # every time on a caller side.
        if (isinstance(expression, six.string_types) and
                evaluator.is_expression(expression)):
            return evaluator.evaluate(expression, context)

    return expression


def _evaluate_item(item, context):
    if isinstance(item, six.string_types):
        try:
            return evaluate(item, context)
        except AttributeError as e:
            LOG.debug(
                "Expression %s is not evaluated, [context=%s]: %s",
                item,
                context,
                e
            )
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
