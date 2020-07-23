# Copyright 2015 - Mirantis, Inc.
# Copyright 2020 - Nokia Software.
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

from mistral import config as cfg
from mistral import exceptions as exc
from mistral import utils

from oslo_utils import importutils
from stevedore import driver
from stevedore import extension

_PYV8 = importutils.try_import('PyV8')
_V8EVAL = importutils.try_import('v8eval')
_PY_MINI_RACER = importutils.try_import('py_mini_racer.py_mini_racer')
_EVALUATOR = None


class JSEvaluator(object):
    @classmethod
    @abc.abstractmethod
    def evaluate(cls, script, context):
        """Executes given JavaScript.

        :param script: The text of JavaScript snippet that needs to be
        executed.
        :param context: This object will be assigned to the $ javascript
        variable.
        :return result of evaluated javascript code.
        :raise MistralException: if corresponding js library is not installed.
        """
        pass


class PyV8Evaluator(JSEvaluator):
    @classmethod
    def evaluate(cls, script, ctx):
        if not _PYV8:
            raise exc.MistralException(
                "PyV8 module is not available. Please install PyV8."
            )

        with _PYV8.JSContext() as js_ctx:
            # Prepare data context and way for interaction with it.
            js_ctx.eval('$ = %s' % utils.to_json_str(ctx))

            result = js_ctx.eval(script)

            return _PYV8.convert(result)


class V8EvalEvaluator(JSEvaluator):
    @classmethod
    def evaluate(cls, script, ctx):
        if not _V8EVAL:
            raise exc.MistralException(
                "v8eval module is not available. Please install v8eval."
            )

        v8 = _V8EVAL.V8()

        ctx_str = utils.to_json_str(ctx)

        return v8.eval(
            '$ = %s; %s' % (ctx_str, script)
        )


class PyMiniRacerEvaluator(JSEvaluator):
    @classmethod
    def evaluate(cls, script, ctx):
        if not _PY_MINI_RACER:
            raise exc.MistralException(
                "PyMiniRacer module is not available. Please install "
                "PyMiniRacer."
            )

        js_ctx = _PY_MINI_RACER.MiniRacer()

        return js_ctx.eval(
            '$ = {}; {}'.format(utils.to_json_str(ctx), script)
        )


_mgr = extension.ExtensionManager(
    namespace='mistral.expression.evaluators',
    invoke_on_load=False
)


def get_js_evaluator():
    global _EVALUATOR

    if not _EVALUATOR:
        mgr = driver.DriverManager(
            'mistral.js.implementation',
            cfg.CONF.js_implementation,
            invoke_on_load=True
        )

        _EVALUATOR = mgr.driver

    return _EVALUATOR


def evaluate(script, ctx):
    return get_js_evaluator().evaluate(script, ctx)
