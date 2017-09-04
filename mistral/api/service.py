# Copyright 2016 NEC Corporation. All rights reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from oslo_concurrency import processutils
from oslo_config import cfg
from oslo_service import service
from oslo_service import wsgi

from mistral.api import app
from mistral.rpc import clients as rpc_clients


class WSGIService(service.ServiceBase):
    """Provides ability to launch Mistral API from wsgi app."""

    def __init__(self, name):
        self.name = name
        self.app = app.setup_app()
        self.workers = (
            cfg.CONF.api.api_workers or processutils.get_worker_count()
        )

        self.server = wsgi.Server(
            cfg.CONF,
            name,
            self.app,
            host=cfg.CONF.api.host,
            port=cfg.CONF.api.port,
            use_ssl=cfg.CONF.api.enable_ssl_api
        )

    def start(self):
        # NOTE: When oslo.service creates an API worker it forks a new child
        # system process. The child process is created as precise copy of the
        # parent process (see how os.fork() works) and within the child process
        # oslo.service calls service's start() method again to reinitialize
        # what's needed. So we must clean up all RPC clients so that RPC works
        # properly (e.g. message routing for synchronous calls may be based on
        # generated queue names).
        rpc_clients.cleanup()

        self.server.start()

        print('API server started.')

    def stop(self):
        self.server.stop()

    def wait(self):
        self.server.wait()

    def reset(self):
        self.server.reset()
