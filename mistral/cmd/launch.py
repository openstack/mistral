#!/usr/bin/env python
# -*- coding: utf-8 -*-
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

import sys
import eventlet

eventlet.monkey_patch(
    os=True,
    select=True,
    socket=True,
    thread=False if '--use-debugger' in sys.argv else True,
    time=True)

import os

# If ../mistral/__init__.py exists, add ../ to Python search path, so that
# it will override what happens to be installed in /usr/(local/)lib/python...
POSSIBLE_TOPDIR = os.path.normpath(os.path.join(os.path.abspath(sys.argv[0]),
                                   os.pardir,
                                   os.pardir))
if os.path.exists(os.path.join(POSSIBLE_TOPDIR, 'mistral', '__init__.py')):
    sys.path.insert(0, POSSIBLE_TOPDIR)

from oslo import messaging
from oslo.config import cfg

from mistral import config
from mistral import engine
from mistral.engine.scalable.executor import server
from mistral.api import app
from wsgiref import simple_server
from mistral.openstack.common import log as logging


LOG = logging.getLogger(__name__)


def launch_executor(transport):
    target = messaging.Target(topic=cfg.CONF.executor.topic,
                              server=cfg.CONF.executor.host)
    endpoints = [server.Executor(transport)]
    ex_server = messaging.get_rpc_server(
        transport, target, endpoints, executor='eventlet')
    ex_server.start()
    ex_server.wait()


def launch_engine(transport):
    target = messaging.Target(topic=cfg.CONF.engine.topic,
                              server=cfg.CONF.engine.host)
    endpoints = [engine.Engine(transport)]
    en_server = messaging.get_rpc_server(
        transport, target, endpoints, executor='eventlet')
    en_server.start()
    en_server.wait()


def launch_api(transport):
    host = cfg.CONF.api.host
    port = cfg.CONF.api.port
    server = simple_server.make_server(host, port,
                                       app.setup_app(transport=transport))
    LOG.info("Mistral API is serving on http://%s:%s (PID=%s)" %
             (host, port, os.getpid()))
    server.serve_forever()


def launch_all(transport):
    # Launch the servers on different threads.
    t1 = eventlet.spawn(launch_executor, transport)
    t2 = eventlet.spawn(launch_engine, transport)
    t3 = eventlet.spawn(launch_api, transport)
    t1.wait() and t2.wait() and t3.wait()


def main():
    try:
        config.parse_args()
        logging.setup('Mistral')

        # Map cli options to appropriate functions. The cli options are
        # registered in mistral's config.py.
        launch_options = {
            'all': launch_all,
            'api': launch_api,
            'engine': launch_engine,
            'executor': launch_executor
        }

        # Please refer to the oslo.messaging documentation for transport
        # configuration. The default transport for oslo.messaging is rabbitMQ.
        # The available transport drivers are listed under oslo.messaging at
        # ./oslo/messaging/rpc/_drivers.  The drivers are prefixed with "impl".
        # The transport driver is specified using the rpc_backend option in the
        # default section of the oslo configuration file. The expected value
        # for rpc_backend is the last part of the driver name. For example,
        # the driver for rabbit is impl_rabbit and for the fake driver is
        # impl_fake. The rpc_backend value for these are "rabbit" and "fake"
        # respectively. There are additional options such as ssl and credential
        # that can be specified depending on the driver.  Please refer to the
        # driver implementation for those additional options.
        transport = messaging.get_transport(cfg.CONF)

        # Launch server(s).
        launch_options[cfg.CONF.server](transport)

    except RuntimeError, e:
        sys.stderr.write("ERROR: %s\n" % e)
        sys.exit(1)


if __name__ == '__main__':
    main()
