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

from unittest import mock

from mistral.tests.unit import base
from mistral.utils import javascript


class PyMiniRacerEvaluatorTest(base.BaseTest):
    def setUp(self):
        super(PyMiniRacerEvaluatorTest, self).setUp()

        self.racer = mock.Mock()
        patcher = mock.patch.object(javascript, '_PY_MINI_RACER', self.racer)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.js_eval = self.racer.MiniRacer.return_value.eval

    def test_default_limits(self):
        javascript.PyMiniRacerEvaluator.evaluate('1 + 1', {})

        self.js_eval.assert_called_once_with(
            '$ = {}; 1 + 1',
            timeout=30000,
            max_memory=256 * 1024 * 1024
        )

    def test_custom_limits(self):
        self.override_config('timeout', 2, group='action_std_javascript')
        self.override_config(
            'max_memory_mb',
            16,
            group='action_std_javascript'
        )

        javascript.PyMiniRacerEvaluator.evaluate('1 + 1', {})

        self.js_eval.assert_called_once_with(
            '$ = {}; 1 + 1',
            timeout=2000,
            max_memory=16 * 1024 * 1024
        )

    def test_limits_disabled(self):
        self.override_config('timeout', 0, group='action_std_javascript')
        self.override_config('max_memory_mb', 0, group='action_std_javascript')

        javascript.PyMiniRacerEvaluator.evaluate('1 + 1', {})

        self.js_eval.assert_called_once_with('$ = {}; 1 + 1')
