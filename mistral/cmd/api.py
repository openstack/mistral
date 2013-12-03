# Copyright 2013 - Mirantis, Inc.
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

"""Script to start Mistral API service."""

import eventlet

import os
import sys
from wsgiref import simple_server

from oslo.config import cfg

from mistral.api import app
from mistral import config
from mistral.openstack.common import log as logging


eventlet.monkey_patch(
    os=True, select=True, socket=True, thread=True, time=True)

LOG = logging.getLogger('mistral.cmd.api')


def main():
    try:
        config.parse_args()
        logging.setup('Mistral')

        host = cfg.CONF.api.host
        port = cfg.CONF.api.port

        server = simple_server.make_server(host, port, app.setup_app())

        LOG.info("Mistral API is serving on http://%s:%s (PID=%s)" %
                 (host, port, os.getpid()))

        server.serve_forever()
    except RuntimeError, e:
        sys.stderr.write("ERROR: %s\n" % e)
        sys.exit(1)


if __name__ == '__main__':
    main()
