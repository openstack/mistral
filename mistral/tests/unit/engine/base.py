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

import eventlet
from oslo.config import cfg
from oslo import messaging

from mistral import context as ctx
from mistral.db.v2 import api as db_api
from mistral.engine import default_engine as def_eng
from mistral.engine import default_executor as def_exec
from mistral.engine import rpc
from mistral.openstack.common import log as logging
from mistral.services import scheduler
from mistral.tests import base
from mistral.workflow import states

LOG = logging.getLogger(__name__)


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

        # Get transport here to let oslo.messaging setup default config
        # before changing the rpc_backend to the fake driver; otherwise,
        # oslo.messaging will throw exception.
        messaging.get_transport(cfg.CONF)

        # Set the transport to 'fake' for Engine tests.
        cfg.CONF.set_default('rpc_backend', 'fake')

        # Drop all RPC objects (transport, clients).
        rpc.cleanup()

        transport = rpc.get_transport()

        self.engine_client = rpc.EngineClient(transport)
        self.executor_client = rpc.ExecutorClient(transport)

        self.engine = def_eng.DefaultEngine(self.engine_client)
        self.executor = def_exec.DefaultExecutor(self.engine_client)

        LOG.info("Starting engine and executor threads...")

        self.threads = [
            eventlet.spawn(launch_engine_server, transport, self.engine),
            eventlet.spawn(launch_executor_server, transport, self.executor),
        ]

        self.addOnException(self.print_workflow_executions)

        # Start scheduler.
        scheduler_thread_group = scheduler.setup()

        self.addCleanup(self.kill_threads)
        self.addCleanup(scheduler_thread_group.stop)

    def kill_threads(self):
        LOG.info("Finishing engine and executor threads...")

        [thread.kill() for thread in self.threads]

    def print_workflow_executions(self, exc_info):
        print("\nEngine test case exception occurred: %s" % exc_info[1])
        print("Exception type: %s" % exc_info[0])
        print("\nPrinting workflow executions...")

        wf_execs = db_api.get_workflow_executions()

        for wf_ex in wf_execs:
            print(
                "\n%s [state=%s, output=%s]" %
                (wf_ex.name, wf_ex.state, wf_ex.output)
            )

            for t_ex in wf_ex.task_executions:
                print(
                    "\t%s [state=%s, published=%s]" %
                    (t_ex.name, t_ex.state, t_ex.published)
                )

    def is_task_in_state(self, task_ex_id, state):
        return db_api.get_task_execution(task_ex_id).state == state

    def is_execution_in_state(self, wf_ex_id, state):
        return db_api.get_workflow_execution(wf_ex_id).state == state

    def is_execution_success(self, wf_ex_id):
        return self.is_execution_in_state(wf_ex_id, states.SUCCESS)

    def is_execution_error(self, wf_ex_id):
        return self.is_execution_in_state(wf_ex_id, states.ERROR)

    def is_execution_paused(self, wf_ex_id):
        return self.is_execution_in_state(wf_ex_id, states.PAUSED)

    def is_task_success(self, task_ex_id):
        return self.is_task_in_state(task_ex_id, states.SUCCESS)

    def is_task_error(self, task_ex_id):
        return self.is_task_in_state(task_ex_id, states.ERROR)

    def is_task_delayed(self, task_ex_id):
        return self.is_task_in_state(task_ex_id, states.DELAYED)
