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

import mock

from mistral.actions import std_actions as std
from mistral.tests.unit import base
from mistral.utils import javascript


class JavascriptActionTest(base.BaseTest):
    @mock.patch.object(
        javascript, 'evaluate', mock.Mock(return_value="3")
    )
    def test_js_action(self):
        script = "return 1 + 2"
        action = std.JavaScriptAction(script)

        self.assertEqual("3", action.run())
