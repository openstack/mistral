# Copyright 2014 - Mirantis, Inc.
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
from oslo.config import cfg
from oslo import messaging
from oslo.messaging import transport

from mistral import context as ctx
from mistral.engine1 import default_engine as def_eng
from mistral.engine1 import default_executor as def_exec
from mistral.engine1 import rpc
from mistral.openstack.common import log as logging
from mistral.tests import base

from stevedore import driver


eventlet.monkey_patch(
    os=True,
    select=True,
    socket=True,
    thread=False if '--use-debugger' in sys.argv else True,
    time=True
)

LOG = logging.getLogger(__name__)


def get_fake_transport():
    # Get transport here to let oslo.messaging setup default config
    # before changing the rpc_backend to the fake driver; otherwise,
    # oslo.messaging will throw exception.
    messaging.get_transport(cfg.CONF)

    cfg.CONF.set_default('rpc_backend', 'fake')

    url = transport.TransportURL.parse(cfg.CONF, None)

    kwargs = dict(
        default_exchange=cfg.CONF.control_exchange,
        allowed_remote_exmods=[]
    )

    mgr = driver.DriverManager(
        'oslo.messaging.drivers',
        url.transport,
        invoke_on_load=True,
        invoke_args=(cfg.CONF, url),
        invoke_kwds=kwargs
    )

    return transport.Transport(mgr.driver)


def launch_engine_server(transport, engine):
    target = messaging.Target(
        topic=cfg.CONF.engine.topic,
        server=cfg.CONF.engine.host
    )

    server = messaging.get_rpc_server(
        transport,
        target,
        [rpc.EngineServer(engine)],
        executor='eventlet',
        serializer=ctx.RpcContextSerializer(ctx.JsonPayloadSerializer())
    )

    server.start()
    server.wait()


def launch_executor_server(transport, executor):
    target = messaging.Target(
        topic=cfg.CONF.executor.topic,
        server=cfg.CONF.executor.host
    )

    server = messaging.get_rpc_server(
        transport,
        target,
        [rpc.ExecutorServer(executor)],
        executor='eventlet',
        serializer=ctx.RpcContextSerializer(ctx.JsonPayloadSerializer())
    )

    server.start()
    server.wait()


class EngineTestCase(base.DbTestCase):
    def setUp(self):
        super(EngineTestCase, self).setUp()

        transport = base.get_fake_transport()

        engine_client = rpc.EngineClient(transport)
        executor_client = rpc.ExecutorClient(transport)

        self.engine = def_eng.DefaultEngine(engine_client, executor_client)
        self.executor = def_exec.DefaultExecutor(engine_client)

        LOG.info("Starting engine and executor threads...")

        self.threads = [
            eventlet.spawn(launch_engine_server, transport, self.engine),
            eventlet.spawn(launch_executor_server, transport, self.executor),
        ]

    def tearDown(self):
        super(EngineTestCase, self).tearDown()

        LOG.info("Finishing engine and executor threads...")

        [thread.kill() for thread in self.threads]
