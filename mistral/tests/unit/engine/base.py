# Copyright 2014 - Mirantis, Inc.
# Copyright 2015 - StackStorm, Inc.
# Copyright 2016 - Brocade Communications Systems, Inc.
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
from oslo_config import cfg
from oslo_log import log as logging
import oslo_messaging as messaging

from mistral import context as ctx
from mistral.db.v2 import api as db_api
from mistral.engine import default_engine as def_eng
from mistral.engine import default_executor as def_exec
from mistral.engine.rpc_backend import rpc
from mistral.services import scheduler
from mistral.tests.unit import base
from mistral.workflow import states


LOG = logging.getLogger(__name__)

# Default delay and timeout in seconds for await_xxx() functions.
DEFAULT_DELAY = 1
DEFAULT_TIMEOUT = 30


def launch_engine_server(transport, engine):
    target = messaging.Target(
        topic=cfg.CONF.engine.topic,
        server=cfg.CONF.engine.host
    )

    server = messaging.get_rpc_server(
        transport,
        target,
        [rpc.EngineServer(engine)],
        executor='blocking',
        serializer=ctx.RpcContextSerializer(ctx.JsonPayloadSerializer())
    )

    try:
        server.start()
        while True:
            eventlet.sleep(604800)
    except (KeyboardInterrupt, SystemExit):
        LOG.info("Stopping engine service...")
    finally:
        server.stop()
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
        executor='blocking',
        serializer=ctx.RpcContextSerializer(ctx.JsonPayloadSerializer())
    )

    try:
        server.start()
        while True:
            eventlet.sleep(604800)
    except (KeyboardInterrupt, SystemExit):
        LOG.info("Stopping executor service...")
    finally:
        server.stop()
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

        self.engine_client = rpc.get_engine_client()
        self.executor_client = rpc.get_executor_client()

        self.engine = def_eng.DefaultEngine(self.engine_client)
        self.executor = def_exec.DefaultExecutor(self.engine_client)

        LOG.info("Starting engine and executor threads...")

        self.threads = [
            eventlet.spawn(launch_engine_server, transport, self.engine),
            eventlet.spawn(launch_executor_server, transport, self.executor),
        ]

        self.addOnException(self.print_executions)

        # Start scheduler.
        scheduler_thread_group = scheduler.setup()

        self.addCleanup(self.kill_threads)
        self.addCleanup(scheduler_thread_group.stop)

    def kill_threads(self):
        LOG.info("Finishing engine and executor threads...")

        [thread.kill() for thread in self.threads]

    @staticmethod
    def print_executions(exc_info=None):
        if exc_info:
            print("\nEngine test case exception occurred: %s" % exc_info[1])
            print("Exception type: %s" % exc_info[0])

        print("\nPrinting workflow executions...")

        with db_api.transaction():
            wf_execs = db_api.get_workflow_executions()

            for w in wf_execs:
                print(
                    "\n%s (%s) [state=%s, state_info=%s, output=%s]" %
                    (w.name, w.id, w.state, w.state_info, w.output)
                )

                for t in w.task_executions:
                    print(
                        "\t%s [id=%s, state=%s, state_info=%s, processed=%s,"
                        " published=%s]" %
                        (t.name,
                         t.id,
                         t.state,
                         t.state_info,
                         t.processed,
                         t.published)
                    )

                    child_execs = t.executions

                    for a in child_execs:
                        print(
                            "\t\t%s [id=%s, state=%s, state_info=%s,"
                            " accepted=%s, output=%s]" %
                            (a.name,
                             a.id,
                             a.state,
                             a.state_info,
                             a.accepted,
                             a.output)
                        )

        print("\nPrinting standalone action executions...")

        child_execs = db_api.get_action_executions(task_execution_id=None)

        for a in child_execs:
            print(
                "\t\t%s [id=%s, state=%s, state_info=%s, accepted=%s,"
                " output=%s]" %
                (a.name,
                 a.id,
                 a.state,
                 a.state_info,
                 a.accepted,
                 a.output)
            )

    # Various methods for action execution objects.

    def is_action_in_state(self, ex_id, state):
        return db_api.get_action_execution(ex_id).state == state

    def await_action_state(self, ex_id, state, delay=DEFAULT_DELAY,
                           timeout=DEFAULT_TIMEOUT):
        self._await(
            lambda: self.is_action_in_state(ex_id, state),
            delay,
            timeout
        )

    def is_action_success(self, ex_id):
        return self.is_action_in_state(ex_id, states.SUCCESS)

    def is_action_error(self, ex_id):
        return self.is_action_in_state(ex_id, states.ERROR)

    def await_action_success(self, ex_id, delay=DEFAULT_DELAY,
                             timeout=DEFAULT_TIMEOUT):
        self.await_action_state(ex_id, states.SUCCESS, delay, timeout)

    def await_action_error(self, ex_id, delay=DEFAULT_DELAY,
                           timeout=DEFAULT_TIMEOUT):
        self.await_action_state(ex_id, states.ERROR, delay, timeout)

    # Various methods for task execution objects.

    def is_task_in_state(self, ex_id, state):
        return db_api.get_task_execution(ex_id).state == state

    def await_task_state(self, ex_id, state, delay=DEFAULT_DELAY,
                         timeout=DEFAULT_TIMEOUT):
        self._await(
            lambda: self.is_task_in_state(ex_id, state),
            delay,
            timeout
        )

    def is_task_success(self, task_ex_id):
        return self.is_task_in_state(task_ex_id, states.SUCCESS)

    def is_task_error(self, task_ex_id):
        return self.is_task_in_state(task_ex_id, states.ERROR)

    def is_task_delayed(self, task_ex_id):
        return self.is_task_in_state(task_ex_id, states.RUNNING_DELAYED)

    def is_task_processed(self, task_ex_id):
        return db_api.get_task_execution(task_ex_id).processed

    def await_task_success(self, ex_id, delay=DEFAULT_DELAY,
                           timeout=DEFAULT_TIMEOUT):
        self.await_task_state(ex_id, states.SUCCESS, delay, timeout)

    def await_task_error(self, ex_id, delay=DEFAULT_DELAY,
                         timeout=DEFAULT_TIMEOUT):
        self.await_task_state(ex_id, states.ERROR, delay, timeout)

    def await_task_cancelled(self, ex_id, delay=DEFAULT_DELAY,
                             timeout=DEFAULT_TIMEOUT):
        self.await_task_state(ex_id, states.CANCELLED, delay, timeout)

    def await_task_delayed(self, ex_id, delay=DEFAULT_DELAY,
                           timeout=DEFAULT_TIMEOUT):
        self.await_task_state(ex_id, states.RUNNING_DELAYED, delay, timeout)

    def await_task_processed(self, ex_id, delay=DEFAULT_DELAY,
                             timeout=DEFAULT_TIMEOUT):
        self._await(lambda: self.is_task_processed(ex_id), delay, timeout)

    # Various methods for workflow execution objects.

    def is_workflow_in_state(self, ex_id, state):
        return db_api.get_workflow_execution(ex_id).state == state

    def await_workflow_state(self, ex_id, state, delay=DEFAULT_DELAY,
                             timeout=DEFAULT_TIMEOUT):
        self._await(
            lambda: self.is_workflow_in_state(ex_id, state),
            delay,
            timeout
        )

    def await_workflow_success(self, ex_id, delay=DEFAULT_DELAY,
                               timeout=DEFAULT_TIMEOUT):
        self.await_workflow_state(ex_id, states.SUCCESS, delay, timeout)

    def await_workflow_error(self, ex_id, delay=DEFAULT_DELAY,
                             timeout=DEFAULT_TIMEOUT):
        self.await_workflow_state(ex_id, states.ERROR, delay, timeout)

    def await_workflow_paused(self, ex_id, delay=DEFAULT_DELAY,
                              timeout=DEFAULT_TIMEOUT):
        self.await_workflow_state(ex_id, states.PAUSED, delay, timeout)

    def await_workflow_cancelled(self, ex_id, delay=DEFAULT_DELAY,
                                 timeout=DEFAULT_TIMEOUT):
        self.await_workflow_state(ex_id, states.CANCELLED, delay, timeout)
