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
import mock

from mistral.actions import std_actions as std
from mistral import exceptions as exc
from mistral.tests.unit import base
import mistral.utils.ssh_utils


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

    @mock.patch.object(mistral.utils.ssh_utils, 'execute_command')
    def test_ssh_action(self, mocked_method):
        mocked_method.return_value = (0, 'ok')
        cmd = "echo -n ok"
        host = "localhost"
        username = "mistral"
        action = std.SSHAction(cmd, host, username)

        mock_ctx = None

        stdout = action.run(mock_ctx)

        self.assertEqual('ok', stdout,
                         'stdout from SSH command differs from expected')

        mocked_method.assert_called_with(
            cmd=cmd,
            host=host,
            username=username,
            password='',
            private_key_filename=None
        )

    @mock.patch.object(mistral.utils.ssh_utils, 'execute_command')
    def test_ssh_action_with_stderr(self, mocked_method):
        mocked_method.return_value = (1, 'Error expected')
        cmd = "echo -n ok"
        host = "localhost"
        username = "mistral"
        action = std.SSHAction(cmd, host, username)

        mock_ctx = None

        self.assertRaisesWithMessageContaining(
            exc.ActionException,
            "Failed to execute ssh cmd 'echo -n ok' on ['localhost']",
            action.run,
            mock_ctx
        )
