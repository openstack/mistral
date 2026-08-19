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

from unittest import mock

from mistral.api import app
from mistral.tests.unit import base


class WsgiLoggingSetupTest(base.BaseTest):
    """The WSGI entry point must configure oslo.log itself.

    Under uWSGI/gunicorn nothing calls the mistral-server launcher, so
    init_wsgi() has to set up logging - otherwise the API emits no
    INFO-level logs at all.
    """

    @mock.patch.object(app, 'setup_app')
    @mock.patch.object(app.logging, 'setup')
    @mock.patch.object(app.m_config, 'parse_args')
    def test_init_wsgi_sets_up_logging(self, parse_args_mock, log_setup_mock,
                                       setup_app_mock):
        app.init_wsgi()

        log_setup_mock.assert_called_once_with(mock.ANY, 'Mistral')
        # And it must happen after config is parsed.
        self.assertTrue(parse_args_mock.called)
        self.assertTrue(setup_app_mock.called)
