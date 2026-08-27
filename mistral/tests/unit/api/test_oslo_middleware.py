# All Rights Reserved.
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

"""Tests http_proxy_to_wsgi middleware."""

import webob

from mistral.api import app as api_app
from mistral.tests.unit.api import base
from mistral.tests.unit import base as test_base
from oslo_config import cfg
from oslo_middleware import healthcheck
from oslo_middleware import http_proxy_to_wsgi


class TestHTTPProxyToWSGIMiddleware(base.APITest):
    """Test oslo_middleware HTTPProxyToWSGI.

    It checks that oslo_middleware middleware HTTPProxyToWSGI is executed
    when enabled.
    """

    def setUp(self):
        # Make sure the HTTPProxyToWSGI options are registered
        cfg.CONF.register_opts(http_proxy_to_wsgi.OPTS,
                               'oslo_middleware')

        # Enable proxy headers parsing in HTTPProxyToWSGI middleware.
        self.override_config(
            "enable_proxy_headers_parsing",
            True,
            group='oslo_middleware'
        )

        # Create the application.
        super(TestHTTPProxyToWSGIMiddleware, self).setUp()


class TestHealthcheckMiddleware(base.APITest):
    """Test oslo_middleware Healthcheck.

    It checks that oslo_middleware middleware Healthcheck is executed
    when enabled.
    """

    def setUp(self):
        # Make sure the Healthcheck options are registered
        cfg.CONF.register_opts(healthcheck.OPTS,
                               'oslo_middleware')

        # Enable healthcheck middleware.
        self.override_config(
            "enabled",
            True,
            group='healthcheck'
        )

        # Create the application.
        super(TestHealthcheckMiddleware, self).setUp()


class TestHealthcheckPathDispatch(test_base.BaseTest):
    """The healthcheck must only answer on /healthcheck.

    Recent oslo.middleware Healthcheck, wrapped around the whole app,
    answers every request with 200, so a missing resource returns 200
    instead of 404. mistral routes only /healthcheck to it.
    """

    @staticmethod
    def _real_app(environ, start_response):
        start_response('404 Not Found', [('Content-Type', 'text/plain')])
        return [b'not found']

    def setUp(self):
        super(TestHealthcheckPathDispatch, self).setUp()

        self.dispatched = api_app._mount_healthcheck(self._real_app)

    def _get(self, path):
        return webob.Request.blank(path).get_response(self.dispatched)

    def test_healthcheck_path_is_answered_by_healthcheck(self):
        resp = self._get('/healthcheck')

        self.assertEqual(200, resp.status_int)

    def test_other_paths_reach_the_real_app(self):
        # The bug was that these returned 200 from the healthcheck instead
        # of reaching the real application.
        for path in ('/v2/workflows/does-not-exist', '/', '/anything'):
            resp = self._get(path)

            self.assertEqual(404, resp.status_int)
            self.assertIn(b'not found', resp.body)
