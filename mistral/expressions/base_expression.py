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
