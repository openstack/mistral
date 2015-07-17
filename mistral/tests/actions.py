# Copyright 2015 - StackStorm, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
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

from mistral.actions import base as base_actions
from mistral.actions import std_actions


class MockEchoAction(base_actions.Action):
    mock_failure = True
    mock_which = []

    def __init__(self, output):
        self.output = output

    def run(self):
        if self.mock_failure and self.output in self.mock_which:
            raise Exception('Test action error for output="%s".', self.output)

        return std_actions.EchoAction(self.output).run()
