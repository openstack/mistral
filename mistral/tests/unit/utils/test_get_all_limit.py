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

from mistral.tests.unit import base
from mistral.utils import rest_utils


class ClampLimitTest(base.BaseTest):
    """List requests must be capped at [api] max_limit."""

    def test_none_limit_is_clamped_to_max(self):
        self.override_config('max_limit', 50, group='api')

        self.assertEqual(50, rest_utils.clamp_limit(None))

    def test_over_max_limit_is_clamped(self):
        self.override_config('max_limit', 50, group='api')

        self.assertEqual(50, rest_utils.clamp_limit(10000))

    def test_small_limit_is_preserved(self):
        self.override_config('max_limit', 50, group='api')

        self.assertEqual(10, rest_utils.clamp_limit(10))
