# Copyright 2014 - Mirantis, Inc.
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
import mock

from mistral.actions import std_actions as std
from mistral import exceptions as exc
from mistral.tests.unit import base


class FailActionTest(base.BaseTest):
    def test_fail_action(self):
        action = std.FailAction()

        self.assertRaises(exc.ActionException, action.run, mock.Mock)

    def test_fail_with_data(self):
        data = {
            "x": 1,
            "y": 2,
        }
        action = std.FailAction(error_data=data)

        action_result = action.run(context={})

        self.assertTrue(action_result.is_error())
        self.assertDictEqual(data, action_result.to_dict()['result'])
