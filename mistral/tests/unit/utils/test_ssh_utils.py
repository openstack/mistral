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

from paramiko.ecdsakey import ECDSAKey
from paramiko.ed25519key import Ed25519Key
from paramiko.rsakey import RSAKey
from paramiko.ssh_exception import SSHException

from mistral import exceptions as exc
from mistral.tests.unit import base
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

    def test_to_paramiko_private_key_rejects_path_traversal(self):
        """Files containing '..' are rejected with DataAccessException."""
        self.assertRaises(
            exc.DataAccessException,
            ssh_utils._to_paramiko_private_key,
            '../../../etc/passwd',
        )

    def test_to_paramiko_private_key_rejects_path_traversal_backslash(self):
        """Files containing '..\\' are rejected with DataAccessException."""
        self.assertRaises(
            exc.DataAccessException,
            ssh_utils._to_paramiko_private_key,
            'foo..\\bar',
        )

    def test_to_paramiko_private_key_rsa_from_file(self):
        """RSA key loaded from file via private_key_filename."""
        key = RSAKey.generate(2048)

        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.pem', delete=False
        ) as f:
            key.write_private_key(f)
            key_path = f.name

        try:
            result = ssh_utils._to_paramiko_private_key(
                private_key_filename=key_path,
            )

            self.assertIsNotNone(result)
            self.assertIsInstance(result, RSAKey)
        finally:
            os.unlink(key_path)

    def test_to_paramiko_private_key_no_key_returns_none(self):
        """When no key material is provided, None is returned."""
        result = ssh_utils._to_paramiko_private_key(
            private_key_filename=None,
            private_key=None,
        )

        self.assertIsNone(result)

    def test_to_paramiko_private_key_absolute_path_used_as_is(self):
        """Absolute filename is used without prepending KEY_PATH."""
        with mock.patch.object(RSAKey, 'from_private_key_file') as rsa_from:
            rsa_from.return_value = mock.Mock()

            ssh_utils._to_paramiko_private_key(
                private_key_filename='/absolute/path/to/key',
            )

            rsa_from.assert_called_once_with(
                filename='/absolute/path/to/key',
                password=None,
            )

    def test_to_paramiko_private_key_relative_path_prepends_ssh_dir(self):
        """Relative filename is prepended with ~/.ssh/."""
        with mock.patch.object(RSAKey, 'from_private_key_file') as rsa_from:
            rsa_from.return_value = mock.Mock()

            ssh_utils._to_paramiko_private_key(
                private_key_filename='my_key',
            )

            expected_path = ssh_utils.KEY_PATH + 'my_key'

            rsa_from.assert_called_once_with(
                filename=expected_path,
                password=None,
            )
