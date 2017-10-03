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
from oslo_service import service

from mistral.db.v2 import api as db_api
from mistral.engine import engine_server
from mistral.executors import base as exe
from mistral.executors import executor_server
from mistral.rpc import base as rpc_base
from mistral.rpc import clients as rpc_clients
from mistral.tests.unit import base
from mistral.workflow import states


LOG = logging.getLogger(__name__)

# Default delay and timeout in seconds for await_xxx() functions.
DEFAULT_DELAY = 1
DEFAULT_TIMEOUT = 30


def launch_service(s):
    launcher = service.ServiceLauncher(cfg.CONF)

    launcher.launch_service(s)

    launcher.wait()


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
        rpc_base.cleanup()
        rpc_clients.cleanup()
        exe.cleanup()

        self.threads = []

        # Start remote executor.
        if cfg.CONF.executor.type == 'remote':
            LOG.info("Starting remote executor threads...")

            self.executor_client = rpc_clients.get_executor_client()

            exe_svc = executor_server.get_oslo_service(setup_profiler=False)

            self.executor = exe_svc.executor
            self.threads.append(eventlet.spawn(launch_service, exe_svc))
            self.addCleanup(exe_svc.stop, True)

        # Start engine.
        LOG.info("Starting engine threads...")

        self.engine_client = rpc_clients.get_engine_client()

        eng_svc = engine_server.get_oslo_service(setup_profiler=False)

        self.engine = eng_svc.engine
        self.threads.append(eventlet.spawn(launch_service, eng_svc))
        self.addCleanup(eng_svc.stop, True)

        self.addOnException(self.print_executions)
        self.addCleanup(self.kill_threads)

        # Make sure that both services fully started, otherwise
        # the test may run too early.
        if cfg.CONF.executor.type == 'remote':
            exe_svc.wait_started()

        eng_svc.wait_started()

    def kill_threads(self):
        LOG.info("Finishing engine and executor threads...")

        for thread in self.threads:
            thread.kill()

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

    def await_task_running(self, ex_id, delay=DEFAULT_DELAY,
                           timeout=DEFAULT_TIMEOUT):
        self.await_task_state(ex_id, states.RUNNING, delay, timeout)

    def await_task_success(self, ex_id, delay=DEFAULT_DELAY,
                           timeout=DEFAULT_TIMEOUT):
        self.await_task_state(ex_id, states.SUCCESS, delay, timeout)

    def await_task_error(self, ex_id, delay=DEFAULT_DELAY,
                         timeout=DEFAULT_TIMEOUT):
        self.await_task_state(ex_id, states.ERROR, delay, timeout)

    def await_task_cancelled(self, ex_id, delay=DEFAULT_DELAY,
                             timeout=DEFAULT_TIMEOUT):
        self.await_task_state(ex_id, states.CANCELLED, delay, timeout)

    def await_task_paused(self, ex_id, delay=DEFAULT_DELAY,
                          timeout=DEFAULT_TIMEOUT):
        self.await_task_state(ex_id, states.PAUSED, delay, timeout)

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

    def await_workflow_running(self, ex_id, delay=DEFAULT_DELAY,
                               timeout=DEFAULT_TIMEOUT):
        self.await_workflow_state(ex_id, states.RUNNING, delay, timeout)

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
