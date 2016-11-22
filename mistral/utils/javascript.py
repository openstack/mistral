# Copyright 2015 - Mirantis, Inc.
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
import json

from oslo_utils import importutils

from mistral import config as cfg
from mistral import exceptions as exc

_PYV8 = importutils.try_import('PyV8')
_V8EVAL = importutils.try_import('v8eval')


class JSEvaluator(object):
    @classmethod
    @abc.abstractmethod
    def evaluate(cls, script, context):
        """Executes given JavaScript."""
        pass


class PyV8Evaluator(JSEvaluator):
    @classmethod
    def evaluate(cls, script, context):
        if not _PYV8:
            raise exc.MistralException(
                "PyV8 module is not available. Please install PyV8."
            )

        with _PYV8.JSContext() as ctx:
            # Prepare data context and way for interaction with it.
            ctx.eval('$ = %s' % json.dumps(context))

            result = ctx.eval(script)
            return _PYV8.convert(result)


class V8EvalEvaluator(JSEvaluator):
    @classmethod
    def evaluate(cls, script, context):
        if not _V8EVAL:
            raise exc.MistralException(
                "v8eval module is not available. Please install v8eval."
            )

        v8 = _V8EVAL.V8()
        return v8.eval(('$ = %s; %s' % (json.dumps(context), script)).encode(
            encoding='UTF-8'))


EVALUATOR = (V8EvalEvaluator if cfg.CONF.js_implementation == 'v8eval'
             else PyV8Evaluator)


def evaluate(script, context):
    return EVALUATOR.evaluate(script, context)
