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

import resource
import subprocess
import sys
from unittest import mock

from mistral.tests.unit import base
from mistral.utils import resource_limits


class ApplyMemoryLimitTest(base.BaseTest):
    @mock.patch.object(resource, 'setrlimit')
    @mock.patch.object(resource, 'getrlimit')
    def test_disabled_by_default(self, get_mock, set_mock):
        resource_limits.apply_memory_limit(0)

        set_mock.assert_not_called()

    @mock.patch.object(resource, 'setrlimit')
    @mock.patch.object(resource, 'getrlimit')
    def test_sets_soft_limit_only(self, get_mock, set_mock):
        get_mock.return_value = (resource.RLIM_INFINITY,
                                 resource.RLIM_INFINITY)

        resource_limits.apply_memory_limit(512)

        set_mock.assert_called_once_with(
            resource.RLIMIT_AS,
            (512 * 1024 * 1024, resource.RLIM_INFINITY)
        )

    @mock.patch.object(resource, 'setrlimit')
    @mock.patch.object(resource, 'getrlimit')
    def test_soft_limit_capped_by_existing_hard_limit(self, get_mock,
                                                      set_mock):
        hard = 256 * 1024 * 1024
        get_mock.return_value = (resource.RLIM_INFINITY, hard)

        resource_limits.apply_memory_limit(512)

        # The requested 512 MiB is above the existing hard limit, so the
        # soft limit is capped at the hard limit and the hard limit is
        # left untouched.
        set_mock.assert_called_once_with(resource.RLIMIT_AS, (hard, hard))


class MemoryBombTest(base.BaseTest):
    """End-to-end check that a memory bomb is contained.

    The limit and the bomb both run in a dedicated subprocess, so the
    RLIMIT_AS cap can only ever affect that child - never the test
    runner.
    """

    def test_jinja_bomb_is_turned_into_evaluation_error(self):
        # 200 MiB is comfortably above the interpreter baseline (the
        # imports already happened) but far below the ~16 GiB the bomb
        # tries to allocate, so the allocation reliably raises MemoryError.
        script = (
            "from mistral.utils import resource_limits;"
            "from mistral.expressions import jinja_expression as j;"
            "from mistral import exceptions as exc;"
            "resource_limits.apply_memory_limit(200);"
            "e=j.InlineJinjaEvaluator;"
            "\ntry:\n"
            "    e.evaluate('{{ [0] * 2000000000 }}', {})\n"
            "    print('NO_ERROR')\n"
            "except exc.JinjaEvaluationException:\n"
            "    print('EVAL_ERROR')\n"
            "except MemoryError:\n"
            "    print('RAW_MEMORY_ERROR')\n"
        )

        out = subprocess.run(
            [sys.executable, '-c', script],
            capture_output=True,
            text=True,
            timeout=120
        )

        self.assertIn('EVAL_ERROR', out.stdout)
