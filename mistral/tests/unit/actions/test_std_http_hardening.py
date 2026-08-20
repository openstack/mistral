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

import json
from unittest import mock

import requests

from mistral.actions import std_actions as std
from mistral import exceptions as exc
from mistral.tests.unit import base

URL = 'http://some_url'


class HttpActionHardeningTest(base.BaseTest):
    @mock.patch.object(requests, 'request')
    def test_default_timeout_applied_when_unset(self, req):
        self.override_config('default_timeout', 42, group='action_std_http')
        req.return_value = base.FakeHTTPResponse(
            json.dumps({'a': 1}), 200,
            headers={'Content-Type': 'application/json'}
        )

        std.HTTPAction(url=URL).run(mock.Mock())

        self.assertEqual(42, req.call_args.kwargs['timeout'])

    @mock.patch.object(requests, 'request')
    def test_action_timeout_overrides_default(self, req):
        self.override_config('default_timeout', 42, group='action_std_http')
        req.return_value = base.FakeHTTPResponse(json.dumps({}), 200)

        std.HTTPAction(url=URL, timeout=5).run(mock.Mock())

        self.assertEqual(5, req.call_args.kwargs['timeout'])

    @mock.patch.object(requests, 'request')
    def test_oversized_response_is_rejected(self, req):
        self.override_config('max_response_size_bytes', 100,
                             group='action_std_http')
        req.return_value = base.FakeHTTPResponse(
            'x', 200, headers={'Content-Length': '10000000'}
        )

        self.assertRaises(
            exc.ActionException,
            std.HTTPAction(url=URL).run,
            mock.Mock()
        )

    @mock.patch.object(requests, 'request')
    def test_default_response_cap_rejects_huge_response(self, req):
        # With the default 5 MiB cap (no override), a response declaring a
        # very large Content-Length is rejected.
        req.return_value = base.FakeHTTPResponse(
            'x', 200, headers={'Content-Length': str(50 * 1024 * 1024)}
        )

        self.assertRaises(
            exc.ActionException,
            std.HTTPAction(url=URL).run,
            mock.Mock()
        )

    @mock.patch.object(requests, 'request')
    def test_response_within_limit_is_allowed(self, req):
        self.override_config('max_response_size_bytes', 100,
                             group='action_std_http')
        req.return_value = base.FakeHTTPResponse(
            json.dumps({'a': 1}), 200,
            headers={'Content-Length': '20',
                     'Content-Type': 'application/json'}
        )

        result = std.HTTPAction(url=URL).run(mock.Mock())

        self.assertEqual(200, result['status'])
