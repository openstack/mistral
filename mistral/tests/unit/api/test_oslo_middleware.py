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

from mistral.tests.unit.api import base
from oslo_config import cfg
from oslo_middleware import http_proxy_to_wsgi as http_proxy_to_wsgi_middleware


class TestHTTPProxyToWSGIMiddleware(base.APITest):
    """Test oslo_middleware HTTPProxyToWSGI.

    It checks that oslo_middleware middleware HTTPProxyToWSGI is executed
    when enabled.
    """

    def setUp(self):
        # Make sure the HTTPProxyToWSGI options are registered
        cfg.CONF.register_opts(http_proxy_to_wsgi_middleware.OPTS,
                               'oslo_middleware')

        # Enable proxy headers parsing in HTTPProxyToWSGI middleware.
        self.override_config(
            "enable_proxy_headers_parsing",
            "True",
            group='oslo_middleware'
        )

        # Create the application.
        super(TestHTTPProxyToWSGIMiddleware, self).setUp()
