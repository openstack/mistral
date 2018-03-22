#    Copyright 2018 Nokia Networks.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import json

from mistral.actions import std_actions as std
from mistral.tests.unit import base


class SSHActionTest(base.BaseTest):

    def test_default_inputs(self):
        cmd = "echo -n ok"
        host = "localhost"
        username = "mistral"
        action = std.SSHAction(cmd, host, username)
        mock_ctx = None

        stdout = action.test(mock_ctx)
        params = json.loads(stdout)

        self.assertEqual("", params['password'], "Password does not match.")
        self.assertIsNone(
            params['private_key_filename'],
            "private_key_filename is not None.")
