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

from mistral.actions import std_actions as std
from mistral import exceptions as exc
from mistral.tests.unit import base


@mock.patch.object(std, 'time')
class SleepActionTest(base.BaseTest):
    def test_sleep_within_limit(self, time_mock):
        self.override_config('max_seconds', 10, group='action_std_sleep')

        std.SleepAction(seconds=10).run(mock.Mock())

        time_mock.sleep.assert_called_once_with(10)

    def test_sleep_over_limit(self, time_mock):
        self.override_config('max_seconds', 10, group='action_std_sleep')

        self.assertRaises(
            exc.ActionException,
            std.SleepAction(seconds=11).run,
            mock.Mock()
        )
        time_mock.sleep.assert_not_called()

    def test_sleep_default_limit(self, time_mock):
        self.assertRaises(
            exc.ActionException,
            std.SleepAction(seconds=10 ** 9).run,
            mock.Mock()
        )
        time_mock.sleep.assert_not_called()

    def test_sleep_limit_disabled(self, time_mock):
        self.override_config('max_seconds', 0, group='action_std_sleep')

        std.SleepAction(seconds=10 ** 9).run(mock.Mock())

        time_mock.sleep.assert_called_once_with(10 ** 9)

    def test_echo_delay_over_limit(self, time_mock):
        self.override_config('max_seconds', 10, group='action_std_sleep')

        self.assertRaises(
            exc.ActionException,
            std.EchoAction('out', delay=10.5).run,
            mock.Mock()
        )
        time_mock.sleep.assert_not_called()

    def test_echo_delay_within_limit(self, time_mock):
        self.override_config('max_seconds', 10, group='action_std_sleep')

        self.assertEqual(
            'out',
            std.EchoAction('out', delay=2).run(mock.Mock())
        )
        time_mock.sleep.assert_called_once_with(2.0)
