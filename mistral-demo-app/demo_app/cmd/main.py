#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
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

"""Script to start Demo API service."""

import eventlet

import logging
import os
from requests import exceptions
import sys
import threading
from time import sleep
from wsgiref import simple_server

from oslo.config import cfg

from demo_app import config
from demo_app.api import app
from demo_app.api import client


eventlet.monkey_patch(
    os=True, select=True, socket=True, thread=True, time=True)

logging.basicConfig(level=logging.WARN)
LOG = logging.getLogger('demo_app.cmd.main')
CLIENT = client.CLIENT


def upload_wb_and_start():
    sleep(5)
    try:
        client.upload_workbook()
    except exceptions.ConnectionError:
        LOG.error("Error. Mistral service probably is not working now")
        sys.exit(1)
    print("Start execution for: %s" % client.TARGET_TASK)

    client.start_execution()


def main():
    try:
        config.parse_args()

        host = cfg.CONF.api.host
        port = cfg.CONF.api.port

        server = simple_server.make_server(host, port, app.setup_app())

        LOG.info("Demo app API is serving on http://%s:%s (PID=%s)" %
                 (host, port, os.getpid()))

        server.serve_forever()
    except RuntimeError, e:
        sys.stderr.write("ERROR: %s\n" % e)
        sys.exit(1)


if __name__ == '__main__':
    upload_thread = threading.Thread(target=upload_wb_and_start)
    upload_thread.run()
    main()
