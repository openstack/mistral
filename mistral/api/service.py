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

import os
import threading

from cheroot.ssl import builtin as cheroot_ssl
from cheroot import wsgi
from oslo_config import cfg
from oslo_log import log as logging
from oslo_service import service
from oslo_service import sslutils

from mistral.api import app
from mistral.rpc import clients as rpc_clients


LOG = logging.getLogger(__name__)


def validate_cert_paths(cert_file, key_file):
    if cert_file and not os.path.exists(cert_file):
        raise RuntimeError(_("Unable to find cert_file: %s") % cert_file)
    if key_file and not os.path.exists(key_file):
        raise RuntimeError(_("Unable to find key_file: %s") % key_file)
    if not cert_file or not key_file:
        raise RuntimeError(_("When running server in SSL mode, you must "
                             "specify a valid cert_file and key_file "
                             "paths in your configuration file"))


class WSGIService(service.ServiceBase):
    """Provides ability to launch Mistral API from wsgi app."""

    def __init__(self, name):
        self.name = name
        self.app = app.setup_app()
        # NOTE(amorin) since we moved to cheroot, we can't start more than
        # one process.
        # If you want to use more than one worker, you should start
        # mistral-wsgi-api instead
        self.workers = 1

        bind_addr = (cfg.CONF.api.host, cfg.CONF.api.port)
        self.server = wsgi.Server(
            bind_addr=bind_addr,
            wsgi_app=self.app,
            server_name=name)

        if cfg.CONF.api.enable_ssl_api:
            # NOTE(amorin) I copy pasted this from ironic code and they
            # were warning about this so I kept it
            LOG.warning(
                "Using deprecated [ssl] group for TLS "
                "credentials: the global [ssl] configuration block is "
                "deprecated and will be removed in 2026.1"
            )
            # Register global SSL config options and validate the
            # existence of configured certificate/private key file paths,
            # when in secure mode.
            sslutils.is_enabled(cfg.CONF)
            cert_file = cfg.CONF.ssl.cert_file
            key_file = cfg.CONF.ssl.key_file
            validate_cert_paths(cert_file, key_file)
            self.server.ssl_adapter = cheroot_ssl.BuiltinSSLAdapter(
                certificate=cert_file,
                private_key=key_file,
            )

        self._thread = None

    def start(self):
        # NOTE: When oslo.service creates an API worker it forks a new child
        # system process. The child process is created as precise copy of the
        # parent process (see how os.fork() works) and within the child process
        # oslo.service calls service's start() method again to reinitialize
        # what's needed. So we must clean up all RPC clients so that RPC works
        # properly (e.g. message routing for synchronous calls may be based on
        # generated queue names).
        rpc_clients.cleanup()

        self.server.prepare()
        self._thread = threading.Thread(
            target=self.server.serve,
            daemon=True
        )
        self._thread.start()
        LOG.info('API server started with one process. If you want more '
                 'workers, consider switching to a wsgi server using '
                 'mistral-wsgi-api')

    def stop(self):
        if self.server:
            self.server.stop()
            if self._thread:
                self._thread.join(timeout=2)

    def wait(self):
        if self._thread:
            self._thread.join()

    def reset(self):
        pass
