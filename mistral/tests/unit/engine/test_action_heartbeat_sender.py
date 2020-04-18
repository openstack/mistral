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

from unittest import mock

from oslo_config import cfg

from mistral.db.v2 import api as db_api
from mistral.rpc import clients as rpc_clients
from mistral.services import workflows as wf_service
from mistral.tests.unit.engine import base
from mistral.workflow import states


# Use the set_default method to set value otherwise in certain test cases
# the change in value is not permanent.
cfg.CONF.set_default('auth_enable', False, group='pecan')


class ActionHeartbeatSenderBaseTest(base.EngineTestCase):
    def setUp(self):
        # We need to set all required configuration values before starting
        # an engine and an executor.
        self.get_configuration()

        super(ActionHeartbeatSenderBaseTest, self).setUp()

    def get_configuration(self):
        # We need to override configuration values before starting engine.
        # Subclasses can override this method and add/change their own
        # config options.
        self.override_config('check_interval', 1, 'action_heartbeat')
        self.override_config('max_missed_heartbeats', 1, 'action_heartbeat')
        self.override_config('first_heartbeat_timeout', 0, 'action_heartbeat')

    def _do_long_action_success_test(self):
        wf_text = """---
        version: '2.0'

        wf:
          tasks:
            task1:
              action: std.sleep seconds=4
        """

        wf_service.create_workflows(wf_text)

        wf_ex = self.engine.start_workflow('wf')

        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            t_execs = wf_ex.task_executions

            t_ex = self._assert_single_item(
                t_execs,
                name='task1',
                state=states.SUCCESS
            )

            a_execs = db_api.get_action_executions(task_execution_id=t_ex.id)

            self._assert_single_item(
                a_execs,
                name='std.sleep',
                state=states.SUCCESS
            )

    # Disable the ability to send action heartbeats.
    @mock.patch.object(
        rpc_clients.EngineClient,
        'process_action_heartbeats',
        mock.MagicMock()
    )
    def _do_long_action_failure_test_with_disabled_sender(self):
        wf_text = """---
        version: '2.0'

        wf:
          tasks:
            task1:
              action: std.sleep seconds=4
        """

        wf_service.create_workflows(wf_text)

        wf_ex = self.engine.start_workflow('wf')

        self.await_workflow_error(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            t_execs = wf_ex.task_executions

            t_ex = self._assert_single_item(
                t_execs,
                name='task1',
                state=states.ERROR
            )

            a_execs = db_api.get_action_executions(task_execution_id=t_ex.id)

            self._assert_single_item(
                a_execs,
                name='std.sleep',
                state=states.ERROR
            )


class ActionHeartbeatSenderLocalExecutorTest(ActionHeartbeatSenderBaseTest):
    def get_configuration(self):
        super(ActionHeartbeatSenderLocalExecutorTest, self).get_configuration()

        self.override_config('type', 'local', 'executor')

    def test_long_action_success(self):
        self._do_long_action_success_test()

    def test_long_action_failure_with_disabled_sender(self):
        self._do_long_action_failure_test_with_disabled_sender()


class ActionHeartbeatSenderRemoteExecutorTest(ActionHeartbeatSenderBaseTest):
    def get_configuration(self):
        super(
            ActionHeartbeatSenderRemoteExecutorTest,
            self
        ).get_configuration()

        self.override_config('type', 'remote', 'executor')

    def test_long_action_success(self):
        self._do_long_action_success_test()

    def test_long_action_failure_with_disabled_sender(self):
        self._do_long_action_failure_test_with_disabled_sender()
