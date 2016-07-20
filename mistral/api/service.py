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


class WSGIService(service.ServiceBase):
    """Provides ability to launch Mistral API from wsgi app."""

    def __init__(self, name):
        self.name = name
        self.app = app.setup_app()
        self.workers = (cfg.CONF.api.api_workers or
                        processutils.get_worker_count())

        self.server = wsgi.Server(
            cfg.CONF,
            name,
            self.app,
            host=cfg.CONF.api.host,
            port=cfg.CONF.api.port,
            use_ssl=cfg.CONF.api.enable_ssl_api
        )

    def start(self):
        self.server.start()

    def stop(self):
        self.server.stop()

    def wait(self):
        self.server.wait()

    def reset(self):
        self.server.reset()


def process_launcher():
    return service.ProcessLauncher(cfg.CONF)
