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
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (ip, 80))]


class EgressValidateUrlTest(base.BaseTest):
    @mock.patch.object(socket, 'getaddrinfo')
    def test_metadata_service_is_blocked(self, gai):
        gai.return_value = _addrinfo('169.254.169.254')

        self.assertRaises(
            exc.UrlNotAllowedException,
            egress.validate_url,
            'http://169.254.169.254/latest/meta-data/'
        )

    @mock.patch.object(socket, 'getaddrinfo')
    def test_loopback_is_blocked(self, gai):
        gai.return_value = _addrinfo('127.0.0.1')

        self.assertRaises(
            exc.UrlNotAllowedException,
            egress.validate_url,
            'http://localhost:8080/'
        )

    @mock.patch.object(socket, 'getaddrinfo')
    def test_operator_can_re_enable_by_emptying_denied_cidrs(self, gai):
        # An operator that wants std.http to reach loopback / the metadata
        # service can clear the deny-list.
        self.override_config('denied_cidrs', [], group='action_std_http')
        gai.return_value = _addrinfo('169.254.169.254')

        # Should not raise.
        egress.validate_url('http://169.254.169.254/latest/meta-data/')

    @mock.patch.object(socket, 'getaddrinfo')
    def test_dns_pointing_to_metadata_is_blocked(self, gai):
        # A public-looking hostname that resolves to the metadata IP.
        gai.return_value = _addrinfo('169.254.169.254')

        self.assertRaises(
            exc.UrlNotAllowedException,
            egress.validate_url,
            'http://evil.example.com/'
        )

    def test_non_http_scheme_is_blocked(self):
        self.assertRaises(
            exc.UrlNotAllowedException,
            egress.validate_url,
            'file:///etc/passwd'
        )

    @mock.patch.object(socket, 'getaddrinfo')
    def test_public_host_is_allowed(self, gai):
        gai.return_value = _addrinfo('93.184.216.34')

        # Should not raise.
        egress.validate_url('http://example.com/')

    @mock.patch.object(socket, 'getaddrinfo')
    def test_rfc1918_allowed_by_default(self, gai):
        # Internal OpenStack endpoints must keep working out of the box.
        gai.return_value = _addrinfo('10.0.0.5')

        egress.validate_url('http://internal-keystone:5000/')

    @mock.patch.object(socket, 'getaddrinfo')
    def test_denied_cidrs_config_blocks_rfc1918(self, gai):
        self.override_config('denied_cidrs', ['10.0.0.0/8'],
                             group='action_std_http')
        gai.return_value = _addrinfo('10.0.0.5')

        self.assertRaises(
            exc.UrlNotAllowedException,
            egress.validate_url,
            'http://internal-keystone:5000/'
        )

    @mock.patch.object(socket, 'getaddrinfo')
    def test_allowed_hosts_allowlist(self, gai):
        self.override_config('allowed_hosts', ['ok.example.com'],
                             group='action_std_http')
        gai.return_value = _addrinfo('93.184.216.34')

        egress.validate_url('http://ok.example.com/')
        self.assertRaises(
            exc.UrlNotAllowedException,
            egress.validate_url,
            'http://other.example.com/'
        )

    def test_unresolvable_host_fails_open(self):
        # If the host cannot be resolved the request would fail to connect
        # anyway, so validation must not raise (and must not break the
        # existing tests that use non-resolvable hostnames).
        with mock.patch.object(socket, 'getaddrinfo',
                               side_effect=socket.gaierror):
            egress.validate_url('http://some_url/')
