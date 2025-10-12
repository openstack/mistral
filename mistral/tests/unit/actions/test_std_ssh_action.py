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
from unittest import mock

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
            private_key_filename=None,
            private_key=None
        )

    @mock.patch.object(mistral.utils.ssh_utils, 'execute_command')
    def test_with_return_result_on_error_success(self, mocked_method):
        # Test with return_result_on_error=True and success
        mocked_method.return_value = (0, 'success stdout', 'success stderr')
        cmd = "echo -n ok"
        host = "localhost"
        username = "mistral"
        action = std.SSHAction(
            cmd, host, username,
            return_result_on_error=True
        )

        mock_ctx = None

        result = action.run(mock_ctx)

        self.assertIsInstance(result, dict)
        self.assertEqual('success stdout', result['stdout'])
        self.assertEqual('success stderr', result['stderr'])
        self.assertEqual(0, result['exit_code'])

        mocked_method.assert_called_with(
            raise_when_error=False,
            get_stderr=True,
            cmd=cmd,
            host=host,
            username=username,
            password='',
            private_key_filename=None,
            private_key=None
        )

    @mock.patch.object(mistral.utils.ssh_utils, 'execute_command')
    def test_with_return_result_on_error_failure(self, mocked_method):
        # Test with return_result_on_error=True and command failure (should not
        # raise exception)
        mocked_method.return_value = (1, 'error stdout', 'error stderr')
        cmd = "echo -n ok"
        host = "localhost"
        username = "mistral"
        action = std.SSHAction(
            cmd, host, username,
            return_result_on_error=True
        )

        mock_ctx = None

        result = action.run(mock_ctx)

        # Should NOT raise exception, should return structured result
        self.assertIsInstance(result, dict)
        self.assertEqual('error stdout', result['stdout'])
        self.assertEqual('error stderr', result['stderr'])
        self.assertEqual(1, result['exit_code'])

    @mock.patch.object(mistral.utils.ssh_utils, 'execute_command')
    def test_with_return_result_on_error_exception_handling(self,
                                                            mocked_method):
        # Test SSH connection failure handling
        # SHOULD still raise exception
        mocked_method.side_effect = Exception("SSH connection failed")
        cmd = "echo -n ok"
        host = "localhost"
        username = "mistral"
        action = std.SSHAction(
            cmd, host, username,
            return_result_on_error=True
        )

        mock_ctx = None

        # SSH connection failures should still raise exceptions
        # even with return_result_on_error=True
        self.assertRaises(exc.ActionException, action.run, mock_ctx)

    @mock.patch.object(mistral.utils.ssh_utils, 'execute_command')
    def test_default_behavior_unchanged(self, mocked_method):
        # Test that default behavior (return_result_on_error=False)
        # is unchanged
        mocked_method.return_value = (0, 'ok')
        cmd = "echo -n ok"
        host = "localhost"
        username = "mistral"
        # return_result_on_error defaults to False
        action = std.SSHAction(cmd, host, username)
        mock_ctx = None

        stdout = action.run(mock_ctx)

        self.assertEqual('ok', stdout)
        mocked_method.assert_called_with(
            cmd=cmd,
            host=host,
            username=username,
            password='',
            private_key_filename=None,
            private_key=None
        )

    @mock.patch.object(mistral.utils.ssh_utils, 'execute_command')
    def test_default_behavior_raises_on_failure(self, mocked_method):
        # Test that default behavior raises exception on failure
        mocked_method.return_value = (1, 'error')
        cmd = "echo -n ok"
        host = "localhost"
        username = "mistral"
        # return_result_on_error defaults to False
        action = std.SSHAction(cmd, host, username)

        mock_ctx = None
        self.assertRaises(exc.ActionException, action.run, mock_ctx)

    @mock.patch.object(mistral.utils.ssh_utils, 'execute_command')
    def test_multiple_hosts_with_return_result_on_error(self, mocked_method):
        # Test multiple hosts with return_result_on_error=True
        mocked_method.side_effect = [
            (0, 'host1 stdout', 'host1 stderr'),
            (1, 'host2 stdout', 'host2 stderr')
        ]
        cmd = "echo -n ok"
        host = ["host1", "host2"]
        username = "mistral"
        action = std.SSHAction(
            cmd, host, username,
            return_result_on_error=True
        )

        mock_ctx = None

        result = action.run(mock_ctx)

        # Should return list of results
        self.assertIsInstance(result, list)
        self.assertEqual(2, len(result))
        self.assertEqual('host1 stdout', result[0]['stdout'])
        self.assertEqual(0, result[0]['exit_code'])
        self.assertEqual('host2 stdout', result[1]['stdout'])
        self.assertEqual(1, result[1]['exit_code'])

    @mock.patch.object(mistral.utils.ssh_utils, 'execute_command')
    def test_single_host_returns_dict_not_list(self, mocked_method):
        # Test that single host returns dict, not list
        mocked_method.return_value = (0, 'stdout', 'stderr')
        cmd = "echo -n ok"
        host = "localhost"
        username = "mistral"
        action = std.SSHAction(
            cmd, host, username,
            return_result_on_error=True
        )

        mock_ctx = None

        result = action.run(mock_ctx)

        # Should return single dict, not list
        self.assertIsInstance(result, dict)
        self.assertNotIsInstance(result, list)
        self.assertEqual('stdout', result['stdout'])
        self.assertEqual('stderr', result['stderr'])
        self.assertEqual(0, result['exit_code'])
