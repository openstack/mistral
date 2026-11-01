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

import socket
from unittest import mock

from mistral import exceptions as exc
from mistral.tests.unit import base
from mistral.utils import egress


def _addrinfo(ip):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (ip, 22))]


class EgressValidateHostTest(base.BaseTest):
    @mock.patch.object(socket, 'getaddrinfo')
    def test_metadata_service_is_blocked(self, gai):
        gai.return_value = _addrinfo('169.254.169.254')

        self.assertRaises(
            exc.UrlNotAllowedException,
            egress.validate_host,
            'metadata.internal',
            22,
            'action_std_ssh',
        )

        gai.assert_called_once_with('metadata.internal', 22)

    @mock.patch.object(socket, 'getaddrinfo')
    def test_public_host_is_allowed(self, gai):
        gai.return_value = _addrinfo('93.184.216.34')

        egress.validate_host('example.com', 22, 'action_std_ssh')

    @mock.patch.object(socket, 'getaddrinfo')
    def test_options_are_read_from_group(self, gai):
        self.override_config('denied_cidrs', [], group='action_std_http')
        self.override_config(
            'allowed_hosts', ['ok.example.com'], group='action_std_http'
        )
        gai.return_value = _addrinfo('127.0.0.1')

        self.assertRaises(
            exc.UrlNotAllowedException,
            egress.validate_host,
            'other.example.com',
            22,
            'action_std_ssh',
        )

        self.override_config('denied_cidrs', [], group='action_std_ssh')

        egress.validate_host('other.example.com', 22, 'action_std_ssh')

    @mock.patch.object(socket, 'getaddrinfo')
    def test_allowed_hosts(self, gai):
        self.override_config(
            'allowed_hosts', ['ok.example.com'], group='action_std_ssh'
        )
        gai.return_value = _addrinfo('93.184.216.34')

        egress.validate_host('ok.example.com', 22, 'action_std_ssh')

        self.assertRaises(
            exc.UrlNotAllowedException,
            egress.validate_host,
            'other.example.com',
            22,
            'action_std_ssh',
        )
